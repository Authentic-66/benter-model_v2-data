"""Take the pre-race DB backup for a card, with checks.

    python scripts_dpv1/pre_race_backup.py --track DED --date 2026-11-09

Writes ``scripts/racing_full.db.<trk><MMDD>-run.bak``, the DB just before the
card's PP load, plus a manifest ``<backup>.json`` (sha256, integrity, the
previous card's backup and its sha256). Run it after the previous card's chart
is loaded and before ``load_pp_card.py load``.

It refuses (exit 1, nothing left behind) when:

* the DB already contains that night's card (entries or staged PP rows for
  the track and date): the backup would not be the pre-race state;
* the copy has the same sha256 as the previous card's backup: nothing changed
  since that card, which is how ``.ded1017-run.bak`` ended up a byte copy of
  ``.ded1016-run.bak`` (taken before the 10/16 chart was loaded);
* the backup already exists (pass ``--replace`` to retake it).

It warns, without refusing, when the previous card at the track still has no
results loaded (charts sometimes arrive late).

``load_pp_card.py load`` on the live DB checks the manifest: the backup must
exist, pass, and still match the live DB byte for byte.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "scripts" / "racing_full.db"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_path(db: Path, track: str, date: str) -> Path:
    mmdd = date[5:7] + date[8:10]
    return db.with_name(f"{db.name}.{track.lower()}{mmdd}-run.bak")


def manifest_path(bak: Path) -> Path:
    return bak.with_name(bak.name + ".json")


def card_rows(db: Path, track: str, date: str) -> dict:
    """Rows of that card already in ``db`` (read-only)."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        entries = conn.execute(
            "SELECT COUNT(*) FROM entries e JOIN races r ON r.id = e.race_id "
            "JOIN race_days rd ON rd.id = r.race_day_id "
            "JOIN tracks t ON t.id = rd.track_id "
            "WHERE t.code = ? AND rd.race_date = ?",
            (track.upper(), date)).fetchone()[0]
        try:
            pp = conn.execute(
                "SELECT COUNT(*) FROM pp_entries_raw WHERE track = ? "
                "AND race_date = ?", (track.upper(), date)).fetchone()[0]
        except sqlite3.OperationalError:
            pp = 0
    finally:
        conn.close()
    return {"entries": entries, "pp_entries_raw": pp}


def previous_card(db: Path, track: str, date: str) -> dict | None:
    """The track's latest card before ``date`` and whether its chart is in."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT rd.race_date, rd.source_pdf FROM race_days rd "
            "JOIN tracks t ON t.id = rd.track_id "
            "WHERE t.code = ? AND rd.race_date < ? "
            "ORDER BY rd.race_date DESC LIMIT 1",
            (track.upper(), date)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {"date": row[0],
            "results_loaded": not (row[1] or "").startswith("PP-SCHEDULED")}


def previous_backup(db: Path, track: str, target: Path) -> Path | None:
    """The most recent other ``<trk>MMDD-run.bak`` next to ``db``."""
    cands = [p for p in db.parent.glob(f"{db.name}.{track.lower()}????-run.bak")
             if p != target]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def recorded_sha(bak: Path) -> str:
    m = manifest_path(bak)
    if m.exists():
        try:
            return json.loads(m.read_text(encoding="utf-8"))["sha256"]
        except (KeyError, ValueError):
            pass
    return sha256(bak)


def take_backup(db: Path, track: str, date: str, replace: bool = False) -> dict:
    db = db.resolve()
    target = backup_path(db, track, date)
    fail = []

    if target.exists() and not replace:
        raise SystemExit(f"REFUSED: {target.name} already exists "
                         f"(--replace to retake it)")
    here = card_rows(db, track, date)
    if here["entries"] or here["pp_entries_raw"]:
        fail.append(f"the DB already contains {track} {date} "
                    f"({here['entries']} entries, {here['pp_entries_raw']} "
                    f"staged PP rows): a backup now is not the pre-race state")
    if fail:
        raise SystemExit("REFUSED: " + "; ".join(fail))

    partial = target.with_name(target.name + ".partial")
    shutil.copy2(db, partial)
    try:
        sha = sha256(partial)
        prev = previous_backup(db, track, target)
        prev_sha = recorded_sha(prev) if prev else None
        if prev_sha == sha:
            fail.append(f"the backup is byte-identical to the previous card's "
                        f"backup {prev.name} (sha256 {sha[:12]}...): nothing "
                        f"has changed since that card. Load the previous "
                        f"card's chart first")
        in_copy = card_rows(partial, track, date)
        if in_copy["entries"] or in_copy["pp_entries_raw"]:
            fail.append(f"the copy contains {track} {date} ({in_copy})")
        conn = sqlite3.connect(f"file:{partial.as_posix()}?mode=ro", uri=True)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        if integrity != "ok":
            fail.append(f"integrity_check: {integrity}")
        if fail:
            raise SystemExit("REFUSED: " + "; ".join(fail))
    except BaseException:
        os.remove(partial)
        raise

    if target.exists():
        os.remove(target)
    os.replace(partial, target)
    pc = previous_card(db, track, date)
    manifest = {
        "track": track.upper(), "card_date": date, "backup": target.name,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha, "integrity": integrity, "card_rows_in_backup": in_copy,
        "previous_backup": prev.name if prev else None,
        "previous_sha256": prev_sha, "previous_card": pc,
    }
    manifest_path(target).write_text(json.dumps(manifest, indent=1),
                                     encoding="utf-8")
    if pc and not pc["results_loaded"]:
        print(f"WARNING: the previous {track.upper()} card ({pc['date']}) has "
              f"no results loaded yet. If its chart is in, load it and "
              f"retake this backup with --replace.")
    return manifest


def verify_for_load(db: Path, track: str, date: str) -> str:
    """Called by ``load_pp_card load`` on the live DB. Raises SystemExit
    unless a passed backup exists for this card and the DB is still
    byte-identical to it (i.e. nothing was written since the backup)."""
    db = db.resolve()
    bak = backup_path(db, track, date)
    m = manifest_path(bak)
    if not bak.exists() or not m.exists():
        raise SystemExit(
            f"REFUSED: no pre-race backup for {track} {date}. Run "
            f"`python scripts_dpv1/pre_race_backup.py --track {track} "
            f"--date {date}` first (or pass --no-backup-check).")
    man = json.loads(m.read_text(encoding="utf-8"))
    live = sha256(db)
    if live != man["sha256"]:
        raise SystemExit(
            f"REFUSED: {db.name} has changed since {bak.name} was taken "
            f"(sha256 {live[:12]}... vs {man['sha256'][:12]}...). Retake it "
            f"with --replace (or pass --no-backup-check).")
    return bak.name


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--track", required=True)
    p.add_argument("--date", required=True, help="card date YYYY-MM-DD")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--replace", action="store_true")
    a = p.parse_args()
    man = take_backup(Path(a.db), a.track, a.date, a.replace)
    print(json.dumps(man, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
