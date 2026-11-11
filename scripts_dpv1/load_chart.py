"""Load one result chart, replacing that day's pre-race card. Checked and loud.

    python scripts_dpv1/load_chart.py "Delta Downs/ded-results-2026/DED111126USA.pdf"

The nightly results load (RUNBOOK_card_night.md, section A). It loads with
``retrain_pipeline.load_charts`` (purge the day, then ingest), which is the
path every chart since 10/16 went through, and adds the guards the PP loader
has:

**Checked backup** (live DB by default; ``--require-backup`` for any DB,
``--no-backup-check`` to skip). Before writing, it copies the DB to
``<db>.pre-<trk><MMDD>res.bak``, checks the copy (sha256 equal to the DB,
``integrity_check``) and writes a manifest ``<backup>.json``. If that backup
already exists, it is used only if its manifest sha256 still equals the DB
(a rerun after a refusal); otherwise it refuses.

**Refuses, writing nothing (exit 1)**, when:

* the file does not parse as a chart, or the header date and the file-name
  date disagree;
* the chart's track is not in the DB (that would create a new track);
* the day already holds a **chart** (pass ``--reload`` to replace it, e.g. a
  re-download);
* the day holds a pre-race card with **more races** than the chart (a short
  or truncated chart);
* the load reports an error, or loads a different number of races or entries
  than the chart has.

There is no fallback: no other parser, no partial load, no merge.
``--dry-run`` parses and checks, and writes nothing (no backup either).

After it: ``score_predictions.py``, then the card build (speed figures and a
feature build rebuild what the purge removed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(REPO / "scripts"))

import db_loader  # noqa: E402
import retrain_pipeline as rp  # noqa: E402
from pre_race_backup import sha256  # noqa: E402

DEFAULT_DB = REPO / "scripts" / "racing_full.db"
DEFAULT_CACHE = REPO / "scripts" / "ct_cache"


def backup_path(db: Path, track: str, date: str) -> Path:
    return db.with_name(f"{db.name}.pre-{track.lower()}{date[5:7]}{date[8:10]}res.bak")


def refuse(msg: str) -> None:
    raise SystemExit(f"REFUSED: {msg}")


def checked_backup(db: Path, track: str, date: str, day: dict | None) -> str:
    """Take (or re-verify) the pre-load backup. Returns its file name."""
    db = db.resolve()
    bak = backup_path(db, track, date)
    man_path = bak.with_name(bak.name + ".json")
    live = sha256(db)
    if bak.exists():
        if not man_path.exists():
            refuse(f"{bak.name} exists with no manifest. Move it aside and run again.")
        man = json.loads(man_path.read_text(encoding="utf-8"))
        if man.get("sha256") != live:
            refuse(f"{bak.name} exists but {db.name} has changed since it was "
                   f"taken (sha256 {live[:12]}... vs {man.get('sha256', '')[:12]}...). "
                   f"Something was written after that backup; check before "
                   f"loading. Move the old backup aside to take a new one.")
        return f"{bak.name} (existing, still matches the DB)"
    partial = bak.with_name(bak.name + ".partial")
    shutil.copy2(db, partial)
    try:
        sha = sha256(partial)
        if sha != live:
            refuse(f"the copy's sha256 differs from {db.name}: the DB changed "
                   f"while it was being copied. Close other programs and retry.")
        conn = sqlite3.connect(f"file:{partial.as_posix()}?mode=ro", uri=True)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        if integrity != "ok":
            refuse(f"integrity_check on the copy: {integrity}")
    except BaseException:
        os.remove(partial)
        raise
    os.replace(partial, bak)
    man_path.write_text(json.dumps({
        "track": track, "chart_date": date, "backup": bak.name,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha, "integrity": integrity, "day_in_backup": day,
    }, indent=1), encoding="utf-8")
    return bak.name


def preflight(conn: sqlite3.Connection, parsed: dict, pdf: Path,
              reload: bool) -> tuple[str, str, dict | None, int]:
    """All refusals that need no write. Returns track, date, day, entries."""
    track, date = parsed.get("track_code"), parsed.get("race_date")
    if not track or not date or not parsed.get("race_count"):
        refuse(f"{pdf.name} is not a result chart (track={track!r}, "
               f"date={date!r}, races={parsed.get('race_count')})")
    fd, hd = parsed.get("filename_date"), parsed.get("header_date")
    if fd and hd and fd != hd:
        refuse(f"{pdf.name}: header date {hd} and file-name date {fd} disagree")
    if not conn.execute("SELECT 1 FROM tracks WHERE code = ?", (track,)).fetchone():
        refuse(f"track {track!r} is not in the DB; loading would create it. "
               f"Corpus loads of a new track go through db_loader pipeline.")
    n_entries = sum(len(r.get("entries") or []) for r in parsed["races"])
    day = db_loader.day_status(conn, track, date)
    if day and day["kind"] == "chart" and not reload:
        refuse(f"{track} {date} already holds a chart ({day['races']} races, "
               f"{day['entries']} entries, {day['source_pdf']!r}). Pass --reload "
               f"to replace it (e.g. a re-download).")
    if day and day["kind"] == "pre-race card" and day["races"] > parsed["race_count"]:
        refuse(f"the chart has {parsed['race_count']} races but the {track} {date} "
               f"card has {day['races']}: a short or truncated chart. Re-download it.")
    return track, date, day, n_entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--reload", action="store_true",
                    help="replace a day that already holds a chart")
    ap.add_argument("--require-backup", action="store_true")
    ap.add_argument("--no-backup-check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pdf = Path(a.pdf).resolve()
    db = Path(a.db)
    if not pdf.exists():
        refuse(f"no such file: {pdf}")
    if not db.exists():
        refuse(f"no such DB: {db}")
    parsed = rp.parse_chart(pdf, Path(a.cache))

    ro = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        track, date, day, n_entries = preflight(ro, parsed, pdf, a.reload)
    finally:
        ro.close()
    warns = [f"R{r['race_num']}: {w}" for r in parsed["races"]
             for w in (r.get("warnings") or [])]
    print(f"chart: {pdf.name}  {track} {date}  {parsed['race_count']} races, "
          f"{n_entries} entries")
    print("in DB: " + (f"{day['kind']}, {day['races']} races, {day['entries']} "
                       f"entries ({day['with_finish']} with a finish)"
                       if day else "nothing for that day"))
    for w in warns:
        print(f"  parser warning {w}")
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    if not a.no_backup_check and (a.require_backup
                                  or db.resolve() == DEFAULT_DB.resolve()):
        print(f"backup verified: {checked_backup(db, track, date, day)}")

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        res = rp.load_charts(conn, [pdf], Path(a.cache))
    finally:
        conn.close()
    t = res["totals"]
    print(json.dumps(t))
    bad = []
    if t["errors"] or t["not_charts"] or t["cards"] != 1:
        bad.append("the load reported an error (see the warning above); "
                   "that chart's transaction was rolled back")
    elif t["races"] != parsed["race_count"] or t["entries"] != n_entries:
        bad.append(f"loaded {t['races']} races / {t['entries']} entries, the "
                   f"chart has {parsed['race_count']} / {n_entries}")
    if bad:
        raise SystemExit("FAILED: " + "; ".join(bad))
    ro = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        after = db_loader.day_status(ro, track, date)
    finally:
        ro.close()
    print(f"loaded: {track} {date} {after['races']} races, {after['entries']} "
          f"entries, {after['with_finish']} with a finish"
          + (f"; replaced a {day['kind']} of {day['entries']} entries" if day else ""))
    if after["races"] != parsed["race_count"] or after["entries"] != n_entries:
        raise SystemExit(f"CHECK FAILED: the DB now has {after['races']} races / "
                         f"{after['entries']} entries for {track} {date}, the chart "
                         f"{parsed['race_count']} / {n_entries}. Restore the backup "
                         f"and ask.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
