"""Incremental feature build, first stage (PHASE_7_SCALING_PLAN 7b-1).

``feature_builder_dpv1.py build`` recomputes all ~326k entries every run.
This module recomputes only the rows a change can reach, by running the
**unchanged** ``build_features`` on the part of the history those rows read
(the "closure"), and writes just those rows back.

    python scripts_dpv1/feature_incremental.py update       # after any load
    python scripts_dpv1/feature_incremental.py plan         # dry run: what would change
    python scripts_dpv1/feature_incremental.py full         # full build + record

**State.** Each full build records an input fingerprint
(``feature_input_hashes``): per entry, a hash over every raw column the
builder reads (``load_raw`` and ``stretch_run``: entry, race, race day, horse,
dam, speed figure) plus the entry's keys and date. ``feature_build_log``
records each run and a hash of the feature code and config
(``build_version``). ``feature_builder_dpv1.py build`` records too.

**Update.**

1. *Seeds*: entries that are new, removed or changed since the recorded
   state (fingerprint diff, so hand edits are caught as well as loads).
2. *Propagate*: every entry on the same date or later (one helper,
   days since the jockey's / trainer's last win, reads earlier races of the
   same day) that shares a horse, jockey, trainer, sire, dam, damsire or track
   with a seed (old and new key values both), then whole races (same-race
   values). Repeated until nothing is added, since a race brought in this way
   can reach further entries.
3. *Closure* of the dirty rows (earlier dates and the same date): for
   jockey and trainer (and sire, dam, damsire when a pedigree feature is
   active), the rows with that key, plus those rows' horses' earlier entries
   (a trainer row's "off a layoff" flag needs its horse's previous race); for
   horse and track, the earlier *races* (whole) with that key; and the dirty
   rows' own races.
4. ``build_features`` on an in-memory copy of the closure; the dirty rows
   are kept and upserted; removed entries' rows are deleted; fingerprint and
   log updated.

**Full build instead** (and it says why) when: no recorded state; the
feature code, config or pandas/numpy version changed; the feature table's
rows don't match the recorded state; or the closure is over ``--max-frac``
(default 0.6) of the corpus, where it saves little.

Speed figures must come from frozen pars (``speed_par_config.json``),
otherwise every chart load moves old figures and the dirty set is the whole
corpus. Equivalence with a full build is tested, not assumed:
``tracking/incremental_build_2026-11-08.md``.

Not done here (7b-2): running totals, so the cost is still set by the
closure (tens of thousands of rows), not by the dirty count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(DPV1_DIR / "new_features"))

from dpv1_common import (  # noqa: E402
    DEFAULT_CONFIG, DEFAULT_DB, FEATURES_TABLE, SCRIPTS_DIR, SPEED_TABLE,
)

log = logging.getLogger("feature_incremental")

HASH_TABLE = "feature_input_hashes"
BUILD_LOG = "feature_build_log"
KEYS = ["horse_id", "jockey_id", "trainer_id", "sire_id", "dam_id",
        "damsire_id", "track_id"]
PEDIGREE_KEYS = ["sire_id", "dam_id", "damsire_id"]
RACE_KEYS = ["horse_id", "track_id"]
# Horse attributes. Only the horse-attribute features (config bucket 2) and
# the pedigree module read them; nothing keyed on jockey, trainer or track
# does. They are hashed separately (``ha``) so a chart that fills in a
# horse's pedigree does not count as a change to its races.
ATTR_COLS = ["sex", "color", "country", "foaled_date", "foaled_place",
             "sire_id", "dam_id", "damsire_id"]


def attr_features(cfg: dict) -> set:
    """Config features that read horse attributes or pedigree."""
    src = (DPV1_DIR / "new_features" / "pedigree_features.py").read_text(encoding="utf-8")
    return ({k for k, v in cfg["features"].items()
             if v.get("bucket") == 5 and f'"{k}"' in src}
            | {k for k, v in cfg["features"].items() if v.get("bucket") == 2})


def uses_attrs(cfg: dict) -> bool:
    return any(cfg["features"][k].get("active") for k in attr_features(cfg))


def keys_for(cfg: dict) -> tuple[list, list]:
    """(propagation keys, row-closure keys) for this config. Without an
    active attribute/pedigree feature, sire / dam / damsire reach nothing."""
    if uses_attrs(cfg):
        return KEYS, ["jockey_id", "trainer_id"] + PEDIGREE_KEYS
    return [k for k in KEYS if k not in PEDIGREE_KEYS], ["jockey_id", "trainer_id"]

# Every raw column feature_builder_dpv1.load_raw and stretch_run read.
_INPUT_SQL = f"""
    SELECT e.id AS entry_id, e.race_id, e.horse_id, e.trainer_id, e.jockey_id,
           e.program_num, e.post_pos, e.start_pos, e.weight_lbs, e.equipment,
           e.has_lasix, e.has_blinkers, e.finish_pos, e.beaten_lengths,
           e.final_odds, e.is_favorite, e.pace_calls_json, e.trip_comment,
           r.race_num, r.race_type, r.distance_yards, r.surface,
           r.track_condition, r.purse, r.claiming_price, r.field_size,
           r.temporary_rail_feet, r.temperature_f, r.call_labels,
           r.fractional_times, rd.race_date, rd.track_id,
           h.sex, h.color, h.country, h.foaled_date, h.foaled_place,
           h.sire_id, h.dam_id, dm.dam_sire_id AS damsire_id,
           sf.speed_figure, sf.par_time_sec
    FROM entries e
    JOIN races r      ON r.id = e.race_id
    JOIN race_days rd ON rd.id = r.race_day_id
    LEFT JOIN horses h ON h.id = e.horse_id
    LEFT JOIN dams dm  ON dm.id = h.dam_id
    LEFT JOIN {SPEED_TABLE} sf ON sf.entry_id = e.id
"""

# Files whose content defines the feature table.
_CODE_FILES = [
    DPV1_DIR / "feature_builder_dpv1.py", DPV1_DIR / "dpv1_common.py",
    DPV1_DIR / "dpv1_feature_schema.json",
    DPV1_DIR / "stretch_run.py", SCRIPTS_DIR / "feature_builder.py",
    SCRIPTS_DIR / "bayesian_shrinkage.py",
] + sorted((DPV1_DIR / "new_features").glob("*.py"))


def build_version(config_path) -> str:
    h = hashlib.sha256()
    for p in [Path(config_path)] + _CODE_FILES:
        h.update(p.name.encode())
        h.update(p.read_bytes() if p.exists() else b"<missing>")
    h.update(f"pandas {pd.__version__} numpy {np.__version__}".encode())
    return h.hexdigest()


_NULL_HASH = np.uint64(0x9E3779B97F4A7C15)


def _row_hashes(df: pd.DataFrame) -> np.ndarray:
    """Per-row hash that does not depend on the dtypes pandas infers.

    ``read_sql`` types a column from the values present: one NULL turns an
    integer column into float, and an all-NULL column is object. Hashing the
    frame directly would then change every row's hash when a card (NULL
    finish positions) is loaded. Here numbers hash as float64, everything
    else as its string, and NULL always as one constant.
    """
    h = np.zeros(len(df), dtype=np.uint64)
    for c in df.columns:
        s = df[c]
        null = s.isna().to_numpy()
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            v = pd.util.hash_array(s.astype("float64").fillna(0.0).to_numpy())
        else:
            v = pd.util.hash_array(s.astype(object).where(~null, "").map(str)
                                   .to_numpy(dtype=object))
        v = np.where(null, _NULL_HASH, v).astype(np.uint64)
        h = (h * np.uint64(1099511628211)) ^ v
    return h


def input_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """One row per entry: ``entry_id, race_id, race_date, KEYS..., h``."""
    df = pd.read_sql_query(_INPUT_SQL, conn)
    rest = [c for c in df.columns if c != "entry_id" and c not in ATTR_COLS]
    out = df[["entry_id", "race_id", "race_date"] + KEYS].copy()
    for k in ["race_id"] + KEYS:
        out[k] = out[k].astype("Int64")
    out["h"] = _row_hashes(df[rest]).view(np.int64)
    out["ha"] = _row_hashes(df[ATTR_COLS]).view(np.int64)
    return out.set_index("entry_id")


def _has_table_name(conn) -> bool:
    return "table_name" in {r[1] for r in conn.execute(f"PRAGMA table_info({HASH_TABLE})")}


def _ensure_tables(conn):
    """The fingerprint is kept per feature table (``table_name``), so a second
    table in the same DB (a side-by-side copy) keeps its own state when the
    live table is rebuilt. A fingerprint table in the old one-per-DB layout is
    dropped: it is state only, and with no state the next update does a full
    build."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (HASH_TABLE,)).fetchone() and not _has_table_name(conn):
        conn.execute(f"DROP TABLE {HASH_TABLE}")
    keycols = ", ".join(f"{k} INTEGER" for k in KEYS)
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS {HASH_TABLE} (
            table_name TEXT NOT NULL, entry_id INTEGER NOT NULL,
            h INTEGER NOT NULL, ha INTEGER NOT NULL,
            race_id INTEGER, race_date TEXT, {keycols},
            PRIMARY KEY (table_name, entry_id));
        CREATE TABLE IF NOT EXISTS {BUILD_LOG} (
            run_at TEXT NOT NULL, mode TEXT NOT NULL, build_version TEXT,
            table_name TEXT, n_rows INTEGER, n_recomputed INTEGER,
            closure_rows INTEGER, seeds INTEGER, seconds REAL, note TEXT);
    """)


_N_HASH_COLS = 6 + len(KEYS)


def _hash_rows(frame: pd.DataFrame, table: str):
    cols = ["h", "ha", "race_id", "race_date"] + KEYS
    sub = frame[cols].astype(object).where(frame[cols].notna(), None)
    return [(table, int(i)) + tuple(int(v) if isinstance(v, (np.integer,)) else v
                              for v in row)
            for i, row in zip(frame.index, sub.itertuples(index=False, name=None))]


def _log(conn, mode, config_path, table, n_recomputed, closure, seeds, sec, note):
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.execute(f"INSERT INTO {BUILD_LOG} VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (datetime.now(timezone.utc).isoformat(timespec="seconds"), mode,
                  build_version(config_path), table, n, n_recomputed, closure,
                  seeds, sec, note))


def record_full_build(conn, config_path, table=FEATURES_TABLE, seconds=None,
                      note=None) -> None:
    """Call right after a full build: store the inputs it was built on."""
    _ensure_tables(conn)
    frame = input_frame(conn)
    conn.execute(f"DELETE FROM {HASH_TABLE} WHERE table_name = ?", (table,))
    conn.executemany(f"INSERT INTO {HASH_TABLE} VALUES ({','.join('?' * _N_HASH_COLS)})",
                     _hash_rows(frame, table))
    _log(conn, "full", config_path, table, len(frame), None, None, seconds, note)
    conn.commit()


def _stored(conn, table=FEATURES_TABLE) -> pd.DataFrame | None:
    try:
        if not _has_table_name(conn):    # missing, or the old one-per-DB layout
            return None
        df = pd.read_sql_query(f"SELECT * FROM {HASH_TABLE} WHERE table_name = ?",
                               conn, params=(table,)).drop(columns="table_name")
    except Exception:  # noqa: BLE001 - no table yet
        return None
    if df.empty:
        return None
    for k in ["race_id"] + KEYS:
        df[k] = df[k].astype("Int64")
    return df.set_index("entry_id")


def _last_version(conn, table):
    try:
        r = conn.execute(f"SELECT build_version FROM {BUILD_LOG} WHERE table_name = ? "
                         f"ORDER BY rowid DESC LIMIT 1", (table,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return r[0] if r else None


def _later_than(frame: pd.DataFrame, events: pd.DataFrame, key: str) -> set:
    """Entries of ``frame`` dated on or after the earliest event with the same
    ``key`` value. Same day included: ``_prior_days_to_event`` (days since the
    jockey's / trainer's last win) walks rows in (entity, date, entry_id)
    order, so a win in an earlier race that day changes a later race's value."""
    ev = events[[key, "race_date"]].dropna()
    if ev.empty:
        return set()
    first = ev.groupby(key)["race_date"].min()
    m = frame[key].map(first)
    has = m.notna().to_numpy()
    if not has.any():
        return set()
    sub = frame.index[has]
    later = frame["race_date"].to_numpy()[has] >= m.to_numpy()[has]
    return set(sub[later])


def dirty_set(frame: pd.DataFrame, stored: pd.DataFrame, keys: list) -> dict:
    """Seeds and their propagation (module docstring, steps 1-2).

    ``h`` covers every input except the horse attributes, ``ha`` those. An
    entry whose ``h`` changed (or that is new or removed) is an entry seed;
    one where only ``ha`` changed is an attribute seed, handled by the caller.
    """
    cur_ids, old_ids = frame.index, stored.index
    new = cur_ids.difference(old_ids)
    removed = old_ids.difference(cur_ids)
    both = cur_ids.intersection(old_ids)
    h_diff = frame.loc[both, "h"].to_numpy() != stored.loc[both, "h"].to_numpy()
    ha_diff = frame.loc[both, "ha"].to_numpy() != stored.loc[both, "ha"].to_numpy()
    changed = both[h_diff]
    attr_only = both[~h_diff & ha_diff]
    cols = ["race_date"] + KEYS
    events = pd.concat([frame.loc[new.union(changed), cols],
                        stored.loc[removed.union(changed), cols]])
    removed_races = set(stored.loc[removed, "race_id"].dropna())
    dirty = set(new.union(changed))
    rounds = 0
    while dirty or removed_races:
        rounds += 1
        add = set()
        for k in keys:
            add |= _later_than(frame, events, k)
        races = set(frame.loc[sorted(dirty | add), "race_id"].dropna()) | removed_races
        add |= set(frame.index[frame["race_id"].isin(races).to_numpy()])
        fresh = add - dirty
        if not fresh:
            break
        dirty |= fresh
        events = frame.loc[sorted(fresh), cols]
    return {"new": len(new), "removed": list(map(int, removed)),
            "changed": len(changed), "attr_only": list(map(int, attr_only)),
            "dirty": sorted(int(i) for i in dirty), "rounds": rounds}


def closure_ids(frame: pd.DataFrame, targets, row_keys: list) -> list[int]:
    """Rows ``build_features`` needs to compute ``targets`` exactly (step 3)."""
    T = frame.loc[list(targets)]
    keep = set(T.index)
    races = set(T["race_id"].dropna())
    dates = frame["race_date"].to_numpy()
    for k in row_keys + RACE_KEYS:
        last = T[[k, "race_date"]].dropna().groupby(k)["race_date"].max()
        m = frame[k].map(last)
        has = m.notna().to_numpy()
        idx = frame.index[has][dates[has] <= m.to_numpy()[has]]   # same day too
        if k in RACE_KEYS:
            races |= set(frame.loc[idx, "race_id"].dropna())
        else:
            keep |= set(idx)
    # A connection or pedigree row's own situation flags come from its horse's
    # history (trainer win% off a layoff / dropping in class / first-time
    # starters, sire first-time-starter win%: previous race and career count),
    # so those horses' earlier entries come in too (rows).
    fam = frame.loc[sorted(keep - set(T.index))]
    last = fam[["horse_id", "race_date"]].dropna().groupby("horse_id")["race_date"].max()
    m = frame["horse_id"].map(last)
    has = m.notna().to_numpy()
    keep |= set(frame.index[has][dates[has] <= m.to_numpy()[has]])
    keep |= set(frame.index[frame["race_id"].isin(races).to_numpy()])
    return sorted(int(i) for i in keep)


def subset_db(src_path, ids) -> sqlite3.Connection:
    """In-memory DB holding only the closure entries (and their races, race
    days, horses, dams, speed figures; all tracks)."""
    m = sqlite3.connect(":memory:", uri=True)
    m.execute(f"ATTACH DATABASE 'file:{Path(src_path).resolve().as_posix()}?mode=ro' AS src")
    m.execute("CREATE TEMP TABLE _ids (id INTEGER PRIMARY KEY)")
    m.executemany("INSERT INTO _ids VALUES (?)", [(int(i),) for i in ids])

    def copy(table, where):
        sql = m.execute("SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone()[0]
        m.execute(sql)   # unqualified CREATE TABLE goes to main (memory)
        m.execute(f"INSERT INTO main.{table} SELECT * FROM src.{table} {where} ORDER BY rowid")

    copy("entries", "WHERE id IN (SELECT id FROM temp._ids)")
    copy("races", "WHERE id IN (SELECT race_id FROM main.entries)")
    copy("race_days", "WHERE id IN (SELECT race_day_id FROM main.races)")
    copy("tracks", "")
    copy("horses", "WHERE id IN (SELECT horse_id FROM main.entries)")
    copy("dams", "WHERE id IN (SELECT dam_id FROM main.horses)")
    copy(SPEED_TABLE, "WHERE entry_id IN (SELECT id FROM temp._ids)")
    m.commit()
    m.execute("DETACH DATABASE src")
    return m


def _full(conn, cfg, config_path, table, why, t0):
    import feature_builder_dpv1 as fb
    log.warning("FULL BUILD: %s", why)
    df = fb.build_features(conn, cfg)
    fb.write_table(conn, df, table)
    sec = round(time.perf_counter() - t0, 1)
    record_full_build(conn, config_path, table, sec, note=why)
    return {"mode": "full", "reason": why, "rows": len(df), "seconds": sec}


def plan(conn, config_path=DEFAULT_CONFIG, table=FEATURES_TABLE,
         max_frac=0.6) -> dict:
    """What ``update`` would do, without doing it."""
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    stored = _stored(conn, table)
    if stored is None or "ha" not in stored.columns or _last_version(conn, table) is None:
        return {"mode": "full", "reason": "no recorded build state in this DB"}
    if _last_version(conn, table) != build_version(config_path):
        return {"mode": "full", "reason": "feature code, config or library "
                                          "versions changed since the last recorded build"}
    frame = input_frame(conn)
    # The table must hold exactly the recorded rows, except rows of entries
    # that no longer exist (a chart load deletes a purged card's feature rows).
    have = {r[0] for r in conn.execute(f"SELECT entry_id FROM {table}")}
    rec = set(stored.index)
    odd = (have - rec) | ((rec - have) & set(frame.index))
    if odd:
        return {"mode": "full", "reason": f"{table} rows do not match the recorded "
                                          f"state ({len(odd)} ids)"}
    keys, row_keys = keys_for(cfg)
    d = dirty_set(frame, stored, keys)
    if d["attr_only"] and uses_attrs(cfg):
        return {"mode": "full", "reason": f"horse attributes / pedigree changed on "
                f"{len(d['attr_only'])} entries and an attribute or pedigree feature "
                f"is active", **_counts(d)}
    if not d["dirty"] and not d["removed"] and not d["attr_only"]:
        return {"mode": "none", "reason": "no input changed", **_counts(d)}
    clo = closure_ids(frame, d["dirty"], row_keys) if d["dirty"] else []
    if len(clo) > max_frac * len(frame):
        return {"mode": "full", "reason": f"closure {len(clo)} rows is over "
                f"{max_frac:.0%} of {len(frame)}", **_counts(d), "closure_rows": len(clo)}
    return {"mode": "incremental", "reason": "ok", **_counts(d),
            "closure_rows": len(clo), "_frame": frame, "_d": d, "_closure": clo}


def _counts(d):
    return {"seeds_new": d["new"], "seeds_changed": d["changed"],
            "seeds_removed": len(d["removed"]), "attr_only": len(d["attr_only"]),
            "dirty_rows": len(d["dirty"]),
            "rounds": d["rounds"]}


def update(db, config_path=DEFAULT_CONFIG, table=FEATURES_TABLE, max_frac=0.6,
           allow_fallback=True) -> dict:
    import feature_builder_dpv1 as fb
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db))
    t0 = time.perf_counter()
    p = plan(conn, config_path, table, max_frac)
    if p["mode"] == "full":
        if not allow_fallback:
            raise SystemExit(f"incremental update refused: {p['reason']}")
        res = _full(conn, cfg, config_path, table, p["reason"], t0)
        conn.close()
        return res
    if p["mode"] == "none":
        conn.close()
        return {k: v for k, v in p.items() if not k.startswith("_")}

    frame, d, clo = p.pop("_frame"), p.pop("_d"), p.pop("_closure")
    t1 = time.perf_counter()
    dirty = d["dirty"]
    out = pd.DataFrame()
    if dirty:
        sub = subset_db(db, clo)
        df = fb.build_features(sub, cfg)
        sub.close()
        out = df[df["entry_id"].isin(dirty)]
        if len(out) != len(dirty):
            raise RuntimeError(f"closure build returned {len(out)} of {len(dirty)} dirty rows")
    t2 = time.perf_counter()

    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if dirty and set(cols) != set(out.columns):
        raise RuntimeError(f"column mismatch: table-only {sorted(set(cols) - set(out.columns))}, "
                           f"build-only {sorted(set(out.columns) - set(cols))}")
    # Feature rows out: removed entries and the dirty rows (re-inserted).
    # Fingerprint rows out: those plus attribute-only seeds (re-recorded; with
    # no attribute feature active they change no feature value).
    rehash = sorted(set(dirty) | set(d["attr_only"]))
    conn.execute("DROP TABLE IF EXISTS temp._gone")
    conn.execute("CREATE TEMP TABLE _gone (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO temp._gone VALUES (?)",
                     [(i,) for i in sorted(set(d["removed"]) | set(dirty))])
    conn.execute(f"DELETE FROM {table} WHERE entry_id IN (SELECT id FROM temp._gone)")
    conn.executemany("INSERT OR IGNORE INTO temp._gone VALUES (?)", [(i,) for i in rehash])
    conn.execute(f"DELETE FROM {HASH_TABLE} WHERE table_name = ? AND "
                 f"entry_id IN (SELECT id FROM temp._gone)", (table,))
    if dirty:
        vals = out[cols].astype(object).where(out[cols].notna(), None)
        rows = [tuple(v.item() if hasattr(v, "item") else v for v in r)
                for r in vals.itertuples(index=False, name=None)]
        conn.executemany(f"INSERT INTO {table} ({','.join(cols)}) "
                         f"VALUES ({','.join('?' * len(cols))})", rows)
    if rehash:
        conn.executemany(f"INSERT INTO {HASH_TABLE} VALUES "
                         f"({','.join('?' * _N_HASH_COLS)})",
                         _hash_rows(frame.loc[rehash], table))
    sec = round(time.perf_counter() - t0, 1)
    seeds = p["seeds_new"] + p["seeds_changed"] + p["seeds_removed"] + p["attr_only"]
    _log(conn, "incremental", config_path, table, len(dirty), len(clo), seeds, sec, None)
    conn.commit()
    conn.close()
    return {**p, "mode": "incremental", "seconds": sec,
            "plan_s": round(t1 - t0, 1), "build_s": round(t2 - t1, 1),
            "write_s": round(time.perf_counter() - t2, 1)}


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("update", "plan", "full"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(DEFAULT_DB))
        s.add_argument("--config", default=str(DEFAULT_CONFIG))
        s.add_argument("--table", default=FEATURES_TABLE)
        s.add_argument("--max-frac", type=float, default=0.6)
        if name == "update":
            s.add_argument("--no-fallback", action="store_true",
                           help="refuse instead of running the full build")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if a.cmd == "update":
        res = update(a.db, a.config, a.table, a.max_frac, not a.no_fallback)
    elif a.cmd == "plan":
        conn = sqlite3.connect(a.db)
        res = {k: v for k, v in plan(conn, a.config, a.table, a.max_frac).items()
               if not k.startswith("_")}
        conn.close()
    else:
        import feature_builder_dpv1 as fb
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
        conn = sqlite3.connect(a.db)
        res = _full(conn, cfg, a.config, a.table, "requested", time.perf_counter())
        conn.close()
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
