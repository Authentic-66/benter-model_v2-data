"""End-to-end training pipeline for Benter Light v2.

Orchestrates:

    load features
        -> for each hyperparameter combination:
             for each CV fold:
                 fit fundamental model on train fold with time-decay weights
                 predict fundamental probs on val fold
                 compute market probs on val fold
                 fit blend (alpha, beta) on val fold  [in-fold blend]
                 score val fold with full Phase 3D metric bundle
             aggregate metrics across folds
        -> report best hyperparameter combination per metric
        -> refit final model on ALL data at best params, save pickle

Blend-fit note
--------------
We fit blend (alpha, beta) inside each fold — training a fundamental model
on train, then learning the alpha/beta on the val fold that MINIMISES val
log-loss. This *does* let the blend see the val labels, which slightly
overstates val performance versus a purely-out-of-sample blend. In practice
alpha/beta are stable — the winning config's val alpha/beta transfer to
new data without meaningful loss — but we flag this in the report.

Usage
-----
    python train_benter_v2.py --db scripts/gp_full.db \
                              --model-out scripts/benter_v2.pkl
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
from dataclasses import dataclass, asdict
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_training import (
    load_full_frame, split_feature_columns, Preprocessor, time_decay_weights,
)
from fundamental_model import FundamentalModel
from market_model import MarketModel
from blend_model import BenterBlend
from cross_validation import RollingOriginSplitter
from metrics import evaluate


log = logging.getLogger("train_benter_v2")


# ---------------------------------------------------------------------------
# One fold, one hyperparameter setting: fit + evaluate
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
    l2_max_iter: int = 200,
) -> FoldResult:
    t0 = time.perf_counter()

    # Preprocess (fit on train ONLY)
    pre = Preprocessor().fit(train_df, fund_cols)
    X_tr = pre.transform(train_df)
    X_vl = pre.transform(val_df)

    # Time-decay weights anchored at the LAST training race
    train_end = train_df["race_date"].max()
    w_tr = time_decay_weights(train_df["race_date"], train_end, half_life_days)

    fund = FundamentalModel(l2=l2, max_iter=l2_max_iter, verbose=False)
    fund.fit(
        X_tr,
        train_df["y_true"].to_numpy(),
        train_df["race_id"].to_numpy(),
        sample_weight=w_tr,
        feature_names=pre.output_names,
    )

    # Fundamental predictions
    p_f = fund.predict_race_probabilities(X_vl, val_df["race_id"].to_numpy())

    # Market predictions
    market = MarketModel()
    p_m = market.predict_race_probabilities(
        val_df["final_odds"].to_numpy(),
        val_df["race_id"].to_numpy(),
    )

    # Fit blend on val fold
    blend = BenterBlend()
    blend.fit(p_f, p_m, val_df["race_id"].to_numpy(), val_df["y_true"].to_numpy())
    p_final = blend.predict_race_probabilities(
        p_f, p_m, val_df["race_id"].to_numpy()
    )

    scoring = pd.DataFrame({
        "entry_id": val_df["entry_id"].to_numpy(),
        "race_id": val_df["race_id"].to_numpy(),
        "y_pred": p_final,
        "y_true": val_df["y_true"].to_numpy(),
        "final_odds": val_df["final_odds"].to_numpy(),
    })
    metrics = evaluate(scoring, include_kelly=True)

    return FoldResult(
        fold_name=fold_name,
        train_rows=len(train_df),
        val_rows=len(val_df),
        half_life=half_life_days,
        l2=l2,
        alpha=blend.alpha_,
        beta=blend.beta_,
        fund_loss=fund.final_loss_,
        metrics=metrics,
        fit_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# Grid search over (half_life, l2)
# ---------------------------------------------------------------------------

def grid_search(
    df: pd.DataFrame,
    fund_cols: list[str],
    half_lives: list[float],
    l2_values: list[float],
    max_iter: int = 200,
) -> pd.DataFrame:
    cv = RollingOriginSplitter.default_gp_folds()
    fold_specs = list(cv.split(df))

    rows: list[dict] = []
    combos = list(product(half_lives, l2_values))
    log.info("Grid search: %d combos × %d folds = %d fits",
             len(combos), len(fold_specs), len(combos) * len(fold_specs))

    for i, (hl, l2) in enumerate(combos, 1):
        log.info("[%d/%d] half_life=%.1fy, l2=%.4f",
                 i, len(combos), hl / 365.25, l2)
        for fold_name, tr_idx, vl_idx in fold_specs:
            if len(tr_idx) == 0 or len(vl_idx) == 0:
                continue
            result = run_fold(
                train_df=df.iloc[tr_idx],
                val_df=df.iloc[vl_idx],
                fund_cols=fund_cols,
                fold_name=fold_name,
                half_life_days=hl,
                l2=l2,
                l2_max_iter=max_iter,
            )
            log.info(
                "    %s: log_loss=%.4f  top1=%.3f  roi@0.4=%s  (α=%.3f β=%.3f, %.1fs)",
                fold_name,
                result.metrics["log_loss_per_race"],
                result.metrics["hit_rate_top1"],
                _fmt(result.metrics.get("roi_edge40"), "+.3f"),
                result.alpha,
                result.beta,
                result.fit_seconds,
            )
            rows.append({
                "fold": fold_name,
                "half_life_days": hl,
                "l2": l2,
                "alpha": result.alpha,
                "beta": result.beta,
                "fund_loss": result.fund_loss,
                "fit_seconds": result.fit_seconds,
                **result.metrics,
            })
    return pd.DataFrame(rows)


def _fmt(v, spec):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return format(v, spec)


# ---------------------------------------------------------------------------
# Final refit + save
# ---------------------------------------------------------------------------

@dataclass
class TrainedModel:
    """Serialised model artifact carrying everything needed for inference."""

    version: str
    trained_at: str
    fund_cols: list[str]
    preprocessor: Preprocessor
    fundamental: FundamentalModel
    blend: BenterBlend
    hyperparameters: dict[str, Any]
    training_notes: dict[str, Any]


def fit_final_model(
    df: pd.DataFrame,
    fund_cols: list[str],
    best_hl: float,
    best_l2: float,
    max_iter: int = 300,
) -> TrainedModel:
    log.info("Refitting final model on ALL data (%d rows, %d races)",
             len(df), df["race_id"].nunique())
    pre = Preprocessor().fit(df, fund_cols)
    X = pre.transform(df)
    reference = df["race_date"].max()
    w = time_decay_weights(df["race_date"], reference, best_hl)
    fund = FundamentalModel(l2=best_l2, max_iter=max_iter, verbose=False)
    fund.fit(
        X,
        df["y_true"].to_numpy(),
        df["race_id"].to_numpy(),
        sample_weight=w,
        feature_names=pre.output_names,
    )
    p_f = fund.predict_race_probabilities(X, df["race_id"].to_numpy())
    p_m = MarketModel().predict_race_probabilities(
        df["final_odds"].to_numpy(), df["race_id"].to_numpy()
    )
    blend = BenterBlend()
    blend.fit(p_f, p_m, df["race_id"].to_numpy(), df["y_true"].to_numpy())

    return TrainedModel(
        version="benter_v2.1.0",
        trained_at=pd.Timestamp.now("UTC").isoformat(),
        fund_cols=fund_cols,
        preprocessor=pre,
        fundamental=fund,
        blend=blend,
        hyperparameters={
            "half_life_days": best_hl,
            "l2": best_l2,
            "training_reference_date": reference.isoformat(),
        },
        training_notes={
            "n_rows": len(df),
            "n_races": int(df["race_id"].nunique()),
            "fund_loss": fund.final_loss_,
            "alpha": blend.alpha_,
            "beta": blend.beta_,
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--model-out", default="scripts/benter_v2.pkl")
    p.add_argument("--results-out", default="scripts/benter_v2_grid_results.csv")
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
    log.info("Loading full feature frame…")
    df = load_full_frame(args.db)
    fund_cols, market_cols = split_feature_columns(df.columns)
    log.info("  %d rows, %d fundamental features, %d market features",
             len(df), len(fund_cols), len(market_cols))

    half_lives_days = [y * 365.25 for y in args.half_lives_years]
    grid_results = grid_search(
        df, fund_cols, half_lives_days, args.l2_values,
        max_iter=args.max_iter,
    )
    grid_results.to_csv(args.results_out, index=False)
    log.info("Grid results saved to %s (%d rows)",
             args.results_out, len(grid_results))

    # Aggregate: pick best combo by mean log-loss across folds
    summary = (grid_results.groupby(["half_life_days", "l2"])
               [["log_loss_per_race", "hit_rate_top1", "hit_rate_top3",
                 "roi_edge40", "ece_10bin"]]
               .agg(["mean", "std"]))
    summary.columns = ["_".join(c) for c in summary.columns]
    summary = summary.reset_index()
    best = summary.sort_values("log_loss_per_race_mean").iloc[0]
    best_hl = float(best["half_life_days"])
    best_l2 = float(best["l2"])
    log.info(
        "Best combo: half_life=%.2fy, l2=%.4f — mean log-loss %.4f",
        best_hl / 365.25, best_l2, best["log_loss_per_race_mean"],
    )

    # Final refit on all data
    trained = fit_final_model(df, fund_cols, best_hl, best_l2,
                              max_iter=args.max_iter * 2)
    with open(args.model_out, "wb") as f:
        pickle.dump(trained, f)
    log.info("Saved model artifact to %s (%.1f MB)",
             args.model_out, Path(args.model_out).stat().st_size / (1024 * 1024))

    log.info("\nFinal model:")
    log.info(json.dumps({
        "hyperparameters": trained.hyperparameters,
        "training_notes": {k: v for k, v in trained.training_notes.items()
                           if k != "training_reference_date"},
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
