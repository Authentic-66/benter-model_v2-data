"""PART 2 -- QUEUED, NOT YET APPROVED TO RUN.

Load the CT result-chart backlog: 14 files in CharlesTown/ct-results-2026 that
have never been parsed, covering 2026-07-30 through 2026-08-27. Thirteen unique
charts; one file is a byte-identical duplicate and is skipped.

    python scripts_dpv1/_load_ct_backlog.py --dry-run   # parse + report, no writes
    python scripts_dpv1/_load_ct_backlog.py --execute   # actually load

Default is --dry-run. This expands the training corpus, so it wants a
deliberate decision and a fresh backup, exactly like the Part 1 load.

The duplicate
-------------
``20260801-usa-ct-a-d.standard.pdf`` and
``20260801-usa-ct-a-d.standard (1).pdf`` are byte-identical -- same size
(125,161 bytes) and same sha256 (45f7df71b568...). The '(1)' copy is a
browser re-download, one minute newer by mtime. The file WITHOUT the suffix is
kept as canonical; the '(1)' copy is skipped and never recorded in
parsed_files.

That choice has to be explicit rather than incidental: '(1)' sorts *before*
the clean name, so a naive ``sorted(dir.glob('*.pdf'))`` walk keeps the copy
and treats the real filename as the duplicate. Deduplication here is by
sha256, with the canonical file chosen by name, not by sort order.

Purge-first
-----------
Part 1 had to delete loaded upcoming cards before loading their charts, because
``entries`` carries ``UNIQUE(race_id, program_num)`` and ``db_loader`` inserts
with ``INSERT OR IGNORE`` while reusing existing race_day/race rows -- so a
chart loaded over an existing card is silently dropped. None of these 13 dates
currently exist in the database (checked 2026-08-29), so no purge is expected.
The guard runs anyway and refuses to load over a populated date rather than
silently no-op, since the backlog may grow before this is approved.

After loading
-------------
The DPv1 feature tables are NOT rebuilt by this script. Newly loaded entries
have no rows in entry_features_dpv1, so card_picks.py cannot score these cards
until the feature pipeline is re-run. That is a separate, deliberate step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import db_loader  # noqa: E402
import equibase_pdf_parser as parser  # noqa: E402

from _load_pending_results import purge_card  # noqa: E402

DB = ROOT / "scripts" / "racing_full.db"
CACHE = ROOT / "scripts" / "ct_cache"
PDF_DIR = ROOT / "CharlesTown" / "ct-results-2026"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pending_pdfs(conn: sqlite3.Connection) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """Unparsed charts, deduplicated by content. Returns (to_load, skipped)."""
    known = {r[0].replace("\\", "/").lower()
             for r in conn.execute(
                 "SELECT source_pdf FROM parsed_files WHERE success = 1")}
    known_names = {Path(k).name for k in known}

    candidates = []
    for f in sorted(PDF_DIR.glob("*.pdf")):
        if (str(f.relative_to(ROOT)).replace("\\", "/").lower() in known
                or f.name.lower() in known_names):
            continue
        candidates.append(f)

    # Canonical file per sha256: prefer the name without a '(n)' download
    # suffix, then the shortest name. Never rely on sort order -- '(1)' sorts
    # first and would otherwise win.
    by_sha: dict[str, list[Path]] = {}
    for f in candidates:
        by_sha.setdefault(_sha(f), []).append(f)

    to_load, skipped = [], []
    for _sha_hex, group in by_sha.items():
        canonical = sorted(group, key=lambda p: ("(" in p.stem, len(p.name)))[0]
        to_load.append(canonical)
        skipped.extend((dupe, canonical) for dupe in group if dupe != canonical)
    return sorted(to_load), skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="Load the CT result-chart backlog.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="parse and report, write nothing (default)")
    g.add_argument("--execute", action="store_true",
                   help="actually load into racing_full.db")
    args = ap.parse_args()
    execute = args.execute

    CACHE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        to_load, skipped = pending_pdfs(conn)
        for dupe, canonical in skipped:
            print(f"SKIP  {dupe.name}")
            print(f"      byte-identical duplicate of {canonical.name}")
        print(f"\n{len(to_load)} charts to load "
              f"({'EXECUTING' if execute else 'dry run, no writes'})\n")

        totals = {"races": 0, "entries": 0, "exotics": 0}
        for pdf in to_load:
            cached = CACHE / (pdf.stem + ".json")
            parsed = None
            if cached.exists():
                try:
                    candidate = json.loads(cached.read_text(encoding="utf-8"))
                    if candidate.get("file_sha256") == _sha(pdf):
                        parsed = candidate
                except (json.JSONDecodeError, OSError):
                    parsed = None
            if parsed is None:
                parsed = parser.parse_pdf(pdf)
                cached.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

            track = parsed.get("track_code")
            date = parsed.get("race_date")
            existing = conn.execute(
                """SELECT COUNT(*) FROM entries e
                   JOIN races r      ON r.id  = e.race_id
                   JOIN race_days rd ON rd.id = r.race_day_id
                   JOIN tracks t     ON t.id  = rd.track_id
                   WHERE t.code = ? AND rd.race_date = ?""",
                (track, date)).fetchone()[0]

            n_ent = sum(len(r.get("entries", [])) for r in parsed["races"])
            note = f"  ** {existing} existing entries: PURGE FIRST **" if existing else ""
            print(f"  {pdf.name:<45} {track} {date}  "
                  f"races={parsed.get('race_count')} entries={n_ent}{note}")

            if not execute:
                continue

            parsed["source_pdf"] = str(pdf.relative_to(ROOT)).replace("/", "\\")
            with conn:
                if existing:
                    purged = purge_card(conn, track, date)
                    print(f"      purged {purged['entries']} entries / "
                          f"{purged['races']} races / "
                          f"{purged['derived']} derived rows")
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
            for k in totals:
                totals[k] += counts[k]
            print(f"      loaded {counts['races']} races, "
                  f"{counts['entries']} entries, {counts['exotics']} exotics")

        if execute:
            print(f"\ntotal: {totals['races']} races, {totals['entries']} entries, "
                  f"{totals['exotics']} exotics")
            print("NOTE: entry_features_dpv1 is not rebuilt by this script. "
                  "Re-run the DPv1 feature pipeline before predicting these cards.")
        else:
            print("\ndry run -- nothing written. Re-run with --execute to load.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
