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

Frozen pars (2026-11-08, interim)
---------------------------------
Pars used to be recomputed from the whole DB on every ``compute``, so loading
any chart could move old figures (the 2026-11-07 load moved 41,311).
``compute`` now reads the pars from ``par_times_dpv1`` under the version named
in ``speed_par_config.json`` and never recomputes them. The table holds the
raw cell statistics (median and count, fine and coarse), and the same
fine / coarse / insufficient rule is applied to them at lookup, so figures are
identical to a recompute on the data the pars were frozen from. A cell with a
timed race that did not exist at freeze time (a new distance or condition
label) falls back to its frozen coarse cell, else gets no figure. Refresh =
``freeze`` a new version and point the config at it (a model-input change;
record it in PHASE_6E). Point-in-time pars are item 2 of the 1.4 candidate
(PHASE_6D_ROADMAP).

Usage
-----
    python scripts_dpv1/speed_figures_dpv1.py compute            # frozen pars
    python scripts_dpv1/speed_figures_dpv1.py compute --recompute-pars
        # old behaviour: medians over the whole DB (e.g. rebuilding a backup
        # taken before pars were frozen, to reproduce its logged run)
    python scripts_dpv1/speed_figures_dpv1.py freeze --version pars-v1 --note "..."
    python scripts_dpv1/speed_figures_dpv1.py summarize
"""
from __future__ import annotations

import argparse
import json
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

PAR_TABLE = "par_times_dpv1"          # frozen cell statistics, per version
PAR_VERSIONS = "par_versions_dpv1"    # one row per frozen version
PAR_CONFIG = Path(__file__).resolve().parent / "speed_par_config.json"
FINE_KEY = ["track_id", "surface", "distance_yards", "track_condition"]
COARSE_KEY = ["track_id", "surface", "distance_yards"]


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
    fine, coarse = par_cell_stats(race_df)
    return resolve_par(fine, coarse)


def par_cell_stats(race_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Median final time and race count per fine and per coarse cell."""
    df = race_df.dropna(subset=["final_time_sec"]).copy()

    fine = (
        df.groupby(FINE_KEY, dropna=False)["final_time_sec"]
          .agg(fine_median="median", fine_n="count")
          .reset_index()
    )
    coarse = (
        df.groupby(COARSE_KEY, dropna=False)["final_time_sec"]
          .agg(coarse_median="median", coarse_n="count")
          .reset_index()
    )
    return fine, coarse


def resolve_par(fine: pd.DataFrame, coarse: pd.DataFrame) -> pd.DataFrame:
    """Apply the fine / coarse / insufficient rule to cell statistics."""
    par = fine.merge(coarse, on=COARSE_KEY, how="left")

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


# ---------------------------------------------------------------------------
# Frozen pars
# ---------------------------------------------------------------------------

def active_par_version(path: Path = PAR_CONFIG) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("par_version") or None
    except (OSError, ValueError):
        return None


def _ensure_par_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS {PAR_VERSIONS} (
            par_version    TEXT PRIMARY KEY,
            created_at     TEXT NOT NULL,   -- UTC
            n_races        INTEGER,         -- races with a final time used
            n_fine         INTEGER,
            n_coarse       INTEGER,
            last_race_date TEXT,            -- latest timed race in the data
            note           TEXT
        );
        CREATE TABLE IF NOT EXISTS {PAR_TABLE} (
            par_version     TEXT NOT NULL,
            level           TEXT NOT NULL,  -- 'fine' or 'coarse'
            track_id        INTEGER,
            surface         TEXT,
            distance_yards  INTEGER,
            track_condition TEXT,           -- NULL on coarse rows
            median_sec      REAL,
            n               INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_{PAR_TABLE}_version
            ON {PAR_TABLE}(par_version);
        """)


def freeze_pars(conn: sqlite3.Connection, version: str, note: str = "") -> dict:
    """Store the current whole-DB cell statistics as ``version``."""
    from datetime import datetime, timezone
    _ensure_par_tables(conn)
    if conn.execute(f"SELECT 1 FROM {PAR_VERSIONS} WHERE par_version = ?",
                    (version,)).fetchone():
        raise SystemExit(f"par version {version!r} already exists; "
                         f"versions are never overwritten")
    races = load_race_times(conn)
    fine, coarse = par_cell_stats(races)
    last = conn.execute(
        """SELECT MAX(rd.race_date) FROM races r
           JOIN race_days rd ON rd.id = r.race_day_id
           WHERE r.final_time IS NOT NULL""").fetchone()[0]
    rows = []
    for t in fine.itertuples(index=False):
        rows.append((version, "fine", int(t.track_id), t.surface,
                     int(t.distance_yards),
                     None if pd.isna(t.track_condition) else t.track_condition,
                     float(t.fine_median), int(t.fine_n)))
    for t in coarse.itertuples(index=False):
        rows.append((version, "coarse", int(t.track_id), t.surface,
                     int(t.distance_yards), None,
                     float(t.coarse_median), int(t.coarse_n)))
    conn.executemany(f"INSERT INTO {PAR_TABLE} VALUES (?,?,?,?,?,?,?,?)", rows)
    info = {"n_races": int(races["final_time_sec"].notna().sum()),
            "n_fine": len(fine), "n_coarse": len(coarse),
            "last_race_date": last}
    conn.execute(f"INSERT INTO {PAR_VERSIONS} VALUES (?,?,?,?,?,?,?)",
                 (version,
                  datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  info["n_races"], info["n_fine"], info["n_coarse"], last,
                  note))
    conn.commit()
    return info


def load_frozen_stats(conn: sqlite3.Connection,
                      version: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    have = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (PAR_VERSIONS,)).fetchone()
    if not have or not conn.execute(
            f"SELECT 1 FROM {PAR_VERSIONS} WHERE par_version = ?",
            (version,)).fetchone():
        raise SystemExit(
            f"par version {version!r} is not in this DB ({PAR_VERSIONS}). "
            f"Run 'speed_figures_dpv1.py freeze --version {version}', or pass "
            f"--recompute-pars for whole-DB medians (the old behaviour, e.g. "
            f"when rebuilding a backup taken before pars were frozen).")
    t = pd.read_sql_query(
        f"SELECT level, track_id, surface, distance_yards, track_condition, "
        f"median_sec, n FROM {PAR_TABLE} WHERE par_version = ?",
        conn, params=(version,))
    fine = (t[t.level == "fine"].drop(columns="level")
            .rename(columns={"median_sec": "fine_median", "n": "fine_n"})
            .reset_index(drop=True))
    coarse = (t[t.level == "coarse"].drop(columns=["level", "track_condition"])
              .rename(columns={"median_sec": "coarse_median", "n": "coarse_n"})
              .reset_index(drop=True))
    return fine, coarse


def frozen_par_times(fine: pd.DataFrame, coarse: pd.DataFrame,
                     race_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Par rows from frozen statistics. A cell that has a timed race now but
    was not in the frozen data gets a row with no fine statistics, so the
    usual rule sends it to its frozen coarse cell (or none). Returns
    ``(par, n_new_cells)``."""
    now = (race_df.dropna(subset=["final_time_sec"])[FINE_KEY]
           .drop_duplicates())
    m = now.merge(fine[FINE_KEY], on=FINE_KEY, how="left", indicator=True)
    new = m[m["_merge"] == "left_only"][FINE_KEY].copy()
    if len(new):
        new["fine_median"] = np.nan
        new["fine_n"] = 0
        fine = pd.concat([fine, new], ignore_index=True)
    return resolve_par(fine, coarse), len(new)


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
    if args.recompute_pars:
        par = compute_par_times(races)
        log.info("Pars: RECOMPUTED from the whole DB (--recompute-pars)")
    else:
        version = args.par_version or active_par_version()
        if not version:
            raise SystemExit(f"no par_version in {PAR_CONFIG.name}; pass "
                             f"--par-version or --recompute-pars")
        fine, coarse = load_frozen_stats(conn, version)
        par, n_new = frozen_par_times(fine, coarse, races)
        log.info("Pars: FROZEN version %s (%d timed cells not in it -> "
                 "coarse fallback)", version, n_new)
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


def cmd_freeze(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    info = freeze_pars(conn, args.version, args.note)
    log.info("Froze par version %s: %s", args.version, info)
    log.info("It is used once %s names it.", PAR_CONFIG.name)
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
    for name, fn in (("compute", cmd_compute), ("summarize", cmd_summarize),
                     ("freeze", cmd_freeze)):
        sp = sub.add_parser(name)
        sp.add_argument("--db", default=str(DEFAULT_DB))
        sp.set_defaults(func=fn)
        if name == "compute":
            sp.add_argument("--recompute-pars", action="store_true",
                            help="medians over the whole DB (old behaviour)")
            sp.add_argument("--par-version", default=None,
                            help=f"override {PAR_CONFIG.name}")
        if name == "freeze":
            sp.add_argument("--version", required=True)
            sp.add_argument("--note", default="")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
