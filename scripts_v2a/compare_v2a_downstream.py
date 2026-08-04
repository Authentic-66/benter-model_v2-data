"""Downstream v2a metrics for two model artifacts, scored identically.

The Phase 3G headline numbers (top-3 hit, precision, full-sweep, trifecta box
ROI) are computed inside ``generate_phase3g_reports.make_phase3g_report``,
which writes the historical report file. Phase 4B.1 needs those same numbers
for the pre-fix and post-fix models *without* overwriting that report, so
this script imports the reusable pieces and prints a side-by-side.

Both models are re-scored over the same rolling-origin val folds, so the
comparison isolates the feature fix.

Usage
-----
    python scripts_v2a/compare_v2a_downstream.py \
        --old scripts_v2a/benter_v2a.pkl \
        --new scripts_v2a/benter_v2a_rebuilt.pkl
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from generate_phase3g_reports import (  # noqa: E402
    rebuild_v2a_predictions, load_v2a_frame, _load_trifecta_payouts,
)
from itm_metrics import evaluate_itm, trifecta_box_roi, longshot_metrics  # noqa: E402
from longshot_detector import flag_longshots  # noqa: E402

# The .pkl artifacts were written by train_benter_v2a.py running as __main__,
# so pickle looks their class up in __main__. Bind it here so this script can
# unpickle them without modifying the training script.
from train_benter_v2a import TrainedModelITM  # noqa: E402,F401


def score(pkl: Path, df: pd.DataFrame, payouts: pd.DataFrame) -> dict:
    with open(pkl, "rb") as f:
        model = pickle.load(f)
    preds = rebuild_v2a_predictions(df, model)

    out = dict(evaluate_itm(preds))
    out["n_scored"] = len(preds)
    out["alpha"] = model.training_notes["alpha"]
    out["beta"] = model.training_notes["beta"]
    out["gamma"] = model.training_notes["gamma"]
    out["half_life_days"] = model.hyperparameters["half_life_days"]
    out["l2"] = model.hyperparameters["l2"]

    roi = trifecta_box_roi(
        preds[["entry_id", "race_id", "y_pred", "y_true", "final_odds",
               "finish_pos"]],
        payouts, k=3,
    )
    out["trifecta_races"] = roi["n_races"]
    out["trifecta_hits"] = roi["n_hits"]
    out["trifecta_stake"] = roi["stake_total"]
    out["trifecta_return"] = roi["return_total"]
    out["trifecta_roi"] = roi["roi"]

    preds = preds.copy()
    preds["rank"] = preds.groupby("race_id")["y_pred"].rank(
        ascending=False, method="first")
    flags = flag_longshots(preds["y_pred"].to_numpy(),
                           preds["y_pred_market_only"].to_numpy(),
                           preds["rank"].to_numpy())
    ls = longshot_metrics(preds, pd.Series(flags, index=preds.index))
    out["longshot_flagged"] = ls["n_flagged"]
    out["longshot_hits"] = ls["hits"]
    out["longshot_precision"] = ls["precision"]
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--old", default="scripts_v2a/benter_v2a.pkl")
    p.add_argument("--new", default="scripts_v2a/benter_v2a_rebuilt.pkl")
    p.add_argument("--db", default="scripts/gp_full.db")
    args = p.parse_args()

    print("Loading 2022+ frame (current, corrected features)…")
    df = load_v2a_frame(args.db)
    payouts = _load_trifecta_payouts()

    print("Scoring old model…")
    old = score(Path(args.old), df, payouts)
    print("Scoring new model…")
    new = score(Path(args.new), df, payouts)

    print("\nNOTE: both models are scored on the CURRENT (corrected) feature")
    print("table, so this isolates the effect of the refit. The pre-fix model's")
    print("published Phase 3G numbers came from the buggy features it was")
    print("trained on — see the grid comparison for that side.\n")

    keys = [
        ("itm_hit_rate_top3", "ITM hit rate top-3", "pct"),
        ("itm_hit_rate_top4", "ITM hit rate top-4", "pct"),
        ("itm_precision_top3", "ITM precision top-3", "pct"),
        ("itm_full_sweep_top_3", "Full sweep top-3", "pct"),
        ("longshot_flagged", "Longshots flagged", "int"),
        ("longshot_precision", "Longshot precision", "pct"),
        ("trifecta_races", "Trifecta races bet", "int"),
        ("trifecta_hits", "Trifecta hits", "int"),
        ("trifecta_roi", "Trifecta box ROI", "pct"),
        ("alpha", "alpha (fundamental)", "num"),
        ("beta", "beta (market)", "num"),
        ("gamma", "gamma (intercept)", "num"),
    ]
    print(f"{'metric':<26} {'old':>14} {'new':>14} {'delta':>14}")
    print("-" * 72)
    for k, label, kind in keys:
        o, n = old[k], new[k]
        if kind == "pct":
            print(f"{label:<26} {o*100:>13.2f}% {n*100:>13.2f}% {(n-o)*100:>+13.2f}%")
        elif kind == "int":
            print(f"{label:<26} {o:>14,} {n:>14,} {n-o:>+14,}")
        else:
            print(f"{label:<26} {o:>14.4f} {n:>14.4f} {n-o:>+14.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
