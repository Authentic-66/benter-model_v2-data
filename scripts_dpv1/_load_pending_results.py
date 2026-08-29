"""One-off: replace three loaded-upcoming cards with their result charts.

This is the manual version of Piece 4 step 1, run once so Piece 2 has a scored
card to check against. It is not part of the toolkit -- Piece 4 will automate
it properly -- but the ordering it uses is the ordering Piece 4 has to use.

Why the delete is not optional
------------------------------
``entries`` carries ``UNIQUE(race_id, program_num)`` and ``db_loader`` inserts
with ``INSERT OR IGNORE``, while ``ingest_race_day``/``ingest_race`` return the
*existing* row when the day is already present. So loading a result chart onto
a day that was already loaded as an upcoming card silently drops every result
row and reports success: the NULL ``finish_pos`` entries survive untouched and
the race rows never get their chart fields. The card has to come out first.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import db_loader  # noqa: E402

DB = ROOT / "scripts" / "racing_full.db"
CACHE = ROOT / "scripts" / "ct_cache"

CARDS = [
    ("CT", "2026-08-28", ROOT / "CharlesTown/ct-results-2026/CT082826USA.pdf"),
    ("ELP", "2026-08-22", ROOT / "Ellis/elp-results-2026/ELP082226USA.pdf"),
    ("ELP", "2026-08-23", ROOT / "Ellis/elp-results-2026/ELP082326USA.pdf"),
]

# Derived, entry-grain tables. These are recomputed by the feature pipeline;
# leaving them behind would orphan them against deleted entry ids.
DERIVED = ["entry_features_dpv1", "entry_features_v1", "entry_pp_features",
           "computed_speed_figures", "computed_speed_figures_dpv1",
           "entry_v10_flags"]


def purge_card(conn: sqlite3.Connection, track: str, date: str) -> dict[str, int]:
    """Remove one loaded card entirely: derived rows, entries, races, day."""
    entry_ids = [r[0] for r in conn.execute(
        """SELECT e.id FROM entries e
           JOIN races r      ON r.id  = e.race_id
           JOIN race_days rd ON rd.id = r.race_day_id
           JOIN tracks t     ON t.id  = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]
    race_ids = [r[0] for r in conn.execute(
        """SELECT r.id FROM races r
           JOIN race_days rd ON rd.id = r.race_day_id
           JOIN tracks t     ON t.id  = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]
    day_ids = [r[0] for r in conn.execute(
        """SELECT rd.id FROM race_days rd
           JOIN tracks t ON t.id = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]

    counts = {"entries": len(entry_ids), "races": len(race_ids),
              "race_days": len(day_ids), "derived": 0, "exotics": 0}
    if entry_ids:
        q = ",".join("?" * len(entry_ids))
        for tbl in DERIVED:
            try:
                cur = conn.execute(
                    f"DELETE FROM {tbl} WHERE entry_id IN ({q})", entry_ids)
                counts["derived"] += cur.rowcount
            except sqlite3.OperationalError:
                pass  # table or column absent in this schema revision
        conn.execute(f"DELETE FROM entries WHERE id IN ({q})", entry_ids)
    if race_ids:
        q = ",".join("?" * len(race_ids))
        cur = conn.execute(
            f"DELETE FROM exotic_payouts WHERE race_id IN ({q})", race_ids)
        counts["exotics"] = cur.rowcount
        conn.execute(f"DELETE FROM races WHERE id IN ({q})", race_ids)
    if day_ids:
        q = ",".join("?" * len(day_ids))
        conn.execute(f"DELETE FROM race_days WHERE id IN ({q})", day_ids)
    return counts


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for track, date, pdf in CARDS:
            cached = CACHE / (pdf.stem + ".json")
            parsed = json.loads(cached.read_text(encoding="utf-8"))
            assert parsed["track_code"] == track and parsed["race_date"] == date, (
                f"{pdf.name} is {parsed['track_code']} {parsed['race_date']}, "
                f"expected {track} {date}")
            # Record the real repo-relative source path, not the cache path, so
            # parsed_files stays a usable provenance/resume index.
            parsed["source_pdf"] = str(pdf.relative_to(ROOT)).replace("/", "\\")

            with conn:
                purged = purge_card(conn, track, date)
                counts = db_loader.ingest_parsed_pdf(conn, parsed)
                warnings = [w for r in parsed["races"]
                            for w in (r.get("warnings") or [])]
                db_loader.record_parsed_file(
                    conn,
                    source_pdf=parsed["source_pdf"],
                    sha256=parsed.get("file_sha256", ""),
                    races_found=parsed.get("race_count", 0),
                    races_loaded=counts["races"],
                    success=True, error_message=None,
                    warnings_json=json.dumps(warnings) if warnings else None,
                )
            print(f"{track} {date}: purged {purged['entries']} entries / "
                  f"{purged['races']} races / {purged['derived']} derived rows"
                  f"  ->  loaded {counts['races']} races, "
                  f"{counts['entries']} entries, {counts['exotics']} exotics")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
