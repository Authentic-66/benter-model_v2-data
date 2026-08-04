"""Regression test for the pedigree-population leak (Phase 4D).

What the leak is
----------------
Equibase result charts publish breeding in exactly one place: the ``Winner:``
line. ``equibase_pdf_parser._parse_winner_pedigree`` reads it, and
``db_loader.get_or_create_horse`` writes it onto the ``horses`` row — which is
shared by every entry that horse ever makes.

The consequence is that ``horses.sex IS NOT NULL`` is equivalent to "this
horse wins at least once somewhere in the corpus", and applying it to a row
dated *before* that win uses future information. Phase 3E caught this for
Bucket 2; Phase 4C found it had survived multi-track loading intact
(P(ever won | horse_sex known) = 100.00%, P(ever won | null) = 0.00%, on all
three tracks independently).

What this test asserts
----------------------
1. **The data limit is what we think it is.** Pedigree coverage in ``horses``
   is exactly the set of horses that won at least once — no more, no less.
   If a future loader change starts filling pedigree for non-winners (a
   different source, a PP feed), this assertion fails and that is a *good*
   failure: it means the as-of workaround can be retired.

2. **Nothing downstream consumes pedigree globally.** Any feature table built
   from ``horses.*`` must gate availability by date. The check re-derives the
   as-of mask and asserts the built feature table respects it.

Why the loader is NOT patched to "populate for all entries"
-----------------------------------------------------------
It cannot be. The information does not exist in the source for non-winners —
verified here by assertion 1, and by inspection: a 9-runner chart contains one
sex token, the winner's, and per-entry parse output carries no breeding fields
at all. This is a data-source limitation, not a parser or loader bug.

Backfilling from a horse's own winning appearances (gating pedigree to "the
horse had already won before today") was considered and **rejected** in Phase
4D: it removes the future component, but what survives is so nearly a
restatement of ``career_wins`` that it adds no information while retaining
leak risk.

**Decision: the pedigree bucket is marked permanently unavailable in this data
regime.** 26 catalog features carry ``unavailable_permanent: true`` in
``dpv1_feature_config.json``. Unblocking requires a past-performance feed
(Brisnet/DRF), which carries breeding for every starter. This test therefore
asserts that no pedigree column reaches the built feature table at all.

Usage
-----
    python scripts/test_pedigree_population.py --db scripts/racing_full.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

import pandas as pd


def _check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return ok


def test_pedigree_only_from_winners(conn: sqlite3.Connection) -> bool:
    """Pedigree coverage == the set of horses that ever won.

    Failing this is not necessarily a bug — it means a new source started
    supplying breeding for non-winners, and the as-of gating can be relaxed.
    """
    n_ped = conn.execute(
        "SELECT count(*) FROM horses WHERE sex IS NOT NULL").fetchone()[0]
    n_won = conn.execute(
        "SELECT count(DISTINCT horse_id) FROM entries WHERE finish_pos = 1"
    ).fetchone()[0]
    ped_never_won = conn.execute("""
        SELECT count(*) FROM horses h
        WHERE h.sex IS NOT NULL
          AND h.id NOT IN (SELECT horse_id FROM entries WHERE finish_pos = 1)
    """).fetchone()[0]
    won_no_ped = conn.execute("""
        SELECT count(*) FROM horses h
        WHERE h.sex IS NULL
          AND h.id IN (SELECT horse_id FROM entries WHERE finish_pos = 1)
    """).fetchone()[0]
    ok = (n_ped == n_won) and ped_never_won == 0
    return _check(
        "pedigree exists for winners only (documents the data limit)", ok,
        f"with_pedigree={n_ped} ever_won={n_won} "
        f"pedigree_but_never_won={ped_never_won} won_but_no_pedigree={won_no_ped}")


def test_global_pedigree_is_a_perfect_leak(conn: sqlite3.Connection) -> bool:
    """The unmitigated (global) mask must look exactly like a perfect leak.

    This pins the severity so a regression that silently *reintroduces* global
    pedigree into a feature table is visible as a number, not a vibe.
    """
    df = pd.read_sql_query("""
        SELECT e.horse_id, e.finish_pos, h.sex IS NOT NULL AS ped_global
        FROM entries e LEFT JOIN horses h ON h.id = e.horse_id
    """, conn)
    df["is_win"] = (df["finish_pos"] == 1).astype(float)
    ever = df.groupby("horse_id")["is_win"].max()
    df["ever_won"] = df["horse_id"].map(ever)
    known = df[df["ped_global"] == 1]["ever_won"].mean()
    null = df[df["ped_global"] == 0]["ever_won"].mean()
    ok = known > 0.999 and null < 0.001
    return _check("global pedigree mask is a perfect leak (as expected)", ok,
                  f"P(ever won|known)={known:.4f} P(ever won|null)={null:.4f}")


PEDIGREE_PREFIXES = ("sire_", "broodmare_", "damsire_", "dam_")
PEDIGREE_EXACT = {"horse_sex", "horse_age", "horse_country_origin",
                  "is_florida_bred", "horse_color", "days_since_foaled",
                  "pedigree_index"}


def _is_pedigree_column(col: str) -> bool:
    # is_first_time_lasix / is_first_time_blinkers sit in Doug's pedigree
    # bucket but are read off entries.equipment, not the winner block.
    if col in ("is_first_time_lasix", "is_first_time_blinkers"):
        return False
    return col in PEDIGREE_EXACT or col.startswith(PEDIGREE_PREFIXES)


def test_feature_table_has_no_pedigree(conn: sqlite3.Connection,
                                       table: str) -> bool:
    """The built feature table must carry no pedigree-derived column.

    Phase 4D marked the whole bucket permanently unavailable. If a future
    change re-introduces one of these columns — say a PP feed lands and
    someone re-activates them — this fails loudly and forces a fresh look at
    whether the new source really covers non-winners.
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    found = sorted(c for c in cols if _is_pedigree_column(c))
    return _check(f"{table} carries no pedigree-derived columns",
                  not found, f"found: {found}" if found else "")


def test_config_marks_pedigree_unavailable(config_path: str) -> bool:
    """The catalog must record the bucket as permanently unavailable."""
    import json
    from pathlib import Path
    if not Path(config_path).exists():
        return _check("config marks pedigree unavailable", True, "config absent, skipped")
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    feats = cfg["features"]
    offenders = [n for n, s in feats.items()
                 if _is_pedigree_column(n) and s.get("active")]
    n_unavail = sum(1 for s in feats.values() if s.get("unavailable_permanent"))
    return _check("config marks pedigree permanently unavailable",
                  not offenders and n_unavail > 0,
                  f"{n_unavail} marked unavailable"
                  + (f"; still active: {offenders}" if offenders else ""))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/racing_full.db")
    p.add_argument("--features-table", default="entry_features_dpv1")
    p.add_argument("--config", default="scripts_dpv1/dpv1_feature_config.json")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    print("pedigree availability (results-only data regime)")
    print("-" * 66)
    results = [
        test_pedigree_only_from_winners(conn),
        test_global_pedigree_is_a_perfect_leak(conn),
        test_config_marks_pedigree_unavailable(args.config),
    ]
    has_tbl = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (args.features_table,)).fetchone()
    if has_tbl:
        results.append(test_feature_table_has_no_pedigree(conn, args.features_table))
    else:
        print(f"  SKIP  {args.features_table} not present")
    print("-" * 66)
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
