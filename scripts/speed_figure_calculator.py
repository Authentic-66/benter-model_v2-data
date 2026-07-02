"""Compute a Beyer-like speed figure for every horse in the DB.

Methodology
-----------
1. Parse the race-level `final_time` into seconds.
2. For each (surface, distance_yards, track_condition) cell, compute a
   Bayesian-shrunk **par time**: the median final time expected for an
   average field in that cell.
3. Per horse, estimate that horse's individual time from the race's final
   time plus `beaten_lengths * SEC_PER_LENGTH`.
4. `raw_speed = par_time - horse_time`  (positive = faster than par).
5. Rescale to a 0-120 Beyer-ish scale: `sf = 80 + raw_speed * SEC_TO_POINTS`.

Design notes
~~~~~~~~~~~~
* Par time uses two-level shrinkage:
    - Fine cell: (surface, distance_yards, track_condition)
    - Fallback: (surface, distance_yards)   [ignores condition]
  A cell with fewer than N_MIN races shrinks strongly toward the fallback.
* Beaten lengths from tail-end finishers are often NULL in Equibase charts
  (~13% missing). For those horses we leave speed_figure NULL rather than
  impute — no fake data.
* `SEC_PER_LENGTH` and `SEC_TO_POINTS` are calibrated to match Beyer's
  rough conventions (1 length ≈ 1/5 sec at 40 mph; 5 points per second).
  These are v1 defaults; refinement is Phase 3F+.
* Muddy/Sloppy tracks slow horses but the par is computed on those tracks
  too, so the shrinkage handles it — a horse running fast in slop still
  gets a high figure relative to slop par.

Output
~~~~~~
Writes a `computed_speed_figures` table:
    entry_id (PK)     — FK to entries.id
    race_id           — for convenience
    horse_time_sec    — estimated horse time in seconds (nullable)
    par_time_sec      — shrunk par for the cell
    raw_diff          — par_time_sec - horse_time_sec
    speed_figure      — Beyer-ish scale
    par_cell_used     — 'fine' or 'coarse' (which shrinkage tier was used)
    n_cell            — sample size supporting the par estimate

Usage
-----
    python speed_figure_calculator.py compute --db scripts/gp_full.db
    python speed_figure_calculator.py summarize --db scripts/gp_full.db
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bayesian_shrinkage import shrink_rate  # noqa: E402


log = logging.getLogger("speed_figure")

# Calibration constants (v1 defaults — Phase 3D can retune)
SEC_PER_LENGTH = 0.20      # seconds per length at wire speed
SEC_TO_POINTS = 5.0        # scaled points per second faster/slower than par
SF_BASE = 80.0             # arithmetic center of the scale

# Two-tier par lookup. We DO NOT shrink across distances — a 4.5f par cannot
# be estimated from 8f data. If the coarse (surface, distance) cell itself
# has too few races, the par is NULL for that cell and the speed figure will
# be NULL for those entries.
N_MIN_FINE = 30            # ≥30 races to trust (surf, dist, cond) alone
N_MIN_COARSE = 15          # ≥15 races in (surf, dist) to use it as par


def parse_final_time_seconds(text) -> float | None:
    """`1:05.90` → 65.9;  `52.17` → 52.17;  `2:02.95` → 122.95.

    Accepts str, None, or NaN (pandas often produces NaN for missing).
    """
    if text is None or not isinstance(text, str):
        return None
    m = re.match(r"^(?:(\d+):)?(\d+\.\d+|\d+)$", text.strip())
    if not m:
        return None
    mins = int(m.group(1) or 0)
    secs = float(m.group(2))
    return mins * 60 + secs


def create_speed_figures_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS computed_speed_figures (
            entry_id        INTEGER PRIMARY KEY,
            race_id         INTEGER NOT NULL,
            horse_time_sec  REAL,
            par_time_sec    REAL,
            raw_diff        REAL,
            speed_figure    REAL,
            par_cell_used   TEXT,
            n_cell          INTEGER,
            FOREIGN KEY (entry_id) REFERENCES entries(id),
            FOREIGN KEY (race_id) REFERENCES races(id)
        );
        CREATE INDEX IF NOT EXISTS idx_csf_race ON computed_speed_figures(race_id);
        """
    )
    conn.commit()


def load_race_times(conn: sqlite3.Connection) -> pd.DataFrame:
    """Pull every race's raw final time + descriptors into a DataFrame."""
    df = pd.read_sql_query(
        """
        SELECT id AS race_id, distance_yards, surface, track_condition, final_time
        FROM races
        WHERE distance_yards IS NOT NULL AND surface IS NOT NULL
        """,
        conn,
    )
    df["final_time_sec"] = df["final_time"].map(parse_final_time_seconds)
    return df


def compute_par_times(race_df: pd.DataFrame) -> pd.DataFrame:
    """Compute par times per (surface, distance_yards, track_condition).

    Two-tier fallback within the same distance (no cross-distance mixing):
        - fine  (surf, dist, cond) — if ≥ N_MIN_FINE races, use it
        - coarse (surf, dist)      — if fine is thin but coarse ≥ N_MIN_COARSE, use it
        - else par_time_sec = NULL (speed figure will be NULL for these entries)

    Distance is never averaged across — a 4.5f par cannot be inferred from
    6f data because the underlying physics is different.

    Returns a DataFrame keyed by (surface, distance_yards, track_condition)
    with columns: par_time_sec, par_cell_used, n_cell.
    """
    df = race_df.dropna(subset=["final_time_sec"]).copy()

    fine = (
        df.groupby(["surface", "distance_yards", "track_condition"], dropna=False)
          ["final_time_sec"]
          .agg(fine_median="median", fine_n="count")
          .reset_index()
    )
    coarse = (
        df.groupby(["surface", "distance_yards"], dropna=False)
          ["final_time_sec"]
          .agg(coarse_median="median", coarse_n="count")
          .reset_index()
    )
    par = fine.merge(coarse, on=["surface", "distance_yards"], how="left")

    # Tier selection
    use_fine = par["fine_n"] >= N_MIN_FINE
    use_coarse = (~use_fine) & (par["coarse_n"] >= N_MIN_COARSE)

    par["par_time_sec"] = np.where(
        use_fine, par["fine_median"],
        np.where(use_coarse, par["coarse_median"], np.nan),
    )
    par["par_cell_used"] = np.where(
        use_fine, "fine",
        np.where(use_coarse, "coarse", "insufficient"),
    )
    par["n_cell"] = np.where(use_fine, par["fine_n"], par["coarse_n"]).astype(int)
    return par[[
        "surface", "distance_yards", "track_condition",
        "par_time_sec", "par_cell_used", "n_cell",
    ]]


def load_entries_for_sf(conn: sqlite3.Connection) -> pd.DataFrame:
    """Everything we need to score each entry."""
    return pd.read_sql_query(
        """
        SELECT e.id AS entry_id, e.race_id, e.beaten_lengths, e.finish_pos,
               r.distance_yards, r.surface, r.track_condition, r.final_time
        FROM entries e
        JOIN races r ON r.id = e.race_id
        """,
        conn,
    )


def compute_entry_speed_figures(
    entries_df: pd.DataFrame, par_df: pd.DataFrame
) -> pd.DataFrame:
    """Attach par + horse_time + speed_figure to each entry."""
    df = entries_df.copy()
    df["race_time_sec"] = df["final_time"].map(parse_final_time_seconds)
    # Horse's estimated finishing time. Winners have beaten_lengths=0 exactly.
    # Non-winners with NULL beaten_lengths remain NULL (chart didn't report a
    # margin, so we can't estimate a horse time honestly).
    df["horse_time_sec"] = df["race_time_sec"] + df["beaten_lengths"] * SEC_PER_LENGTH

    df = df.merge(
        par_df,
        on=["surface", "distance_yards", "track_condition"],
        how="left",
    )
    df["raw_diff"] = df["par_time_sec"] - df["horse_time_sec"]
    df["speed_figure"] = SF_BASE + df["raw_diff"] * SEC_TO_POINTS
    # Clip to reasonable Beyer-ish range
    df["speed_figure"] = df["speed_figure"].clip(lower=0, upper=140)
    return df


def write_results(conn: sqlite3.Connection, sf_df: pd.DataFrame) -> int:
    create_speed_figures_table(conn)
    conn.execute("DELETE FROM computed_speed_figures")
    conn.commit()

    out = sf_df[[
        "entry_id", "race_id", "horse_time_sec", "par_time_sec",
        "raw_diff", "speed_figure", "par_cell_used", "n_cell",
    ]].copy()
    out = out.where(pd.notnull(out), None)

    rows = 0
    batch: list[tuple] = []
    BATCH = 5000
    for row in out.itertuples(index=False, name=None):
        batch.append(row)
        if len(batch) >= BATCH:
            conn.executemany(
                """
                INSERT INTO computed_speed_figures
                  (entry_id, race_id, horse_time_sec, par_time_sec,
                   raw_diff, speed_figure, par_cell_used, n_cell)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            rows += len(batch)
            batch = []
    if batch:
        conn.executemany(
            """
            INSERT INTO computed_speed_figures
              (entry_id, race_id, horse_time_sec, par_time_sec,
               raw_diff, speed_figure, par_cell_used, n_cell)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        rows += len(batch)
    conn.commit()
    return rows


def cmd_compute(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        log.error("DB not found: %s", db_path)
        return 1
    conn = sqlite3.connect(db_path)
    log.info("Loading race times…")
    race_df = load_race_times(conn)
    log.info("  %d races with times", len(race_df))
    log.info("Computing par times…")
    par_df = compute_par_times(race_df)
    log.info("  %d (surf, dist, cond) cells", len(par_df))
    log.info("Loading entries…")
    entries_df = load_entries_for_sf(conn)
    log.info("  %d entries", len(entries_df))
    log.info("Attaching speed figures…")
    sf_df = compute_entry_speed_figures(entries_df, par_df)
    valid = sf_df["speed_figure"].notna().sum()
    log.info("  %d entries with a valid speed_figure (%.1f%%)",
             valid, 100.0 * valid / len(sf_df))
    log.info("Writing to computed_speed_figures…")
    n = write_results(conn, sf_df)
    log.info("Wrote %d rows.", n)
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT count(*) FROM computed_speed_figures").fetchone()[0]
    print(f"Total speed-figure rows: {n}")
    df = pd.read_sql_query(
        "SELECT speed_figure, par_cell_used FROM computed_speed_figures "
        "WHERE speed_figure IS NOT NULL", conn,
    )
    print(f"With non-null figure: {len(df)}")
    print(f"Overall distribution:")
    print(df["speed_figure"].describe().round(2).to_string())
    print(f"\nBy shrinkage tier used:")
    print(df.groupby("par_cell_used")["speed_figure"].describe().round(2))

    # Top / bottom 5
    print(f"\nTop 5 figures observed:")
    top = pd.read_sql_query(
        """
        SELECT rd.race_date, r.race_num, h.name, csf.speed_figure, csf.horse_time_sec,
               csf.par_time_sec, r.surface, r.distance_yards, r.track_condition
        FROM computed_speed_figures csf
        JOIN entries e ON e.id = csf.entry_id
        JOIN horses h ON h.id = e.horse_id
        JOIN races r ON r.id = csf.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE csf.speed_figure IS NOT NULL
        ORDER BY csf.speed_figure DESC LIMIT 5
        """,
        conn,
    )
    print(top.to_string(index=False))
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_c = sub.add_parser("compute")
    p_c.add_argument("--db", default="scripts/gp_full.db")
    p_c.set_defaults(func=cmd_compute)
    p_s = sub.add_parser("summarize")
    p_s.add_argument("--db", default="scripts/gp_full.db")
    p_s.set_defaults(func=cmd_summarize)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
