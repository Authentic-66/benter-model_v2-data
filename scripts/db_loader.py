"""Load parsed race JSON into the SQLite schema in db_schema.sql.

Idempotent: dedupes horses/trainers/jockeys/owners/sires/dams by normalized
name. Safe to re-run — UNIQUE constraints on (race_day, race_num) and
(race_id, program_num) keep the fact tables clean.

Usage:
  # Initialize DB and ingest JSON sidecars produced by equibase_pdf_parser.py
  python db_loader.py init --db gp_2019_2026.db --schema db_schema.sql
  python db_loader.py ingest --db gp_2019_2026.db --json-dir <cache_dir>

  # One-shot: parse a directory then load
  python db_loader.py pipeline --db gp_2019_2026.db --pdf-dir <dir> --cache <cache>
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# Make the parser module importable when this script lives next to it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equibase_pdf_parser as parser

log = logging.getLogger("db_loader")


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db(db_path: Path, schema_path: Path) -> None:
    """Apply the schema file. Safe to call repeatedly (CREATE IF NOT EXISTS)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dimension lookups — get-or-insert with normalized name keys.
# ---------------------------------------------------------------------------

def _norm(name: str | None) -> str | None:
    if not name:
        return None
    return parser.normalize_name(name)


def get_or_create_track(conn: sqlite3.Connection, code: str, full_name: str | None) -> int:
    cur = conn.execute("SELECT id FROM tracks WHERE code = ?", (code,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO tracks (code, name) VALUES (?, ?)",
        (code, full_name),
    )
    return cur.lastrowid


def _get_or_create(conn: sqlite3.Connection, table: str, name: str | None) -> int | None:
    if not name:
        return None
    nm = _norm(name)
    cur = conn.execute(f"SELECT id FROM {table} WHERE normalized_name = ?", (nm,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        f"INSERT INTO {table} (name, normalized_name) VALUES (?, ?)",
        (name, nm),
    )
    return cur.lastrowid


def get_or_create_trainer(conn, name): return _get_or_create(conn, "trainers", name)
def get_or_create_jockey(conn, name):  return _get_or_create(conn, "jockeys", name)
def get_or_create_owner(conn, name):   return _get_or_create(conn, "owners", name)


def get_or_create_sire(conn: sqlite3.Connection, full_name: str | None) -> int | None:
    if not full_name:
        return None
    base, country = parser.strip_country_code(full_name)
    nm = _norm(base)
    if not nm:
        return None
    cur = conn.execute("SELECT id FROM sires WHERE normalized_name = ?", (nm,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO sires (name, country, normalized_name) VALUES (?, ?, ?)",
        (base, country, nm),
    )
    return cur.lastrowid


def get_or_create_dam(
    conn: sqlite3.Connection, full_name: str | None, dam_sire_id: int | None
) -> int | None:
    if not full_name:
        return None
    base, country = parser.strip_country_code(full_name)
    nm = _norm(base)
    if not nm:
        return None
    cur = conn.execute("SELECT id, dam_sire_id FROM dams WHERE normalized_name = ?", (nm,))
    row = cur.fetchone()
    if row:
        # Backfill dam_sire_id if it was unknown before but is now provided
        if row[1] is None and dam_sire_id is not None:
            conn.execute("UPDATE dams SET dam_sire_id = ? WHERE id = ?", (dam_sire_id, row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO dams (name, country, normalized_name, dam_sire_id) VALUES (?, ?, ?, ?)",
        (base, country, nm, dam_sire_id),
    )
    return cur.lastrowid


def get_or_create_horse(
    conn: sqlite3.Connection,
    name: str,
    country: str | None = None,
    color: str | None = None,
    sex: str | None = None,
    foaled_date: str | None = None,
    foaled_place: str | None = None,
    sire_id: int | None = None,
    dam_id: int | None = None,
    breeder_id: int | None = None,
) -> int:
    nm = _norm(name)
    cur = conn.execute("SELECT id, sire_id, dam_id FROM horses WHERE normalized_name = ?", (nm,))
    row = cur.fetchone()
    if row:
        # Opportunistically backfill missing pedigree fields
        updates: dict[str, Any] = {}
        if row[1] is None and sire_id is not None:
            updates["sire_id"] = sire_id
        if row[2] is None and dam_id is not None:
            updates["dam_id"] = dam_id
        if color or sex or foaled_date or foaled_place or breeder_id:
            # Read existing to fill only-when-missing
            cur2 = conn.execute(
                "SELECT color, sex, foaled_date, foaled_place, breeder_id FROM horses WHERE id = ?",
                (row[0],),
            )
            existing = cur2.fetchone()
            keys = ("color", "sex", "foaled_date", "foaled_place", "breeder_id")
            current = dict(zip(keys, existing))
            for k, v in {
                "color": color,
                "sex": sex,
                "foaled_date": foaled_date,
                "foaled_place": foaled_place,
                "breeder_id": breeder_id,
            }.items():
                if current.get(k) is None and v is not None:
                    updates[k] = v
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE horses SET {set_clause} WHERE id = ?",
                (*updates.values(), row[0]),
            )
        return row[0]
    cur = conn.execute(
        """
        INSERT INTO horses
          (name, country, normalized_name, color, sex, foaled_date, foaled_place,
           sire_id, dam_id, breeder_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, country, nm, color, sex, foaled_date, foaled_place, sire_id, dam_id, breeder_id),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Race ingest
# ---------------------------------------------------------------------------

def _to_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def ingest_race_day(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    race_date: str,
    source_pdf: str,
    weather_summary: str | None,
) -> int:
    cur = conn.execute(
        "SELECT id FROM race_days WHERE track_id = ? AND race_date = ?",
        (track_id, race_date),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        """
        INSERT INTO race_days (track_id, race_date, source_pdf, weather_summary)
        VALUES (?, ?, ?, ?)
        """,
        (track_id, race_date, source_pdf, weather_summary),
    )
    return cur.lastrowid


def ingest_race(conn: sqlite3.Connection, race_day_id: int, race: dict[str, Any]) -> int:
    cur = conn.execute(
        "SELECT id FROM races WHERE race_day_id = ? AND race_num = ?",
        (race_day_id, race["race_num"]),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur = conn.execute(
        """
        INSERT INTO races (
            race_day_id, race_num,
            distance_text, distance_yards, surface, is_off_turf, track_condition,
            purse, available_money, value_of_race, value_breakdown, race_type, breed,
            class_level, conditions_text, claiming_price,
            track_record_holder, track_record_time, track_record_date,
            field_size, scratched_horses,
            weather, temperature_f, off_at, start_note, timing_method,
            call_labels, fractional_times, final_time, time_from_gate, split_times,
            run_up_feet, temporary_rail_feet,
            total_wps_pool, footnotes
        ) VALUES (
            ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?
        )
        """,
        (
            race_day_id, race["race_num"],
            race.get("distance_text"), race.get("distance_yards"), race.get("surface"),
            race.get("is_off_turf", 0), race.get("track_condition"),
            race.get("purse"), race.get("available_money"), race.get("value_of_race"),
            race.get("value_breakdown"), race.get("race_type"), race.get("breed"),
            race.get("class_level"), race.get("conditions_text"), race.get("claiming_price"),
            race.get("track_record_holder"), race.get("track_record_time"), race.get("track_record_date"),
            race.get("field_size"), _to_json(race.get("scratched_horses") or []),
            race.get("weather"), race.get("temperature_f"), race.get("off_at"),
            race.get("start_note"), race.get("timing_method"),
            _to_json(race.get("call_labels")), _to_json(race.get("fractional_times")),
            race.get("final_time"), race.get("time_from_gate"), _to_json(race.get("split_times")),
            race.get("run_up_feet"), race.get("temporary_rail_feet"),
            race.get("total_wps_pool"), race.get("footnotes"),
        ),
    )
    return cur.lastrowid


def ingest_entry(
    conn: sqlite3.Connection, race_id: int, entry: dict[str, Any], race: dict[str, Any]
) -> None:
    # Horse pedigree comes from race.winner only for the winner. For non-winners
    # we have just the name; pedigree backfills when this horse later appears as
    # a winner or as another entry with richer info (re-ingest is harmless).
    winner_info = race.get("winner") or {}
    is_winner = entry.get("finish_pos") == 1
    pedigree = winner_info if is_winner else {}

    sire_id = get_or_create_sire(conn, pedigree.get("sire"))
    # dam_sire row first, since dam references it
    dam_sire_id = get_or_create_sire(conn, pedigree.get("dam_sire"))
    dam_id = get_or_create_dam(conn, pedigree.get("dam"), dam_sire_id)
    breeder_id = get_or_create_owner(conn, race.get("breeder")) if is_winner else None

    horse_id = get_or_create_horse(
        conn,
        name=entry["horse_name"],
        country=entry.get("horse_country"),
        color=pedigree.get("color"),
        sex=pedigree.get("sex"),
        foaled_date=pedigree.get("foaled_date"),
        foaled_place=pedigree.get("foaled_place"),
        sire_id=sire_id,
        dam_id=dam_id,
        breeder_id=breeder_id,
    )
    jockey_id = get_or_create_jockey(conn, entry.get("jockey"))
    trainer_id = get_or_create_trainer(conn, entry.get("trainer"))
    owner_id = get_or_create_owner(conn, entry.get("owner"))

    conn.execute(
        """
        INSERT OR IGNORE INTO entries (
            race_id, horse_id, jockey_id, trainer_id, owner_id,
            program_num, post_pos, start_pos,
            weight_lbs, equipment,
            has_lasix, has_blinkers, has_front_bandages,
            first_time_blinkers, first_time_bandages,
            pace_calls_json, finish_pos, finish_status, beaten_lengths, winning_margin_text,
            final_odds, is_favorite,
            speed_figure, trip_comment, last_raced_raw,
            win_payout, place_payout, show_payout,
            claimed_in_race, new_trainer_after, new_owner_after, claiming_price
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?
        )
        """,
        (
            race_id, horse_id, jockey_id, trainer_id, owner_id,
            entry.get("program_num"), entry.get("post_pos"), entry.get("start_pos"),
            entry.get("weight_lbs"), entry.get("equipment"),
            entry.get("has_lasix"), entry.get("has_blinkers"), entry.get("has_front_bandages"),
            entry.get("first_time_blinkers"), entry.get("first_time_bandages"),
            _to_json(entry.get("pace_calls")), entry.get("finish_pos"),
            "DNF" if entry.get("finish_pos") is None and (entry.get("pace_calls") or {}).get(
                (race.get("call_labels") or ["Fin"])[-1]
            ) == "---" else "finished" if entry.get("finish_pos") is not None else None,
            entry.get("beaten_lengths"), entry.get("winning_margin_text"),
            entry.get("final_odds"), entry.get("is_favorite"),
            entry.get("speed_figure"), entry.get("trip_comment"), entry.get("last_raced_raw"),
            entry.get("win_payout"), entry.get("place_payout"), entry.get("show_payout"),
            entry.get("claimed_in_race", 0), entry.get("new_trainer_after"),
            entry.get("new_owner_after"), entry.get("claiming_price"),
        ),
    )


def ingest_exotics(conn: sqlite3.Connection, race_id: int, exotics: list[dict[str, Any]]) -> None:
    for e in exotics:
        conn.execute(
            """
            INSERT INTO exotic_payouts
              (race_id, wager_type, base_amount, wager_name,
               winning_numbers, qualifier, payoff, pool, carryover)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                race_id, e.get("wager_type"), e.get("base_amount"), e.get("wager_name"),
                e.get("winning_numbers"), e.get("qualifier"),
                e.get("payoff"), e.get("pool"), e.get("carryover"),
            ),
        )


class SkippedPDF(Exception):
    """Raised when a parsed PDF is not a result chart we can ingest.

    Distinct from generic errors so the pipeline can record it as a soft
    skip rather than a crash (e.g. Brisnet PP files share the directory tree
    but aren't result charts; later phases will parse those separately).
    """


def ingest_parsed_pdf(conn: sqlite3.Connection, parsed: dict[str, Any]) -> dict[str, int]:
    """Top-level: insert one parsed-PDF dict into the DB. Returns counts."""
    track_code = parsed.get("track_code")
    race_date = parsed.get("race_date")
    race_count = parsed.get("race_count", 0)
    if not track_code or not race_date or race_count == 0:
        raise SkippedPDF(
            f"not a result chart "
            f"(track={track_code!r}, date={race_date!r}, races={race_count}): "
            f"{parsed.get('source_pdf')}"
        )
    track_id = get_or_create_track(conn, track_code, parsed.get("track_text"))

    # Weather summary uses first race that has one (most cards have one weather block).
    weather_summary = None
    for r in parsed["races"]:
        if r.get("weather") and r.get("temperature_f") is not None:
            weather_summary = f"{r['weather']},{r['temperature_f']}F"
            break

    race_day_id = ingest_race_day(
        conn,
        track_id=track_id,
        race_date=race_date,
        source_pdf=parsed.get("source_pdf", ""),
        weather_summary=weather_summary,
    )

    n_races = 0
    n_entries = 0
    n_exotics = 0
    for race in parsed["races"]:
        race_id = ingest_race(conn, race_day_id, race)
        n_races += 1
        for entry in race["entries"]:
            ingest_entry(conn, race_id, entry, race)
            n_entries += 1
        ingest_exotics(conn, race_id, race.get("exotic_payouts") or [])
        n_exotics += len(race.get("exotic_payouts") or [])

    return {"races": n_races, "entries": n_entries, "exotics": n_exotics}


def record_parsed_file(
    conn: sqlite3.Connection,
    *,
    source_pdf: str,
    sha256: str,
    races_found: int,
    races_loaded: int,
    success: bool,
    error_message: str | None,
    warnings_json: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO parsed_files
          (source_pdf, file_sha256, parsed_at, parser_version,
           races_found, races_loaded, success, error_message, warnings_json)
        VALUES (?, ?, datetime('now'), ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_pdf) DO UPDATE SET
          file_sha256 = excluded.file_sha256,
          parsed_at   = excluded.parsed_at,
          parser_version = excluded.parser_version,
          races_found = excluded.races_found,
          races_loaded = excluded.races_loaded,
          success     = excluded.success,
          error_message = excluded.error_message,
          warnings_json = excluded.warnings_json
        """,
        (
            source_pdf, sha256, parser.PARSER_VERSION,
            races_found, races_loaded, int(success), error_message, warnings_json,
        ),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _cmd_init(args: argparse.Namespace) -> int:
    init_db(Path(args.db), Path(args.schema))
    log.info("initialized %s with schema %s", args.db, args.schema)
    return 0


def _ingest_one_json(conn: sqlite3.Connection, json_path: Path) -> tuple[bool, str | None, dict[str, int]]:
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    try:
        with conn:  # transaction per PDF — rollback on error
            counts = ingest_parsed_pdf(conn, parsed)
            warnings = []
            for r in parsed["races"]:
                warnings.extend(r.get("warnings") or [])
            record_parsed_file(
                conn,
                source_pdf=parsed.get("source_pdf", str(json_path)),
                sha256=parsed.get("file_sha256", ""),
                races_found=parsed.get("race_count", 0),
                races_loaded=counts["races"],
                success=True,
                error_message=None,
                warnings_json=json.dumps(warnings) if warnings else None,
            )
        return True, None, counts
    except Exception as e:
        log.exception("ingest failed for %s", json_path)
        with conn:
            record_parsed_file(
                conn,
                source_pdf=parsed.get("source_pdf", str(json_path)),
                sha256=parsed.get("file_sha256", ""),
                races_found=parsed.get("race_count", 0),
                races_loaded=0,
                success=False,
                error_message=str(e),
                warnings_json=None,
            )
        return False, str(e), {"races": 0, "entries": 0, "exotics": 0}


def _cmd_ingest(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    json_dir = Path(args.json_dir)
    if not db_path.exists():
        log.error("DB %s does not exist; run `init` first", db_path)
        return 1
    if not json_dir.exists():
        log.error("json_dir %s not found", json_dir)
        return 1
    files = sorted(json_dir.glob("*.json"))
    if args.limit:
        files = files[: args.limit]
    log.info("ingesting %d JSON files", len(files))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    n_ok = 0
    n_err = 0
    totals = {"races": 0, "entries": 0, "exotics": 0}
    t0 = time.perf_counter()
    for f in files:
        ok, err, counts = _ingest_one_json(conn, f)
        if ok:
            n_ok += 1
            for k in totals:
                totals[k] += counts.get(k, 0)
        else:
            n_err += 1
    conn.close()
    elapsed = time.perf_counter() - t0
    log.info(
        "done: %d ok, %d err in %.1fs — %d races, %d entries, %d exotics",
        n_ok, n_err, elapsed, totals["races"], totals["entries"], totals["exotics"],
    )
    return 0 if n_err == 0 else 2


def _cmd_pipeline(args: argparse.Namespace) -> int:
    # Parse PDFs, then ingest the resulting JSONs.
    pdf_dir = Path(args.pdf_dir)
    cache_dir = Path(args.cache)
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db)
    schema_path = Path(args.schema)
    if not db_path.exists():
        init_db(db_path, schema_path)
        log.info("created %s", db_path)
    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if args.exclude:
        excludes = args.exclude
        pdfs = [p for p in pdfs if not any(x in p.parts for x in excludes)]
    if args.limit:
        pdfs = pdfs[: args.limit]
    log.info("found %d PDFs under %s", len(pdfs), pdf_dir)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Resume support: skip PDFs already successfully recorded with a matching sha.
    already_done: dict[str, str] = {}
    if args.resume:
        for s, h in conn.execute(
            "SELECT source_pdf, file_sha256 FROM parsed_files WHERE success = 1"
        ):
            already_done[s] = h

    n_ok = 0
    n_err = 0
    n_skip = 0
    n_resumed = 0
    totals = {"races": 0, "entries": 0, "exotics": 0}
    t0 = time.perf_counter()
    for i, pdf in enumerate(pdfs, 1):
        try:
            # Resume: skip if already recorded as successful with matching sha.
            if args.resume and (recorded := already_done.get(str(pdf))):
                pdf_sha = parser._sha256(pdf)
                if recorded == pdf_sha:
                    n_resumed += 1
                    if i % 100 == 0:
                        log.info("  progress: %d/%d (%d resumed)", i, len(pdfs), n_resumed)
                    continue
            cache_file = cache_dir / (pdf.stem + ".json")
            parsed: dict[str, Any] | None = None
            if cache_file.exists() and not args.force_parse:
                try:
                    candidate = json.loads(cache_file.read_text(encoding="utf-8"))
                    if candidate.get("file_sha256") == parser._sha256(pdf):
                        parsed = candidate
                except Exception:
                    parsed = None
            if parsed is None:
                parsed = parser.parse_pdf(pdf)
                cache_file.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            with conn:
                counts = ingest_parsed_pdf(conn, parsed)
                warnings = [w for r in parsed["races"] for w in (r.get("warnings") or [])]
                record_parsed_file(
                    conn,
                    source_pdf=parsed.get("source_pdf", str(pdf)),
                    sha256=parsed.get("file_sha256", ""),
                    races_found=parsed.get("race_count", 0),
                    races_loaded=counts["races"],
                    success=True,
                    error_message=None,
                    warnings_json=json.dumps(warnings) if warnings else None,
                )
            for k in totals:
                totals[k] += counts.get(k, 0)
            n_ok += 1
            if i % 25 == 0:
                log.info("  progress: %d/%d  (%.1f PDFs/min)", i, len(pdfs),
                         (i / max(time.perf_counter() - t0, 1e-9)) * 60.0)
        except SkippedPDF as e:
            log.info("SKIP %s: %s", pdf.name, e)
            with conn:
                record_parsed_file(
                    conn,
                    source_pdf=str(pdf), sha256="", races_found=0, races_loaded=0,
                    success=False, error_message=f"skipped: {e}", warnings_json=None,
                )
            n_skip += 1
        except Exception as e:
            log.exception("FAILED %s: %s", pdf, e)
            with conn:
                record_parsed_file(
                    conn,
                    source_pdf=str(pdf), sha256="", races_found=0, races_loaded=0,
                    success=False, error_message=str(e), warnings_json=None,
                )
            n_err += 1
    conn.close()
    elapsed = time.perf_counter() - t0
    rate = len(pdfs) / max(elapsed / 60.0, 1e-9)
    log.info(
        "done: %d ok, %d skipped (non-chart), %d resumed, %d err in %.1fs (%.1f PDFs/min)\n"
        "  totals: %d races, %d entries, %d exotics",
        n_ok, n_skip, n_resumed, n_err, elapsed, rate,
        totals["races"], totals["entries"], totals["exotics"],
    )
    return 0 if n_err == 0 else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Equibase results SQLite loader")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--db", required=True)
    p_init.add_argument("--schema", required=True)
    p_init.set_defaults(func=_cmd_init)

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--db", required=True)
    p_ing.add_argument("--json-dir", required=True)
    p_ing.add_argument("--limit", type=int, default=0)
    p_ing.set_defaults(func=_cmd_ingest)

    p_pipe = sub.add_parser("pipeline")
    p_pipe.add_argument("--db", required=True)
    p_pipe.add_argument("--schema", required=True)
    p_pipe.add_argument("--pdf-dir", required=True)
    p_pipe.add_argument("--cache", required=True)
    p_pipe.add_argument("--limit", type=int, default=0)
    p_pipe.add_argument("--force-parse", action="store_true")
    p_pipe.add_argument(
        "--exclude", action="append", default=[],
        help="Skip PDFs under this path component (repeatable). e.g. --exclude gp-pps-files",
    )
    p_pipe.add_argument(
        "--resume", action="store_true",
        help="Skip PDFs already successfully recorded in parsed_files with matching sha.",
    )
    p_pipe.set_defaults(func=_cmd_pipeline)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
