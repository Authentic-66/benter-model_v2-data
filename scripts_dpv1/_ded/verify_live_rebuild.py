"""Verify the live feature-table rebuild against the Arm B training table.

    python _ded/verify_live_rebuild.py

Three checks, all on natural keys (track, date, race number, program number)
rather than row ids, so a different load order cannot mask or fake a match:

1. LIVE vs _ded/racing_ded.db -- the rebuilt live table must reproduce the
   table Arm B was actually fitted on, cell for cell.
2. LIVE vs scripts/racing_full.db.pre-ded-rebuild.bak, restricted to the four
   pre-existing tracks -- the only columns allowed to move are the pooled
   jockey/trainer statistics that a wider corpus necessarily widens.
3. No numeric |value| > 1e12 anywhere (the INT64_MIN check from the
   TRACK_CODES bug, kept as a standing assertion).
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
LIVE = REPO / "scripts" / "racing_full.db"
TRAIN = HERE / "racing_ded.db"
BACKUP = REPO / "scripts" / "racing_full.db.pre-ded-rebuild.bak"

KEY = ["k_track", "k_date", "k_race", "k_prog"]
SQL = """
SELECT t.code AS k_track, d.race_date AS k_date, r.race_num AS k_race,
       CAST(e.program_num AS TEXT) AS k_prog, f.*
FROM entry_features_dpv1 f
JOIN entries e ON e.id = f.entry_id
JOIN races r ON r.id = e.race_id
JOIN race_days d ON d.id = r.race_day_id
JOIN tracks t ON t.id = d.track_id
"""


def load(path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    df = pd.read_sql_query(SQL, conn)
    conn.close()
    df = df.drop(columns=[c for c in ("entry_id",) if c in df.columns])
    dup = df.duplicated(subset=KEY).sum()
    if dup:
        raise RuntimeError(f"{path.name}: {dup} duplicate natural keys")
    return df.set_index(KEY).sort_index()


def compare(a: pd.DataFrame, b: pd.DataFrame, label_a: str, label_b: str,
            rows: pd.Index | None = None) -> dict[str, int]:
    """Per-column count of cells that differ. NaN == NaN counts as equal."""
    cols = [c for c in a.columns if c in b.columns]
    idx = a.index.intersection(b.index) if rows is None else rows
    a, b = a.loc[idx, cols], b.loc[idx, cols]
    diffs: dict[str, int] = {}
    for c in cols:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv = pd.to_numeric(x, errors="coerce").astype("float64")
            yv = pd.to_numeric(y, errors="coerce").astype("float64")
            ne = ~(np.isclose(xv, yv, rtol=0, atol=1e-9, equal_nan=True))
        else:
            xs, ys = x.astype("object"), y.astype("object")
            ne = ~((xs == ys) | (xs.isna() & ys.isna()))
        n = int(ne.sum())
        if n:
            diffs[c] = n
    only_a = sorted(set(a.columns) - set(b.columns))
    only_b = sorted(set(b.columns) - set(a.columns))
    print(f"\n-- {label_a} vs {label_b}: {len(idx):,} shared rows, "
          f"{len(cols)} shared columns")
    if only_a or only_b:
        print(f"   columns only in {label_a}: {only_a}")
        print(f"   columns only in {label_b}: {only_b}")
    return diffs


def main() -> int:
    ok = True
    print("loading tables...")
    live = load(LIVE)
    train = load(TRAIN)
    print(f"  live  {len(live):,} rows x {len(live.columns)} cols")
    print(f"  train {len(train):,} rows x {len(train.columns)} cols")

    # --- Check 1: live must reproduce the Arm B training table exactly -----
    if len(live) != len(train):
        print(f"\n!! row-count mismatch: live {len(live):,} vs train {len(train):,}")
        ok = False
    missing = train.index.difference(live.index)
    extra = live.index.difference(train.index)
    if len(missing) or len(extra):
        print(f"\n!! key mismatch: {len(missing):,} in train not live, "
              f"{len(extra):,} in live not train")
        print(f"   sample missing: {list(missing[:5])}")
        print(f"   sample extra:   {list(extra[:5])}")
        ok = False
    d1 = compare(live, train, "LIVE", "ARM-B TRAIN")
    if d1:
        print("   !! DIFFERING COLUMNS (must be none):")
        for c, n in sorted(d1.items(), key=lambda kv: -kv[1]):
            print(f"      {c:45} {n:>8,}")
        ok = False
    else:
        print("   OK - identical on every shared cell")

    # --- Check 2: existing tracks vs the pre-rebuild backup ---------------
    old = load(BACKUP)
    existing = old.index  # backup holds only the four pre-existing tracks
    d2 = compare(live, old, "LIVE", "PRE-REBUILD BACKUP", rows=existing)
    n_rows = len(existing)
    print(f"   {len(d2)} of {len(old.columns)} columns changed on "
          f"{n_rows:,} existing-track rows")
    for c, n in sorted(d2.items(), key=lambda kv: -kv[1])[:15]:
        print(f"      {c:45} {n:>8,}  ({100 * n / n_rows:5.2f}%)")

    # --- Check 3: no INT64_MIN-style garbage ------------------------------
    num = live.select_dtypes(include=[np.number])
    big = {}
    for c in num.columns:
        v = pd.to_numeric(num[c], errors="coerce")
        n = int((v.abs() > 1e12).sum())
        if n:
            big[c] = n
    print(f"\n-- numeric |value| > 1e12 in the live table: "
          f"{'none' if not big else big}")
    if big:
        ok = False

    print("\n" + ("VERIFY PASS" if ok else "VERIFY FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
