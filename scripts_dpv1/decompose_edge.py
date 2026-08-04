"""Decompose DPv1's edge into calibration vs information — all three tracks.

Phase 4D found that on CT+MNR, 93.9% of the model's measured +0.983% log-loss
edge over the raw Harville market is reproduced by a **two-parameter Platt
rescaling of that same market estimate** — no features involved. Doug's 19
rank-1 features add +0.060% on top.

If that also holds at Gulfstream, then Phase 4C's headline finding — DPv1
performs better on the CT/MNR bullring circuit than on GP, consistently across
4 of 4 folds — is not evidence of a less efficient market. It is evidence that
the Harville reduction is *worse calibrated* on those tracks, which is a
property of our market model, not of the betting public.

Method: for each rolling-origin fold, fit the calibration on the OTHER folds
(out-of-fold) and apply it to this one, so the calibrated market is never
fitted on the rows it is scored against.

Usage
-----
    python scripts_dpv1/decompose_edge.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))
import dpv1_metrics as M  # noqa: E402


def out_of_fold_calibration(preds: pd.DataFrame) -> np.ndarray:
    """Platt-calibrate p_market using, for each fold, the other folds."""
    cal = np.full(len(preds), np.nan)
    for fold in preds["fold"].unique():
        te = preds["fold"] == fold
        tr = ~te
        a, b = M.fit_market_calibration(
            preds.loc[tr, "p_market"].to_numpy(),
            preds.loc[tr, "y_true"].to_numpy())
        cal[te.to_numpy()] = M.apply_market_calibration(
            preds.loc[te, "p_market"].to_numpy(), a, b)
    return cal


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--preds", default=str(DPV1_DIR / "dpv1_fold_predictions.csv"),
                   help="Phase 4C fold predictions (all three tracks)")
    args = p.parse_args()

    df = pd.read_csv(args.preds)
    df["p_market_cal"] = out_of_fold_calibration(df)

    def ll(y, q):
        q = np.clip(np.asarray(q, float), 1e-9, 1 - 1e-9)
        y = np.asarray(y, float)
        return float(-(y * np.log(q) + (1 - y) * np.log(1 - q)).mean())

    print("Decomposition of DPv1's edge over the raw market")
    print("(Phase 4C model, out-of-sample folds, out-of-fold market calibration)")
    print("=" * 92)
    print(f"{'slice':<9} {'n':>7} {'raw mkt':>9} {'cal mkt':>9} {'DPv1':>9} "
          f"{'edge vs raw':>12} {'edge vs cal':>12} {'% from calib':>13}")
    print("-" * 92)
    slices = {"GP": df["track"] == "GP", "CT": df["track"] == "CT",
              "MNR": df["track"] == "MNR",
              "CT+MNR": df["track"].isin(["CT", "MNR"]),
              "ALL": pd.Series(True, index=df.index)}
    rows = []
    for name, mask in slices.items():
        s = df[mask]
        y = s["y_true"].to_numpy()
        raw, cal, mdl = (ll(y, s["p_market"]), ll(y, s["p_market_cal"]),
                         ll(y, s["y_pred"]))
        e_raw = 100 * (raw - mdl) / raw
        e_cal = 100 * (cal - mdl) / cal
        share = 100 * (raw - cal) / (raw - mdl) if raw > mdl else float("nan")
        rows.append((name, len(s), raw, cal, mdl, e_raw, e_cal, share))
        print(f"{name:<9} {len(s):>7} {raw:>9.5f} {cal:>9.5f} {mdl:>9.5f} "
              f"{e_raw:>11.3f}% {e_cal:>11.3f}% {share:>12.1f}%")
    print("-" * 92)

    gp = next(r for r in rows if r[0] == "GP")
    ctm = next(r for r in rows if r[0] == "CT+MNR")
    print("\nPhase 4C's headline was the gap in 'edge vs raw':")
    print(f"    GP {gp[5]:+.3f}%   vs   CT+MNR {ctm[5]:+.3f}%   "
          f"→ gap {ctm[5] - gp[5]:+.3f}pp")
    print("Measured against a calibrated market instead:")
    print(f"    GP {gp[6]:+.3f}%   vs   CT+MNR {ctm[6]:+.3f}%   "
          f"→ gap {ctm[6] - gp[6]:+.3f}pp")
    print("\nHow much of each track's raw-market edge is pure recalibration:")
    for name, _, raw, cal, mdl, _, _, share in rows:
        print(f"    {name:<9} {share:>6.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
