"""Regression tests for the feature_builder row-order contract (Phase 4B.1).

The bug these guard against
---------------------------
``_prior_by_entity_expanding`` and friends sort internally by
``(entity, race_date, entry_id)``. They used to *return* rows in that sorted
order while several call sites assigned the result straight onto an
entry-ordered frame::

    rolled = _prior_by_entity_expanding(df_w, "horse_id", ["one"], "horse")
    out["career_starts"] = rolled["horse_one"]     # positional, not keyed

Values landed on the wrong entries. Against a SQL ground-truth count of prior
starts the affected features matched on ~9.8% of entries — chance. Roughly two
dozen aggregates were affected, four of them ranked 1 by Doug.

The fix restores the caller's row order before returning, so both access
patterns (positional assignment and merge-on-entry_id) are correct.

These tests fail if that contract is ever broken again.

Usage
-----
    python scripts/test_feature_builder_alignment.py            # synthetic only
    python scripts/test_feature_builder_alignment.py --db scripts/gp_full.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_builder import (  # noqa: E402
    _prior_by_entity_expanding,
    _prior_by_entity_windowed,
    _prior_last_value,
    _prior_days_to_event,
)


class TestFailure(AssertionError):
    pass


def _check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return ok


# ---------------------------------------------------------------------------
# Synthetic fixtures — deliberately NOT pre-sorted by entity
# ---------------------------------------------------------------------------

def _fixture() -> pd.DataFrame:
    """Three horses interleaved, so entity order != row order.

    Expected prior-start counts per row are hand-computed in `expect_starts`.
    Horse 7 has two runners on the same day (entries 8, 9) to exercise the
    same-day exclusion rule.
    """
    rows = [
        # entry_id, horse_id, date,        is_win
        (1, 7, "2024-01-01", 0),
        (2, 3, "2024-01-01", 1),
        (3, 7, "2024-02-01", 1),
        (4, 5, "2024-01-15", 0),
        (5, 3, "2024-03-01", 0),
        (6, 7, "2024-03-01", 0),
        (7, 5, "2024-04-01", 1),
        (8, 7, "2024-05-01", 0),
        (9, 7, "2024-05-01", 1),   # same day as entry 8 — neither sees the other
        (10, 3, "2024-06-01", 1),
    ]
    df = pd.DataFrame(rows, columns=["entry_id", "horse_id", "race_date", "is_win"])
    df["race_date_dt"] = pd.to_datetime(df["race_date"])
    df["one"] = 1.0
    df["is_win"] = df["is_win"].astype(float)
    return df


EXPECT_STARTS = {1: 0, 2: 0, 3: 1, 4: 0, 5: 1, 6: 2, 7: 1, 8: 3, 9: 3, 10: 2}
EXPECT_WINS = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 0, 8: 1, 9: 1, 10: 1}


def test_expanding_positional() -> bool:
    """The exact pattern that was broken: assign the result positionally."""
    df = _fixture()
    rolled = _prior_by_entity_expanding(df, "horse_id", ["one", "is_win"], "h")

    out = pd.DataFrame({"entry_id": df["entry_id"]})
    out["career_starts"] = rolled["h_one"]        # positional
    out["career_wins"] = rolled["h_is_win"]       # positional

    got_s = dict(zip(out["entry_id"], out["career_starts"]))
    got_w = dict(zip(out["entry_id"], out["career_wins"]))
    bad = [f"entry {k}: starts {got_s[k]:.0f} != {v}"
           for k, v in EXPECT_STARTS.items() if got_s[k] != v]
    bad += [f"entry {k}: wins {got_w[k]:.0f} != {v}"
            for k, v in EXPECT_WINS.items() if got_w[k] != v]
    return _check("expanding: positional assignment lands on the right entries",
                  not bad, "; ".join(bad[:4]))


def test_expanding_entry_id_order() -> bool:
    """The returned entry_id column must equal the input's, row for row."""
    df = _fixture()
    rolled = _prior_by_entity_expanding(df, "horse_id", ["one"], "h")
    same = rolled["entry_id"].tolist() == df["entry_id"].tolist()
    return _check("expanding: returns rows in input order", same,
                  f"got {rolled['entry_id'].tolist()}")


def test_expanding_merge_still_works() -> bool:
    """Merging on entry_id must give the same answer as positional access.

    Call sites that were already correct must not regress.
    """
    df = _fixture()
    rolled = _prior_by_entity_expanding(df, "horse_id", ["one"], "h")
    merged = df[["entry_id"]].merge(rolled, on="entry_id", how="left")
    same = np.array_equal(merged["h_one"].to_numpy(), rolled["h_one"].to_numpy())
    return _check("expanding: merge-on-entry_id agrees with positional", same)


def test_windowed_order() -> bool:
    df = _fixture()
    rolled = _prior_by_entity_windowed(df, "horse_id", ["one"], 60, "w")
    same = rolled["entry_id"].tolist() == df["entry_id"].tolist()
    # Horse 7: entry 6 (2024-03-01) sees entries 1 (Jan 1, 60 days) and 3 (Feb 1).
    # Jan 1 -> Mar 1 is 60 days, inclusive of the window boundary.
    val = dict(zip(rolled["entry_id"], rolled["w_one"]))
    ok = same and val[6] == 2 and val[3] == 1
    return _check("windowed: returns rows in input order, counts correct", ok,
                  f"entry3={val.get(3)} entry6={val.get(6)}")


def test_last_value_order() -> bool:
    df = _fixture()
    prev = _prior_last_value(df, "horse_id", ["is_win"], "race_date", "prev")
    same = prev["entry_id"].tolist() == df["entry_id"].tolist()
    val = dict(zip(prev["entry_id"], prev["prev_race_date"]))
    # entry 6 (horse 7, Mar 1) — previous start was Feb 1 (entry 3).
    # entry 8 (horse 7, May 1) — previous start was Mar 1 (entry 6).
    ok = same and val[6] == "2024-02-01" and val[8] == "2024-03-01"
    return _check("last_value: returns rows in input order, lookback correct",
                  ok, f"entry6={val.get(6)} entry8={val.get(8)}")


def test_last_value_same_day_limitation() -> bool:
    """Documents a known, currently-unreachable limitation.

    ``_prior_last_value`` only inspects the immediately-preceding row of the
    entity. When a horse has TWO entries on the same date, the second one
    finds the first at an equal date, fails the strict ``<`` test, and gets
    NULL rather than falling back to the last strictly-earlier start.

    Measured frequency of a horse having >1 entry on the same date:
    **0 of 116,311 entries in gp_full.db, 0 of 207,976 in racing_full.db.**

    Left unfixed deliberately in Phase 4B.1: changing it would alter feature
    values beyond the alignment fix and contaminate the before/after impact
    measurement, for zero real-world gain. This test pins the current
    behaviour so a future change is a conscious one.
    """
    df = _fixture()
    prev = _prior_last_value(df, "horse_id", ["is_win"], "race_date", "prev")
    val = dict(zip(prev["entry_id"], prev["prev_race_date"]))
    # entry 9 shares 2024-05-01 with entry 8; ideally it would see 2024-03-01.
    is_null = val[9] is None or (isinstance(val[9], float) and np.isnan(val[9]))
    return _check("last_value: same-day second entry -> NULL (known, n=0 in corpus)",
                  is_null, f"entry9={val.get(9)}")


def test_days_to_event_order() -> bool:
    df = _fixture()
    dse = _prior_days_to_event(df, "horse_id", "is_win", "last_win")
    same = dse["entry_id"].tolist() == df["entry_id"].tolist()
    val = dict(zip(dse["entry_id"], dse["days_since_last_win"]))
    # Horse 3 won on Jan 1 (entry 2); entry 5 is Mar 1 -> 60 days.
    ok = same and val[5] == 60 and np.isnan(val[1])
    return _check("days_to_event: returns rows in input order", ok,
                  f"entry5={val.get(5)}")


def test_shuffled_input() -> bool:
    """Result must not depend on the caller's row order."""
    df = _fixture()
    shuffled = df.sample(frac=1.0, random_state=17).reset_index(drop=True)

    a = _prior_by_entity_expanding(df, "horse_id", ["one"], "h")
    b = _prior_by_entity_expanding(shuffled, "horse_id", ["one"], "h")

    a_map = dict(zip(a["entry_id"], a["h_one"]))
    b_map = dict(zip(b["entry_id"], b["h_one"]))
    ok = a_map == b_map and b["entry_id"].tolist() == shuffled["entry_id"].tolist()
    return _check("expanding: invariant to caller's row order", ok)


def test_nonstandard_index() -> bool:
    """A caller passing a frame with a non-default index must still be safe."""
    df = _fixture()
    df.index = np.arange(100, 100 + len(df))[::-1]  # descending, non-zero-based
    rolled = _prior_by_entity_expanding(df, "horse_id", ["one"], "h")
    got = dict(zip(rolled["entry_id"], rolled["h_one"]))
    bad = [k for k, v in EXPECT_STARTS.items() if got[k] != v]
    ok = not bad and rolled["entry_id"].tolist() == df["entry_id"].tolist()
    return _check("expanding: correct with a non-default input index", ok,
                  f"wrong entries: {bad}")


# ---------------------------------------------------------------------------
# Ground truth against the real database
# ---------------------------------------------------------------------------

def test_against_sql(db_path: str, sample_mod: int = 997) -> bool:
    """Compare career_starts to a SQL count of prior starts.

    This is the check that originally exposed the bug: the pre-fix pipeline
    matched on 9.8% of sampled entries, the fixed one on 100%.
    """
    conn = sqlite3.connect(db_path)
    truth = pd.read_sql_query(f"""
        SELECT e.id AS entry_id,
          (SELECT count(*) FROM entries e2
             JOIN races r2 ON r2.id = e2.race_id
             JOIN race_days rd2 ON rd2.id = r2.race_day_id
           WHERE e2.horse_id = e.horse_id AND rd2.race_date < rd.race_date
          ) AS true_prior_starts
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE e.id % {sample_mod} = 0
    """, conn)

    df = pd.read_sql_query("""
        SELECT e.id AS entry_id, e.horse_id, rd.race_date
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
    """, conn)
    conn.close()
    df["race_date_dt"] = pd.to_datetime(df["race_date"])
    df["one"] = 1.0

    rolled = _prior_by_entity_expanding(df, "horse_id", ["one"], "h")
    out = pd.DataFrame({"entry_id": df["entry_id"]})
    out["career_starts"] = rolled["h_one"]          # the pattern that was broken

    m = truth.merge(out, on="entry_id")
    rate = (m["career_starts"] == m["true_prior_starts"]).mean()
    return _check(f"SQL ground truth ({len(m)} sampled entries)", rate == 1.0,
                  f"match rate {rate * 100:.1f}%")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=None,
                   help="run the SQL ground-truth check against this database")
    args = p.parse_args()

    print("feature_builder row-order contract")
    print("-" * 60)
    results = [
        test_expanding_positional(),
        test_expanding_entry_id_order(),
        test_expanding_merge_still_works(),
        test_windowed_order(),
        test_last_value_order(),
        test_last_value_same_day_limitation(),
        test_days_to_event_order(),
        test_shuffled_input(),
        test_nonstandard_index(),
    ]
    if args.db:
        print("-" * 60)
        results.append(test_against_sql(args.db))

    print("-" * 60)
    n_pass = sum(results)
    print(f"{n_pass}/{len(results)} passed")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
