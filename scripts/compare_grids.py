"""Compare a pre-fix and post-fix grid-search CSV, using each report's own
selection rule (best mean log-loss across folds).

Prints the head-to-head at the winning combination plus the per-fold detail,
so the Phase 4B.1 report can quote numbers that are directly comparable to
what Phase 3E / 3F / 3G published.

Usage
-----
    python scripts/compare_grids.py --old scripts/benter_v2_grid_phase3e.csv \
                                    --new scripts/benter_v2_grid_rebuilt.csv \
                                    --label-old "Phase 3E (buggy)" \
                                    --label-new "Phase 4B.1 (fixed)"
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


WIN_METRICS = ["log_loss_per_race", "hit_rate_top1", "hit_rate_top3",
               "ece_10bin", "alpha", "beta"]
ITM_METRICS = ["log_loss_per_race", "itm_hit_rate_top3", "itm_hit_rate_top4",
               "itm_precision_top3", "ece_10bin", "alpha", "beta", "gamma"]


def summarize(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    cols = [m for m in metrics if m in df.columns]
    s = df.groupby(["half_life_days", "l2"])[cols].mean().reset_index()
    return s.sort_values("log_loss_per_race")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--label-old", default="before")
    p.add_argument("--label-new", default="after")
    p.add_argument("--itm", action="store_true", help="use ITM metric set")
    args = p.parse_args()

    metrics = ITM_METRICS if args.itm else WIN_METRICS
    old = pd.read_csv(args.old)
    new = pd.read_csv(args.new)

    so, sn = summarize(old, metrics), summarize(new, metrics)
    bo, bn = so.iloc[0], sn.iloc[0]

    print("=" * 78)
    print(f"{args.label_old}   vs   {args.label_new}")
    print("=" * 78)
    print(f"\nBest combo ({args.label_old}): "
          f"half_life={bo['half_life_days']/365.25:.1f}y  l2={bo['l2']}")
    print(f"Best combo ({args.label_new}): "
          f"half_life={bn['half_life_days']/365.25:.1f}y  l2={bn['l2']}")

    print(f"\n{'metric':<24} {args.label_old:>18} {args.label_new:>18} {'delta':>12}")
    print("-" * 76)
    for m in metrics:
        if m not in so.columns or m not in sn.columns:
            continue
        o, n = float(bo[m]), float(bn[m])
        print(f"{m:<24} {o:>18.4f} {n:>18.4f} {n - o:>+12.4f}")

    # Per-fold at each side's own best combo.
    def folds(df, best):
        sel = df[(df["half_life_days"] == best["half_life_days"])
                 & (df["l2"] == best["l2"])]
        return sel.set_index("fold")

    fo, fn = folds(old, bo), folds(new, bn)
    common = [f for f in fo.index if f in fn.index]
    key = "itm_hit_rate_top3" if args.itm else "hit_rate_top1"
    print(f"\nPer-fold (each at its own best combo)")
    print(f"{'fold':<20} {'log-loss old':>13} {'new':>10} {'Δ':>9} "
          f"{key + ' old':>22} {'new':>10} {'α old':>8} {'α new':>8}")
    print("-" * 108)
    for f in common:
        print(f"{f:<20} {fo.loc[f, 'log_loss_per_race']:>13.4f} "
              f"{fn.loc[f, 'log_loss_per_race']:>10.4f} "
              f"{fn.loc[f, 'log_loss_per_race'] - fo.loc[f, 'log_loss_per_race']:>+9.4f} "
              f"{fo.loc[f, key]:>22.4f} {fn.loc[f, key]:>10.4f} "
              f"{fo.loc[f, 'alpha']:>8.3f} {fn.loc[f, 'alpha']:>8.3f}")

    print(f"\nSpread across all combos (how much hyperparameters matter):")
    for label, s in ((args.label_old, so), (args.label_new, sn)):
        r = s["log_loss_per_race"]
        print(f"  {label:<20} log-loss range {r.min():.4f} – {r.max():.4f} "
              f"(spread {r.max() - r.min():.4f})")
        a = s["alpha"]
        print(f"  {'':<20} alpha    range {a.min():+.4f} – {a.max():+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
