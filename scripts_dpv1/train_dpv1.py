"""DPv1 training: multi-track, ITM target, per-track evaluation.

Architecture (adapted from v2a)
-------------------------------
    fundamental : binary logistic per entry, 95 of Doug's rank 1-2 features
    market      : Harville P(ITM) from per-race-normalised tote win odds
    blend       : sigmoid(alpha*logit(p_f) + beta*logit(p_m) + gamma),
                  alpha/beta/gamma fit per fold on the validation slice

CV is rolling-origin **by year**: train on everything before year Y, validate
on year Y, for Y in 2023..2026.

Phase 4C's question is not "is DPv1 good" but "is DPv1 differently good on the
CT/MNR bullring circuit than on GP", so every fold's predictions are retained
and scored per track.

Usage
-----
    python scripts_dpv1/train_dpv1.py grid          # hyperparameter search
    python scripts_dpv1/train_dpv1.py final         # refit + artifacts
    python scripts_dpv1/train_dpv1.py evaluate      # per-track report tables
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from prepare_training_dpv1 import (  # noqa: E402
    load_full_frame, split_feature_columns, make_preprocessor,
    add_interaction_features, INTERACTION_FEATURES, YearFoldSplitter,
    load_config, rank1_features, DEFAULT_DB, DPV1_LEAKY_FEATURES,
)
from prepare_training import time_decay_weights  # noqa: E402
from fundamental_model_v2a import FundamentalModelITM  # noqa: E402
from market_model_v2a import MarketModelITM  # noqa: E402
from blend_model_v2a import BenterBlendITM  # noqa: E402
import dpv1_metrics as M  # noqa: E402

log = logging.getLogger("train_dpv1")

MODEL_OUT = DPV1_DIR / "dpv1.pkl"
GRID_OUT = DPV1_DIR / "dpv1_grid_results.csv"
PREDS_OUT = DPV1_DIR / "dpv1_predictions_sample.json"
FOLD_PREDS = DPV1_DIR / "dpv1_fold_predictions.csv"

HALF_LIVES_YEARS = [1.0, 1.5, 2.0, 2.5]
L2_VALUES = [0.001, 0.01, 0.1, 1.0]

TRACK_SLICES = {
    "GP": lambda d: d["track"] == "GP",
    "CT": lambda d: d["track"] == "CT",
    "MNR": lambda d: d["track"] == "MNR",
    "CT+MNR": lambda d: d["track"].isin(["CT", "MNR"]),
    "ALL": lambda d: pd.Series(True, index=d.index),
}


def market_p_itm(df: pd.DataFrame) -> np.ndarray:
    """Harville P(ITM) from per-race-normalised implied win probabilities."""
    odds = df["final_odds"].to_numpy(dtype=float)
    rid = df["race_id"].to_numpy()
    raw = np.where((odds > 0) & np.isfinite(odds), 1.0 / (odds + 1.0), np.nan)
    s = pd.Series(raw)
    sums = s.groupby(rid).transform("sum").to_numpy()
    sums = np.where(sums > 0, sums, np.nan)
    return MarketModelITM().predict_p_itm(raw / sums, rid)


# ---------------------------------------------------------------------------
# One fold
# ---------------------------------------------------------------------------

def run_fold(train_df: pd.DataFrame, val_df: pd.DataFrame,
             fund_cols: list[str], half_life: float, l2: float,
             max_iter: int = 200) -> tuple[pd.DataFrame, dict]:
    pre = make_preprocessor().fit(train_df, fund_cols)
    X_tr, X_vl = pre.transform(train_df), pre.transform(val_df)
    w = time_decay_weights(train_df["race_date"],
                           train_df["race_date"].max(), half_life)

    fund = FundamentalModelITM(l2=l2, max_iter=max_iter).fit(
        X_tr, train_df["y_true"].to_numpy(), sample_weight=w,
        feature_names=pre.output_names)

    p_f = fund.predict_probabilities(X_vl)
    p_m = market_p_itm(val_df)
    blend = BenterBlendITM().fit(p_f, p_m, val_df["y_true"].to_numpy())
    p_final = blend.predict(p_f, p_m)

    # Calibrated market, fit on the TRAIN fold only. Raw Harville is
    # overconfident (Phase 4C: ECE 0.033), which made the Phase 4C exacta edge
    # trigger unable to fire. Edge is measured against this instead.
    p_m_tr = market_p_itm(train_df)
    cal_a, cal_b = M.fit_market_calibration(p_m_tr, train_df["y_true"].to_numpy())
    p_m_cal = M.apply_market_calibration(p_m, cal_a, cal_b)

    preds = pd.DataFrame({
        "entry_id": val_df["entry_id"].to_numpy(),
        "race_id": val_df["race_id"].to_numpy(),
        "track": val_df["track"].to_numpy(),
        "race_date": val_df["race_date"].to_numpy(),
        "y_true": val_df["y_true"].to_numpy(),
        "finish_pos": val_df["finish_pos"].to_numpy(),
        "final_odds": val_df["final_odds"].to_numpy(),
        "y_pred": p_final,
        "p_fund": p_f,
        "p_market": p_m,
        "p_market_cal": p_m_cal,
    })
    info = {"alpha": blend.alpha_, "beta": blend.beta_, "gamma": blend.gamma_,
            "fund_loss": fund.final_loss_, "n_features": X_tr.shape[1],
            "cal_a": cal_a, "cal_b": cal_b}
    return preds, info


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------

def cmd_grid(args) -> int:
    df = add_interaction_features(load_full_frame(args.db))
    fund_cols, market_cols = split_feature_columns(df.columns)
    if not args.with_interaction:
        fund_cols = [c for c in fund_cols if c not in INTERACTION_FEATURES]
    log.info("rows=%d races=%d ITM=%.4f | fund=%d market=%d",
             len(df), df["race_id"].nunique(), df["y_true"].mean(),
             len(fund_cols), len(market_cols))

    folds = list(YearFoldSplitter().split(df))
    combos = list(product([y * 365.25 for y in HALF_LIVES_YEARS], L2_VALUES))
    log.info("grid: %d combos x %d folds = %d fits",
             len(combos), len(folds), len(combos) * len(folds))

    rows = []
    for i, (hl, l2) in enumerate(combos, 1):
        log.info("[%d/%d] half_life=%.1fy l2=%g", i, len(combos), hl / 365.25, l2)
        for name, tr, vl in folds:
            t0 = time.perf_counter()
            preds, info = run_fold(df.iloc[tr], df.iloc[vl], fund_cols, hl, l2)
            m_all = M.evaluate_slice(preds, with_wagering=False)
            row = {"fold": name, "half_life_days": hl, "l2": l2,
                   "fit_seconds": time.perf_counter() - t0, **info}
            row.update({f"ALL_{k}": v for k, v in m_all.items()})
            for tname, fn in TRACK_SLICES.items():
                if tname == "ALL":
                    continue
                sl = preds[fn(preds)]
                if len(sl) < 100:
                    continue
                m = M.evaluate_slice(sl, with_wagering=False)
                row.update({f"{tname}_{k}": v for k, v in m.items()})
            rows.append(row)
            log.info("    %s ll=%.4f corr=%.3f a=%.3f b=%.3f (%.1fs)",
                     name, m_all["log_loss"], m_all["corr_logit_pf_pm"],
                     info["alpha"], info["beta"], row["fit_seconds"])
    grid = pd.DataFrame(rows)
    grid.to_csv(args.out, index=False)
    log.info("wrote %s (%d rows)", args.out, len(grid))

    summ = (grid.groupby(["half_life_days", "l2"])
            [["ALL_log_loss", "ALL_corr_logit_pf_pm", "ALL_itm_hit_top3",
              "alpha", "beta"]].mean().reset_index()
            .sort_values("ALL_log_loss"))
    log.info("top 5 combos by mean log-loss:\n%s",
             summ.head().to_string(index=False))
    best = summ.iloc[0]
    log.info("BEST: half_life=%.2fy l2=%g", best["half_life_days"] / 365.25,
             best["l2"])
    return 0


# ---------------------------------------------------------------------------
# Final fit + fold predictions
# ---------------------------------------------------------------------------

@dataclass
class DPv1Model:
    version: str
    trained_at: str
    fund_cols: list[str]
    preprocessor: Any
    fundamental: Any
    blend: Any
    hyperparameters: dict
    training_notes: dict
    coefficients: dict


def _best_combo(grid: pd.DataFrame) -> tuple[float, float]:
    s = (grid.groupby(["half_life_days", "l2"])["ALL_log_loss"].mean()
         .sort_values())
    hl, l2 = s.index[0]
    return float(hl), float(l2)


def cmd_final(args) -> int:
    df = add_interaction_features(load_full_frame(args.db))
    fund_cols, _ = split_feature_columns(df.columns)
    if not args.with_interaction:
        fund_cols = [c for c in fund_cols if c not in INTERACTION_FEATURES]

    grid = pd.read_csv(args.grid)
    hl, l2 = _best_combo(grid)
    log.info("best combo from grid: half_life=%.2fy l2=%g", hl / 365.25, l2)

    # Retain out-of-sample fold predictions for all downstream evaluation.
    frames, infos = [], []
    for name, tr, vl in YearFoldSplitter().split(df):
        preds, info = run_fold(df.iloc[tr], df.iloc[vl], fund_cols, hl, l2,
                               max_iter=args.max_iter)
        preds["fold"] = name
        frames.append(preds)
        infos.append({"fold": name, **info})
        log.info("  %s: n=%d alpha=%.4f beta=%.4f gamma=%.4f",
                 name, len(preds), info["alpha"], info["beta"], info["gamma"])
    fold_preds = pd.concat(frames, ignore_index=True)
    fold_preds.to_csv(args.fold_preds, index=False)
    log.info("wrote %s (%d val entries)", args.fold_preds, len(fold_preds))

    # Final refit on ALL data for the shipped artifact.
    pre = make_preprocessor().fit(df, fund_cols)
    X = pre.transform(df)
    w = time_decay_weights(df["race_date"], df["race_date"].max(), hl)
    fund = FundamentalModelITM(l2=l2, max_iter=args.max_iter).fit(
        X, df["y_true"].to_numpy(), sample_weight=w,
        feature_names=pre.output_names)
    p_f = fund.predict_probabilities(X)
    p_m = market_p_itm(df)
    blend = BenterBlendITM().fit(p_f, p_m, df["y_true"].to_numpy())

    coefs = dict(sorted(zip(pre.output_names, fund.coef_),
                        key=lambda kv: -abs(kv[1])))
    model = DPv1Model(
        version="dpv1.1.0",
        trained_at=pd.Timestamp.now("UTC").isoformat(),
        fund_cols=fund_cols,
        preprocessor=pre,
        fundamental=fund,
        blend=blend,
        hyperparameters={"half_life_days": hl, "l2": l2,
                         "target": "ITM (finish_pos <= 3)",
                         "train_date_min": "2022-01-01",
                         "tracks": ["GP", "CT", "MNR"],
                         "with_interaction": bool(args.with_interaction)},
        training_notes={"n_rows": len(df), "n_races": int(df["race_id"].nunique()),
                        "itm_rate": float(df["y_true"].mean()),
                        "alpha": blend.alpha_, "beta": blend.beta_,
                        "gamma": blend.gamma_,
                        "fund_loss": fund.final_loss_,
                        "excluded_leaky": list(DPV1_LEAKY_FEATURES),
                        "per_fold": infos},
        coefficients=coefs,
    )
    with open(args.model_out, "wb") as f:
        pickle.dump(model, f)
    log.info("wrote %s", args.model_out)
    log.info("blend: alpha=%.4f beta=%.4f gamma=%.4f",
             blend.alpha_, blend.beta_, blend.gamma_)
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grid")
    g.add_argument("--db", default=str(DEFAULT_DB))
    g.add_argument("--out", default=str(GRID_OUT))
    g.add_argument("--with-interaction", action="store_true")
    g.set_defaults(func=cmd_grid)

    f = sub.add_parser("final")
    f.add_argument("--db", default=str(DEFAULT_DB))
    f.add_argument("--grid", default=str(GRID_OUT))
    f.add_argument("--model-out", default=str(MODEL_OUT))
    f.add_argument("--fold-preds", default=str(FOLD_PREDS))
    f.add_argument("--max-iter", type=int, default=400)
    f.add_argument("--with-interaction", action="store_true")
    f.set_defaults(func=cmd_final)

    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
