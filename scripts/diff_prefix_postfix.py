"""Quantify what the Phase 4B.1 alignment fix changed in entry_features_v1.

Compares ``entry_features_v1_prefix`` (snapshot taken before the fix) against
the rebuilt ``entry_features_v1``, per feature, joined on entry_id.

Reports for each feature: whether it changed at all, the share of rows that
changed, the correlation between old and new values, and the mean absolute
difference (scaled by the feature's own standard deviation so features on
different scales are comparable).

A correlation near 0 on a changed feature means the old values were
essentially noise with respect to the correct ones.

Usage
-----
    python scripts/diff_prefix_postfix.py --db scripts/gp_full.db
"""
from __future__ import annotations

import argparse
import sqlite3

import numpy as np
import pandas as pd


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--old", default="entry_features_v1_prefix")
    p.add_argument("--new", default="entry_features_v1")
    p.add_argument("--csv", default=None)
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    old = pd.read_sql_query(f"SELECT * FROM {args.old}", conn).set_index("entry_id").sort_index()
    new = pd.read_sql_query(f"SELECT * FROM {args.new}", conn).set_index("entry_id").sort_index()
    assert old.index.equals(new.index), "entry_id sets differ between snapshots"

    cols = [c for c in new.columns if c in old.columns]
    rows = []
    for c in cols:
        o, n = old[c], new[c]
        if pd.api.types.is_numeric_dtype(n) and pd.api.types.is_numeric_dtype(o):
            o_f, n_f = o.astype("float64"), n.astype("float64")
            both = o_f.notna() & n_f.notna()
            differs = ((o_f != n_f) & both) | (o_f.isna() != n_f.isna())
            pct = float(differs.mean())
            if both.sum() > 1 and o_f[both].std() > 0 and n_f[both].std() > 0:
                corr = float(np.corrcoef(o_f[both], n_f[both])[0, 1])
            else:
                corr = np.nan
            sd = float(n_f.std()) or np.nan
            mad = float((o_f[both] - n_f[both]).abs().mean())
            rows.append({"feature": c, "pct_rows_changed": pct, "corr_old_new": corr,
                         "mean_abs_diff": mad, "mad_over_sd": mad / sd if sd else np.nan,
                         "null_pct_old": float(o_f.isna().mean()),
                         "null_pct_new": float(n_f.isna().mean())})
        else:
            # NULL == NULL must count as "same". A naive string compare makes
            # every null row look changed, which inflates categorical features
            # by exactly their null rate.
            both_null = o.isna() & n.isna()
            differs = (o.astype(str) != n.astype(str)) & ~both_null
            rows.append({"feature": c, "pct_rows_changed": float(differs.mean()),
                         "corr_old_new": np.nan, "mean_abs_diff": np.nan,
                         "mad_over_sd": np.nan,
                         "null_pct_old": float(o.isna().mean()),
                         "null_pct_new": float(n.isna().mean())})

    df = pd.DataFrame(rows).set_index("feature").sort_values(
        "pct_rows_changed", ascending=False)

    changed = df[df["pct_rows_changed"] > 1e-9]
    unchanged = df[df["pct_rows_changed"] <= 1e-9]

    print(f"Compared {len(cols)} features over {len(new)} entries")
    print(f"  CHANGED   : {len(changed)}")
    print(f"  unchanged : {len(unchanged)}")

    print("\n=== CHANGED FEATURES (sorted by share of rows affected) ===")
    print(f"{'feature':<40} {'rows chg':>9} {'corr':>8} {'MAD/sd':>8} "
          f"{'null% old':>10} {'null% new':>10}")
    for f, r in changed.iterrows():
        corr = "  n/a" if np.isnan(r["corr_old_new"]) else f"{r['corr_old_new']:6.3f}"
        mos = "  n/a" if np.isnan(r["mad_over_sd"]) else f"{r['mad_over_sd']:6.3f}"
        print(f"{f:<40} {r['pct_rows_changed']*100:8.2f}% {corr:>8} {mos:>8} "
              f"{r['null_pct_old']*100:9.2f}% {r['null_pct_new']*100:9.2f}%")

    print("\n=== UNCHANGED FEATURES ===")
    for f in unchanged.index:
        print(f"  {f}")

    if len(changed):
        print(f"\nmedian old/new correlation among changed numeric features: "
              f"{changed['corr_old_new'].median():.4f}")

    if args.csv:
        df.to_csv(args.csv)
        print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
