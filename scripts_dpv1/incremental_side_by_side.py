"""Incremental build side by side with the nightly full build (7b-1 trial).

    python scripts_dpv1/incremental_side_by_side.py run --step card --track DED --date 2026-11-12 --pp-file "Delta Downs/ded-pps-files/ded1112y.pdf"
    python scripts_dpv1/incremental_side_by_side.py status

Run it right after a full build of record (``feature_builder_dpv1.py build``,
card or chart night) and after ``card_picks --save``. It never touches the
table of record (``entry_features_dpv1``). Write-up and pass rule:
``tracking/incremental_build_2026-11-08.md``, "Side-by-side period".

``run``:

1. Checks the full build is current: its recorded inputs equal the DB's
   (``plan`` on the main table = "no input changed"). Otherwise it refuses:
   run the full build first.
2. ``feature_incremental.update`` into the side table
   ``entry_features_dpv1_inc``. With no side state yet it seeds it with a full
   build (``seed``); when ``plan`` falls back, a full build with the reason
   (``fallback``).
3. Compares side and main cell for cell: same ids, every column, the stored
   SQLite type of every cell, and a table hash.
4. With ``--pp-file``: runs ``card_picks`` for ``--date`` from each table on
   a scratch copy of the DB (logs to scratch, never the prediction log) and
   compares every logged field per horse except run time, prediction id and
   picks file.
5. Appends one row to ``tracking/incremental_side_by_side.csv`` and prints
   the streak.

**Pass rule (Doug, 2026-11-11).** 14 clean nights in a row. A night is clean
when every row that night was an incremental update with 0 differing cells,
0 type or id differences, equal hashes and 0 pick differences. Any difference
resets the count to 0 and is reported (exit 1). Seeds and fallbacks are
logged but neither count nor reset (unless they differ). The nightly full
build is the full-rebuild check; ``status`` warns when no comparison has run
for 7 days (then run a full build and ``run --step weekly``).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date as Date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))

import feature_incremental as fi  # noqa: E402
from dpv1_common import DEFAULT_CONFIG, DEFAULT_DB, FEATURES_TABLE  # noqa: E402

SIDE_TABLE = "entry_features_dpv1_inc"
LOG = DPV1_DIR / "tracking" / "incremental_side_by_side.csv"
PASS_NIGHTS = 14
FIELDS = ["run_at", "night", "track", "step", "side_mode", "reason",
          "seeds_new", "seeds_changed", "seeds_removed", "attr_only",
          "dirty_rows", "closure_rows", "side_seconds", "rows_main",
          "rows_side", "ids_only_main", "ids_only_side", "differing_cells",
          "type_diffs", "hash_equal", "picks_rows", "picks_diffs", "result",
          "streak", "detail"]
SKIP_PICK_FIELDS = {"generated_at", "prediction_id", "picks_file"}


# --------------------------------------------------------------------------
# table comparison (same rules as tracking/.../table_diff.py)
# --------------------------------------------------------------------------

def _table_hash(df: pd.DataFrame) -> str:
    cols = sorted(df.columns)
    h = hashlib.sha256()
    for row in df[cols].itertuples(index=False, name=None):
        h.update(repr(tuple(None if (isinstance(v, float) and np.isnan(v)) else v
                            for v in row)).encode())
    return h.hexdigest()


def compare_tables(db, a: str = FEATURES_TABLE, b: str = SIDE_TABLE) -> dict:
    """Cell-by-cell: NULL = NULL, floats exact, stored type per cell, hash."""
    c = sqlite3.connect(f"file:{Path(db).resolve().as_posix()}?mode=ro", uri=True)
    try:
        A = pd.read_sql_query(f"SELECT * FROM {a}", c).sort_values("entry_id").reset_index(drop=True)
        B = pd.read_sql_query(f"SELECT * FROM {b}", c).sort_values("entry_id").reset_index(drop=True)

        def types(t):
            cs = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            return pd.read_sql_query(
                "SELECT entry_id, " + ", ".join(f'typeof("{k}") AS "{k}"'
                                                for k in cs if k != "entry_id")
                + f" FROM {t}", c).set_index("entry_id")
        TA, TB = types(a), types(b)
    finally:
        c.close()
    out = {"rows_main": len(A), "rows_side": len(B),
           "cols_only_main": sorted(set(A.columns) - set(B.columns)),
           "cols_only_side": sorted(set(B.columns) - set(A.columns))}
    ida, idb = set(A.entry_id), set(B.entry_id)
    out["ids_only_main"], out["ids_only_side"] = len(ida - idb), len(idb - ida)
    common = sorted(ida & idb)
    A2, B2 = A.set_index("entry_id").loc[common], B.set_index("entry_id").loc[common]
    diff = {}
    for col in sorted(set(A2.columns) & set(B2.columns)):
        x, y = A2[col], B2[col]
        nx, ny = x.isna().to_numpy(), y.isna().to_numpy()
        vx, vy = x.to_numpy(dtype=object), y.to_numpy(dtype=object)
        neq = (nx != ny) | (~nx & ~ny & (vx != vy))
        if neq.any():
            diff[col] = int(neq.sum())
    TA, TB = TA.loc[common], TB.loc[common]
    tdiff = {k: int((TA[k] != TB[k]).sum()) for k in TA.columns
             if k in TB.columns and (TA[k] != TB[k]).any()}
    out["differing_cells_by_column"] = diff
    out["differing_cells"] = int(sum(diff.values()))
    out["type_diffs_by_column"] = tdiff
    out["type_diffs"] = int(sum(tdiff.values()))
    out["hash_equal"] = _table_hash(A) == _table_hash(B)
    out["identical"] = (not diff and not tdiff and not out["ids_only_main"]
                        and not out["ids_only_side"] and not out["cols_only_main"]
                        and not out["cols_only_side"] and out["hash_equal"])
    return out


# --------------------------------------------------------------------------
# picks comparison (scratch copy; the prediction log is never written)
# --------------------------------------------------------------------------

def _picks(db_copy: Path, track: str, day: str, pp_file: str, out: Path,
           tag: str) -> list[dict]:
    log_file = out / f"picks_{tag}.jsonl"
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               BENTER_NAME_MATCH_LOG=str(out / "name_matches.jsonl"))
    res = subprocess.run(
        [sys.executable, str(DPV1_DIR / "card_picks.py"), "--track", track,
         "--date", day, "--pp-file", str(Path(pp_file).resolve()), "--db",
         str(db_copy), "--save", "--log-file", str(log_file), "--outdir",
         str(out / "picks")], cwd=str(DPV1_DIR), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0 or not log_file.exists():
        raise RuntimeError(f"card_picks ({tag}) failed, rc={res.returncode}: "
                           f"{(res.stderr or res.stdout)[-800:]}")
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def compare_picks(db, track: str, day: str, pp_file: str) -> dict:
    """card_picks from the main table and from the side table, on a copy."""
    db = Path(db).resolve()
    work = Path(tempfile.mkdtemp(prefix="sbs_", dir=str(db.parent)))
    try:
        copy = work / "picks_copy.db"
        shutil.copy2(db, copy)
        a = _picks(copy, track, day, pp_file, work, "main")
        c = sqlite3.connect(str(copy))
        c.execute(f"DROP TABLE {FEATURES_TABLE}")
        c.execute(f"ALTER TABLE {SIDE_TABLE} RENAME TO {FEATURES_TABLE}")
        c.commit()
        c.close()
        b = _picks(copy, track, day, pp_file, work, "side")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    key = lambda r: (r["race_num"], str(r["pgm"]))  # noqa: E731
    mb = {key(r): r for r in b}
    n_diff, where = 0, []
    for r in a:
        o = mb.get(key(r))
        if o is None:
            n_diff += 1
            where.append(f"R{r['race_num']} #{r['pgm']} missing from side")
            continue
        for k in r:
            if k not in SKIP_PICK_FIELDS and r[k] != o.get(k):
                n_diff += 1
                where.append(f"R{r['race_num']} #{r['pgm']} {k}")
    extra = set(mb) - {key(r) for r in a}
    n_diff += len(extra)
    where += [f"R{k[0]} #{k[1]} only in side" for k in sorted(extra)]
    return {"picks_rows": len(a), "picks_rows_side": len(b),
            "picks_diffs": n_diff, "picks_where": where[:20]}


# --------------------------------------------------------------------------
# log and streak
# --------------------------------------------------------------------------

def read_log(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def streak(rows: list[dict]) -> int:
    """Clean incremental nights in a row (module docstring)."""
    nights: dict[str, list[str]] = {}
    for r in rows:
        nights.setdefault(r["night"], []).append(r["result"])
    n = 0
    for night in sorted(nights):
        res = nights[night]
        if "DIFF" in res:
            n = 0
        elif "clean" in res:
            n += 1
    return n


def append_row(row: dict, path: Path = LOG) -> None:
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def run(db, step: str, track: str, day: str, pp_file: str | None,
        log_path: Path = LOG, config=DEFAULT_CONFIG, reseed: bool = False,
        night: str | None = None) -> int:
    db = Path(db)
    conn = sqlite3.connect(str(db))
    try:
        main_plan = fi.plan(conn, config, FEATURES_TABLE)
    finally:
        conn.close()
    if main_plan["mode"] != "none":
        why = ("inputs changed since it was built" if main_plan["mode"] == "incremental"
               else main_plan["reason"])
        raise SystemExit(f"REFUSED: the full build of record is not current "
                         f"({why}). Run feature_builder_dpv1.py build first; "
                         f"nothing was logged.")

    if reseed:
        conn = sqlite3.connect(str(db))
        conn.execute(f"DROP TABLE IF EXISTS {SIDE_TABLE}")
        conn.execute(f"DELETE FROM {fi.HASH_TABLE} WHERE table_name = ?", (SIDE_TABLE,))
        conn.commit()
        conn.close()

    t0 = time.perf_counter()
    res = fi.update(db, config, SIDE_TABLE, allow_fallback=True)
    side_s = round(time.perf_counter() - t0, 1)
    mode = res["mode"]
    if mode == "full":
        kind = "seed" if ("no recorded build state" in res["reason"] or reseed) else "fallback"
    else:
        kind = mode                       # incremental / none
    cmp_ = compare_tables(db)
    picks = compare_picks(db, track, day, pp_file) if pp_file else {}

    same = cmp_["identical"] and picks.get("picks_diffs", 0) == 0
    if not same:
        result = "DIFF"
    elif kind == "incremental":
        result = "clean"
    else:
        result = kind                     # seed / fallback / none: logged, not counted
    detail = {}
    if cmp_["differing_cells_by_column"]:
        detail["cells"] = cmp_["differing_cells_by_column"]
    if cmp_["type_diffs_by_column"]:
        detail["types"] = cmp_["type_diffs_by_column"]
    if picks.get("picks_where"):
        detail["picks"] = picks["picks_where"]
    row = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "night": night or day, "track": track, "step": step, "side_mode": mode,
           "reason": res.get("reason", ""),
           **{k: res.get(k, "") for k in ("seeds_new", "seeds_changed",
                                          "seeds_removed", "attr_only",
                                          "dirty_rows", "closure_rows")},
           "side_seconds": side_s,
           **{k: cmp_[k] for k in ("rows_main", "rows_side", "ids_only_main",
                                   "ids_only_side", "differing_cells",
                                   "type_diffs", "hash_equal")},
           "picks_rows": picks.get("picks_rows", ""),
           "picks_diffs": picks.get("picks_diffs", ""),
           "result": result, "detail": json.dumps(detail) if detail else ""}
    rows = read_log(log_path) + [row]
    row["streak"] = streak(rows)
    append_row(row, log_path)

    print(f"side table: {mode} ({res.get('reason', '')}), {side_s} s; "
          f"dirty {res.get('dirty_rows', '-')}, closure {res.get('closure_rows', '-')}")
    print(f"main vs side: {cmp_['rows_main']} / {cmp_['rows_side']} rows, "
          f"{cmp_['differing_cells']} differing cells, {cmp_['type_diffs']} type "
          f"diffs, ids only main/side {cmp_['ids_only_main']}/{cmp_['ids_only_side']}, "
          f"hash equal {cmp_['hash_equal']}")
    if picks:
        print(f"picks: {picks['picks_rows']} rows, {picks['picks_diffs']} diffs")
    print(f"result: {result}; streak {row['streak']} of {PASS_NIGHTS} clean nights "
          f"-> {log_path.name}")
    if result == "DIFF":
        print("DIFFERENCE: the count is reset to 0. Report it to Doug; detail: "
              + row["detail"])
        return 1
    if row["streak"] >= PASS_NIGHTS:
        print(f"PASSED: {PASS_NIGHTS} clean nights in a row. Doug decides "
              f"whether incremental becomes the build of record.")
    return 0


def status(log_path: Path = LOG) -> int:
    rows = read_log(log_path)
    if not rows:
        print("no side-by-side runs logged yet")
        return 0
    s = streak(rows)
    last = rows[-1]
    print(f"{len(rows)} runs; streak {s} of {PASS_NIGHTS} clean nights; last "
          f"{last['night']} {last['step']}: {last['result']}")
    diffs = [r for r in rows if r["result"] == "DIFF"]
    if diffs:
        print(f"last DIFF: {diffs[-1]['night']} {diffs[-1]['step']} {diffs[-1]['detail']}")
    days = (datetime.now(timezone.utc)
            - datetime.fromisoformat(last["run_at"])).days
    if days >= 7:
        print(f"WARNING: no full-vs-incremental comparison for {days} days. "
              f"Run a full build, then `run --step weekly`.")
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--step", required=True, choices=["card", "chart", "weekly"])
    r.add_argument("--track", required=True)
    r.add_argument("--date", required=True, help="the night (card date) YYYY-MM-DD")
    r.add_argument("--pp-file", help="PP PDF of --date: also compare card_picks")
    r.add_argument("--night", help="night to count this run under (default --date)")
    r.add_argument("--db", default=str(DEFAULT_DB))
    r.add_argument("--config", default=str(DEFAULT_CONFIG))
    r.add_argument("--log", default=str(LOG))
    r.add_argument("--reseed", action="store_true",
                   help="drop the side table and rebuild it in full (after a DIFF is fixed)")
    s = sub.add_parser("status")
    s.add_argument("--log", default=str(LOG))
    a = p.parse_args()
    if a.cmd == "status":
        return status(Path(a.log))
    Date.fromisoformat(a.date)
    return run(a.db, a.step, a.track.upper(), a.date, a.pp_file, Path(a.log),
               a.config, a.reseed, a.night)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
    sys.exit(_cli())
