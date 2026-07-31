"""Track-aware speed figures for the 3-track corpus.

Why this exists
---------------
``scripts/speed_figure_calculator.py`` computes par times per
``(surface, distance_yards, track_condition)`` — with no track in the key.
That was correct for a GP-only corpus. On the Phase 4A 3-track corpus it is
not: Charles Town is a 4.5-furlong bullring, Mountaineer a one-mile oval and
Gulfstream a mile-and-an-eighth. Pooling their final times into one par
would hand CT horses systematically low figures and GP horses high ones,
purely as a function of where they ran.

It also left ``computed_speed_figures`` populated for GP only (116,311 rows =
exactly the GP entry count), so ``last_race_speed_figure`` — one of Doug's
rank-1 features — was NULL for every CT and MNR entry.

This module recomputes with **track in the par key** and writes a separate
``computed_speed_figures_dpv1`` table. ``scripts/`` is left untouched, and
the v1 table stays available for reproducing Phase 3 results.

Methodology is otherwise unchanged from Phase 3C: par = median final time
for the cell, horse time = final time + beaten_lengths * SEC_PER_LENGTH,
figure = 80 + (par - horse_time) * 5. Distances are never pooled — a 4.5f
par cannot be inferred from 6f data.

Usage
-----
    python scripts_dpv1/speed_figures_dpv1.py compute
    python scripts_dpv1/speed_figures_dpv1.py summarize
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dpv1_common import DEFAULT_DB, SPEED_TABLE, SCRIPTS_DIR  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
from speed_figure_calculator import (  # noqa: E402
    SEC_PER_LENGTH, SEC_TO_POINTS, SF_BASE, parse_final_time_seconds,
)

log = logging.getLogger("speed_figures_dpv1")

# Thresholds are per (track, surface, distance) now, so the cells are ~3x
# thinner than the GP-only version. Lowered accordingly, with a third tier
# that pools conditions across the whole track+distance when a track simply
# has not raced a distance often enough under one condition.
N_MIN_FINE = 20     # (track, surf, dist, cond)
N_MIN_COARSE = 10   # (track, surf, dist)


def load_race_times(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT r.id AS race_id, rd.track_id, r.distance_yards, r.surface,
               r.track_condition, r.final_time
        FROM races r
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE r.distance_yards IS NOT NULL AND r.surface IS NOT NULL
        """,
        conn,
    )
    df["final_time_sec"] = df["final_time"].map(parse_final_time_seconds)
    return df


def compute_par_times(race_df: pd.DataFrame) -> pd.DataFrame:
    """Par per (track, surface, distance, condition) with a coarse fallback.

    Tier 1 (fine)   : (track, surface, distance, condition), n >= N_MIN_FINE
    Tier 2 (coarse) : (track, surface, distance),            n >= N_MIN_COARSE
    else            : par is NULL and the figure is NULL — never imputed.

    Track is never dropped from the key. A thin cell falls back to a broader
    condition set at the SAME track, never to another track.
    """
    df = race_df.dropna(subset=["final_time_sec"]).copy()

    fine = (
        df.groupby(["track_id", "surface", "distance_yards", "track_condition"],
                   dropna=False)["final_time_sec"]
          .agg(fine_median="median", fine_n="count")
          .reset_index()
    )
    coarse = (
        df.groupby(["track_id", "surface", "distance_yards"], dropna=False)
          ["final_time_sec"]
          .agg(coarse_median="median", coarse_n="count")
          .reset_index()
    )
    par = fine.merge(coarse, on=["track_id", "surface", "distance_yards"],
                     how="left")

    use_fine = par["fine_n"] >= N_MIN_FINE
    use_coarse = (~use_fine) & (par["coarse_n"] >= N_MIN_COARSE)

    par["par_time_sec"] = np.where(
        use_fine, par["fine_median"],
        np.where(use_coarse, par["coarse_median"], np.nan),
    )
    par["par_cell_used"] = np.where(
        use_fine, "fine", np.where(use_coarse, "coarse", "insufficient"))
    par["n_cell"] = np.where(use_fine, par["fine_n"], par["coarse_n"]).astype(int)
    return par[["track_id", "surface", "distance_yards", "track_condition",
                "par_time_sec", "par_cell_used", "n_cell"]]


def load_entries(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT e.id AS entry_id, e.race_id, e.beaten_lengths, e.finish_pos,
               rd.track_id, r.distance_yards, r.surface, r.track_condition,
               r.final_time
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        """,
        conn,
    )


def compute_entry_speed_figures(entries: pd.DataFrame,
                                par: pd.DataFrame) -> pd.DataFrame:
    df = entries.copy()
    df["race_time_sec"] = df["final_time"].map(parse_final_time_seconds)
    # Non-winners with a NULL margin get no horse time — the chart did not
    # report enough to estimate one honestly.
    df["horse_time_sec"] = (
        df["race_time_sec"] + df["beaten_lengths"] * SEC_PER_LENGTH
    )
    df = df.merge(
        par,
        on=["track_id", "surface", "distance_yards", "track_condition"],
        how="left",
    )
    df["raw_diff"] = df["par_time_sec"] - df["horse_time_sec"]
    df["speed_figure"] = (SF_BASE + df["raw_diff"] * SEC_TO_POINTS).clip(0, 140)
    return df


def write_results(conn: sqlite3.Connection, sf: pd.DataFrame) -> int:
    conn.executescript(
        f"""
        DROP TABLE IF EXISTS {SPEED_TABLE};
        CREATE TABLE {SPEED_TABLE} (
            entry_id        INTEGER PRIMARY KEY,
            race_id         INTEGER NOT NULL,
            track_id        INTEGER,
            horse_time_sec  REAL,
            par_time_sec    REAL,
            raw_diff        REAL,
            speed_figure    REAL,
            par_cell_used   TEXT,
            n_cell          INTEGER
        );
        """
    )
    cols = ["entry_id", "race_id", "track_id", "horse_time_sec", "par_time_sec",
            "raw_diff", "speed_figure", "par_cell_used", "n_cell"]
    out = sf[cols].astype(object).where(pd.notnull(sf[cols]), None)
    conn.executemany(
        f"INSERT INTO {SPEED_TABLE} ({','.join(cols)}) "
        f"VALUES ({','.join('?' * len(cols))})",
        list(out.itertuples(index=False, name=None)),
    )
    conn.execute(f"CREATE INDEX idx_{SPEED_TABLE}_race ON {SPEED_TABLE}(race_id)")
    conn.commit()
    return len(out)


def cmd_compute(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    log.info("Loading race times…")
    races = load_race_times(conn)
    log.info("  %d races with a distance + surface", len(races))
    par = compute_par_times(races)
    log.info("  %d (track, surf, dist, cond) par cells", len(par))
    for tier, n in par["par_cell_used"].value_counts().items():
        log.info("    %-12s %d cells", tier, n)
    entries = load_entries(conn)
    log.info("Scoring %d entries…", len(entries))
    sf = compute_entry_speed_figures(entries, par)
    valid = sf["speed_figure"].notna()
    log.info("  %d with a figure (%.1f%%)", valid.sum(),
             100.0 * valid.mean())
    for tid, grp in sf.groupby("track_id"):
        log.info("    track %s: %d/%d (%.1f%%)", tid,
                 grp["speed_figure"].notna().sum(), len(grp),
                 100.0 * grp["speed_figure"].notna().mean())
    n = write_results(conn, sf)
    log.info("Wrote %d rows to %s", n, SPEED_TABLE)
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    df = pd.read_sql_query(
        f"""
        SELECT t.code AS track, s.speed_figure, s.par_cell_used, s.n_cell
        FROM {SPEED_TABLE} s
        JOIN race_days rd ON rd.id = (
            SELECT race_day_id FROM races WHERE id = s.race_id)
        JOIN tracks t ON t.id = rd.track_id
        """,
        conn,
    )
    print(f"rows: {len(df)}   with figure: {df['speed_figure'].notna().sum()}")
    print("\nspeed_figure by track:")
    print(df.groupby("track")["speed_figure"].describe().round(2).to_string())
    print("\npar tier used by track:")
    print(pd.crosstab(df["track"], df["par_cell_used"]).to_string())
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("compute", cmd_compute), ("summarize", cmd_summarize)):
        sp = sub.add_parser(name)
        sp.add_argument("--db", default=str(DEFAULT_DB))
        sp.set_defaults(func=fn)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
