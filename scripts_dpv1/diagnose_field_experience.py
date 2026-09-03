"""Phase 6D Gap #6: distribution diagnostic for the field-experience features.

    python scripts_dpv1/diagnose_field_experience.py > logs/gap6_diagnostic.txt

Run before retraining. The question it answers is whether these seven features
actually separate the races Gap #6 is about from ordinary racing — if maiden
and non-maiden fields look the same through them, there is nothing here for a
model to learn and the retrain is not worth running.

Read at race grain, not entry grain: these are race-level aggregates broadcast
to every entry, so describing them over 221,399 entries would weight each race
by its field size.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import DEFAULT_DB  # noqa: E402
from new_features.field_experience_features import FEATURES  # noqa: E402

FOCUS = [("CT", "2026-08-29", 3), ("CT", "2026-08-29", 5), ("CT", "2026-08-29", 6)]


def load(db: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cols = ", ".join(f"f.{c}" for c in FEATURES)
        return pd.read_sql_query(f"""
            SELECT rc.id AS race_id, t.code AS track, rd.race_date,
                   rc.race_num, rc.race_type,
                   COUNT(*) AS field_size, {cols}
            FROM entry_features_dpv1 f
            JOIN entries e    ON e.id = f.entry_id
            JOIN races rc     ON rc.id = e.race_id
            JOIN race_days rd ON rd.id = rc.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            GROUP BY rc.id
        """, conn)
    finally:
        conn.close()


def rule(t: str) -> None:
    print("\n" + "=" * 78)
    print(f" {t}")
    print("=" * 78)


def main() -> int:
    df = load(str(DEFAULT_DB))
    df["is_maiden"] = df["race_type"].fillna("").str.upper().str.startswith("MAIDEN")

    rule("GAP #6 FIELD-EXPERIENCE FEATURES -- DISTRIBUTION DIAGNOSTIC")
    print(f" races: {len(df):,}   maiden: {int(df['is_maiden'].sum()):,}"
          f"   non-maiden: {int((~df['is_maiden']).sum()):,}")
    nulls = df[FEATURES].isna().sum()
    print(f" nulls in the new features: {int(nulls.sum())}"
          + ("" if nulls.sum() == 0 else f"  {nulls[nulls > 0].to_dict()}"))

    rule("1. OVERALL DISTRIBUTION (per race)")
    desc = df[FEATURES].describe(percentiles=[.10, .25, .50, .75, .90]).T
    print(desc[["mean", "std", "min", "10%", "25%", "50%", "75%", "90%", "max"]]
          .round(3).to_string())

    rule("2. BY RACE TYPE -- maiden vs non-maiden")
    g = df.groupby("is_maiden")[FEATURES].agg(["mean", "median"])
    for f in FEATURES:
        nm, m = g.loc[False, (f, "mean")], g.loc[True, (f, "mean")]
        nmd, md = g.loc[False, (f, "median")], g.loc[True, (f, "median")]
        print(f" {f:<30} non-maiden mean {nm:8.3f} (med {nmd:6.2f})"
              f"   maiden mean {m:8.3f} (med {md:6.2f})   sep {m - nm:+8.3f}")

    print("\n Separation is what matters here: a feature whose maiden and")
    print(" non-maiden means coincide carries no information about the thing")
    print(" Gap #6 describes, however interesting its overall spread.")

    print("\n By specific maiden type:")
    mt = df[df["is_maiden"]].groupby("race_type")[
        ["field_pct_underraced", "field_pct_debut", "field_avg_career_starts"]
    ].agg(["mean", "count"])
    print(mt.round(3).to_string())

    rule("3. THE THREE CT 2026-08-29 MAIDEN RACES")
    print(" Gap #6's observed cases. If these features work, these races sit in")
    print(" the underraced tail of the corpus.\n")
    for track, date, rn in FOCUS:
        row = df[(df["track"] == track) & (df["race_date"] == date)
                 & (df["race_num"] == rn)]
        if row.empty:
            print(f" {track} {date} R{rn}: not found")
            continue
        r = row.iloc[0]
        print(f" {track} {date} R{rn}  ({r['race_type']}, {int(r['field_size'])} runners)")
        for f in FEATURES:
            v = r[f]
            pct_all = (df[f] < v).mean() * 100
            pct_maid = (df.loc[df["is_maiden"], f] < v).mean() * 100
            print(f"    {f:<30} {v:8.3f}   pctile: all races {pct_all:5.1f}"
                  f"   among maidens {pct_maid:5.1f}")
        print()

    rule("4. WHERE THE FLAG THRESHOLD SITS")
    thr = 0.60
    for label, sub in (("all races", df), ("maiden races", df[df["is_maiden"]]),
                       ("non-maiden", df[~df["is_maiden"]])):
        share = (sub["field_pct_underraced"] >= thr).mean()
        print(f" {label:<14} {share * 100:5.1f}% have field_pct_underraced >= {thr:.2f}"
              f"   (n={len(sub):,})")
    print("\n That is the card_picks maiden-warning threshold, shown here against")
    print(" the continuous feature the model will now see instead of a boolean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
