"""End-to-end training pipeline for Benter v2a (ITM target, 2022+ scope).

Same orchestration shape as ``scripts/train_benter_v2.py`` but

    * loads via ``prepare_training_v2a.load_full_frame`` (ITM target, 2022+
      window),
    * fits ``FundamentalModelITM`` (binary logistic, per-entry sigmoid),
    * computes market P(ITM) via ``MarketModelITM`` (Harville),
    * blends via ``BenterBlendITM`` (3-parameter logit blend),
    * evaluates via ``itm_metrics.evaluate_itm``.

Blend is fit *on the val fold* — same convention as v2 (documented in
Phase 3E's report). The blend has only 3 parameters so its influence on
val log-loss is minimal, and the α values transfer cleanly to fresh data.
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from prepare_training_v2a import load_full_frame                       # noqa: E402
from prepare_training import Preprocessor, split_feature_columns, time_decay_weights  # noqa: E402
from fundamental_model_v2a import FundamentalModelITM                  # noqa: E402
from market_model_v2a import MarketModelITM                            # noqa: E402
from blend_model_v2a import BenterBlendITM                             # noqa: E402
from cross_validation import RollingOriginSplitter                     # noqa: E402
from metrics import evaluate as evaluate_phase3d                       # noqa: E402
from itm_metrics import evaluate_itm                                   # noqa: E402


log = logging.getLogger("train_benter_v2a")


# ---------------------------------------------------------------------------
# One-fold run
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    fold_name: str
    train_rows: int
    val_rows: int
    half_life: float
    l2: float
    alpha: float
    beta: float
    gamma: float
    fund_loss: float
    metrics: dict[str, float]
    fit_seconds: float


def run_fold(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    fund_cols: list[str],
    fold_name: str,
    half_life_days: float,
    l2: float,
    max_iter: int = 200,
) -> FoldResult:
    t0 = time.perf_counter()

    pre = Preprocessor().fit(train_df, fund_cols)
    X_tr = pre.transform(train_df)
    X_vl = pre.transform(val_df)

    train_end = train_df["race_date"].max()
    w_tr = time_decay_weights(train_df["race_date"], train_end, half_life_days)

    fund = FundamentalModelITM(l2=l2, max_iter=max_iter, verbose=False)
    fund.fit(
        X_tr,
        train_df["y_true"].to_numpy(),
        sample_weight=w_tr,
        feature_names=pre.output_names,
    )

    # Val predictions
    p_f = fund.predict_probabilities(X_vl)
    p_m = MarketModelITM().predict_p_itm(
        _market_win_p_per_race(val_df),
        val_df["race_id"].to_numpy(),
    )

    # Blend on val
    blend = BenterBlendITM().fit(
        p_f, p_m,
        val_df["y_true"].to_numpy(),
    )
    p_final = blend.predict(p_f, p_m)

    scoring = pd.DataFrame({
        "entry_id": val_df["entry_id"].to_numpy(),
        "race_id":  val_df["race_id"].to_numpy(),
        "y_pred":   p_final,
        "y_true":   val_df["y_true"].to_numpy(),
        "final_odds": val_df["final_odds"].to_numpy(),
        "finish_pos": val_df["finish_pos"].to_numpy(),
    })
    # Phase 3D metrics are win-oriented; we still compute them for reference
    # (they'll look weird because y_true is now ITM, but log-loss, ECE, etc.
    # still measure predictive fit against ITM). The primary metrics are the
    # ITM bundle.
    metrics = {**evaluate_phase3d(scoring),
               **evaluate_itm(scoring)}

    return FoldResult(
        fold_name=fold_name,
        train_rows=len(train_df),
        val_rows=len(val_df),
        half_life=half_life_days,
        l2=l2,
        alpha=blend.alpha_,
        beta=blend.beta_,
        gamma=blend.gamma_,
        fund_loss=fund.final_loss_,
        metrics=metrics,
        fit_seconds=time.perf_counter() - t0,
    )


def _market_win_p_per_race(df: pd.DataFrame) -> np.ndarray:
    odds = df["final_odds"].to_numpy(dtype=float)
    rid = df["race_id"].to_numpy()
    raw = np.where((odds > 0) & np.isfinite(odds), 1.0 / (odds + 1.0), np.nan)
    s = pd.Series(raw)
    sums = s.groupby(rid).transform("sum").to_numpy()
    sums = np.where(sums > 0, sums, np.nan)
    return raw / sums


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------

def grid_search(
    df: pd.DataFrame,
    fund_cols: list[str],
    half_lives_days: list[float],
    l2_values: list[float],
    max_iter: int = 200,
) -> pd.DataFrame:
    cv = RollingOriginSplitter.default_gp_folds()
    fold_specs = list(cv.split(df))

    rows: list[dict] = []
    combos = list(product(half_lives_days, l2_values))
    log.info("Grid: %d combos x %d folds = %d fits",
             len(combos), len(fold_specs), len(combos) * len(fold_specs))

    for i, (hl, l2) in enumerate(combos, 1):
        log.info("[%d/%d] half_life=%.1fy, l2=%.4f",
                 i, len(combos), hl / 365.25, l2)
        for fold_name, tr_idx, vl_idx in fold_specs:
            if len(tr_idx) == 0 or len(vl_idx) == 0:
                continue
            r = run_fold(
                train_df=df.iloc[tr_idx],
                val_df=df.iloc[vl_idx],
                fund_cols=fund_cols,
                fold_name=fold_name,
                half_life_days=hl,
                l2=l2,
                max_iter=max_iter,
            )
            log.info(
                "    %s: log_loss=%.4f  ITMtop3=%.3f  ITMprec_top3=%.3f  "
                "(alpha=%.3f beta=%.3f gamma=%.3f, %.1fs)",
                fold_name,
                r.metrics["log_loss_per_race"],
                r.metrics["itm_hit_rate_top3"],
                r.metrics["itm_precision_top3"],
                r.alpha, r.beta, r.gamma, r.fit_seconds,
            )
            rows.append({
                "fold": fold_name,
                "half_life_days": hl,
                "l2": l2,
                "alpha": r.alpha,
                "beta": r.beta,
                "gamma": r.gamma,
                "fund_loss": r.fund_loss,
                "fit_seconds": r.fit_seconds,
                **r.metrics,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Final model
# ---------------------------------------------------------------------------

@dataclass
class TrainedModelITM:
    version: str
    trained_at: str
    fund_cols: list[str]
    preprocessor: Preprocessor
    fundamental: FundamentalModelITM
    blend: BenterBlendITM
    hyperparameters: dict[str, Any]
    training_notes: dict[str, Any]


def fit_final_model(
    df: pd.DataFrame,
    fund_cols: list[str],
    best_hl: float,
    best_l2: float,
    max_iter: int = 300,
) -> TrainedModelITM:
    log.info("Refitting final model on ALL 2022+ data (%d rows, %d races)",
             len(df), df["race_id"].nunique())
    pre = Preprocessor().fit(df, fund_cols)
    X = pre.transform(df)
    reference = df["race_date"].max()
    w = time_decay_weights(df["race_date"], reference, best_hl)
    fund = FundamentalModelITM(l2=best_l2, max_iter=max_iter, verbose=False)
    fund.fit(
        X,
        df["y_true"].to_numpy(),
        sample_weight=w,
        feature_names=pre.output_names,
    )
    p_f = fund.predict_probabilities(X)
    p_m = MarketModelITM().predict_p_itm(
        _market_win_p_per_race(df),
        df["race_id"].to_numpy(),
    )
    blend = BenterBlendITM().fit(p_f, p_m, df["y_true"].to_numpy())

    return TrainedModelITM(
        version="benter_v2a.1.0",
        trained_at=pd.Timestamp.now("UTC").isoformat(),
        fund_cols=fund_cols,
        preprocessor=pre,
        fundamental=fund,
        blend=blend,
        hyperparameters={
            "half_life_days": best_hl,
            "l2": best_l2,
            "training_reference_date": reference.isoformat(),
            "training_date_min": "2022-01-01",
            "target": "ITM (finish_pos <= 3)",
        },
        training_notes={
            "n_rows": len(df),
            "n_races": int(df["race_id"].nunique()),
            "fund_loss": fund.final_loss_,
            "alpha": blend.alpha_,
            "beta": blend.beta_,
            "gamma": blend.gamma_,
            "itm_positive_rate_train": float(df["y_true"].mean()),
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--model-out", default="scripts_v2a/benter_v2a.pkl")
    p.add_argument("--results-out", default="scripts_v2a/benter_v2a_grid.csv")
    p.add_argument("--half-lives-years", nargs="+", type=float,
                   default=[1.0, 1.5, 2.0, 2.5, 3.0])
    p.add_argument("--l2-values", nargs="+", type=float,
                   default=[0.001, 0.01, 0.1, 1.0])
    p.add_argument("--max-iter", type=int, default=200)
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log.info("Loading 2022+ feature frame...")
    df = load_full_frame(args.db)
    fund_cols, market_cols = split_feature_columns(df.columns)
    log.info("  %d rows, %d races (2022-2026), %d fund features, ITM+ rate %.3f",
             len(df), df["race_id"].nunique(), len(fund_cols), df["y_true"].mean())

    half_lives = [y * 365.25 for y in args.half_lives_years]
    grid = grid_search(df, fund_cols, half_lives, args.l2_values,
                       max_iter=args.max_iter)
    grid.to_csv(args.results_out, index=False)
    log.info("Grid results -> %s (%d rows)", args.results_out, len(grid))

    summary = (grid.groupby(["half_life_days", "l2"])
               [["log_loss_per_race", "itm_hit_rate_top3", "itm_hit_rate_top4",
                 "itm_precision_top3", "ece_10bin", "alpha", "beta", "gamma"]]
               .agg(["mean", "std"]))
    summary.columns = ["_".join(c) for c in summary.columns]
    summary = summary.reset_index()
    best = summary.sort_values("log_loss_per_race_mean").iloc[0]
    best_hl = float(best["half_life_days"])
    best_l2 = float(best["l2"])
    log.info("Best combo: half_life=%.2fy, l2=%.4f -- mean log-loss %.4f, "
             "ITM hit@3 %.3f",
             best_hl / 365.25, best_l2,
             best["log_loss_per_race_mean"], best["itm_hit_rate_top3_mean"])

    trained = fit_final_model(df, fund_cols, best_hl, best_l2,
                              max_iter=args.max_iter * 2)
    with open(args.model_out, "wb") as f:
        pickle.dump(trained, f)
    log.info("Saved %s (%.1f MB)", args.model_out,
             Path(args.model_out).stat().st_size / (1024 * 1024))
    log.info("\nFinal model summary:\n%s", json.dumps({
        "hyperparameters": trained.hyperparameters,
        "training_notes": trained.training_notes,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
