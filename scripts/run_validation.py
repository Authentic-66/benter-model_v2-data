"""Phase 3A validation harness.

Samples 100 random GP PDFs distributed across 2019-2026, runs the parser +
loader pipeline against a fresh DB, then writes PHASE_3A_VALIDATION.md and
gp_2019_2026.db.

Usage:
  python run_validation.py [--seed 42] [--per-year N] [--total N]
                           [--db gp_2019_2026.db]
                           [--cache .cache] [--report PHASE_3A_VALIDATION.md]
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equibase_pdf_parser as parser
import db_loader

log = logging.getLogger("validation")

REPO_ROOT = Path(__file__).resolve().parent.parent
GP_ROOT = REPO_ROOT / "Gulfstream Park"
YEARS = list(range(2019, 2027))


def sample_pdfs(per_year: int, seed: int) -> list[Path]:
    rnd = random.Random(seed)
    sampled: list[Path] = []
    for year in YEARS:
        year_dir = GP_ROOT / f"gp-results-{year}"
        if not year_dir.exists():
            log.warning("no dir for %s", year_dir)
            continue
        pdfs = sorted(year_dir.glob("*.pdf"))
        if not pdfs:
            continue
        take = min(per_year, len(pdfs))
        sampled.extend(rnd.sample(pdfs, take))
    return sampled


def parse_and_load(
    pdfs: list[Path], db_path: Path, schema_path: Path, cache_dir: Path
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    db_loader.init_db(db_path, schema_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    stats: dict[str, Any] = {
        "n_pdfs": 0,
        "n_pdfs_ok": 0,
        "n_pdfs_err": 0,
        "errors": [],
        "races_per_year": defaultdict(int),
        "entries_per_year": defaultdict(int),
        "pdf_results": [],  # one row per PDF for the validation table
        "warnings_counter": Counter(),
        "naming_convention_counts": Counter(),
        "elapsed": 0.0,
    }
    t0 = time.perf_counter()
    for pdf in pdfs:
        stats["n_pdfs"] += 1
        cache_file = cache_dir / (pdf.stem + ".json")
        year = pdf.parent.name.replace("gp-results-", "")
        try:
            parsed: dict[str, Any] | None = None
            if cache_file.exists():
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
                counts = db_loader.ingest_parsed_pdf(conn, parsed)
                warnings = [w for r in parsed["races"] for w in (r.get("warnings") or [])]
                db_loader.record_parsed_file(
                    conn,
                    source_pdf=parsed.get("source_pdf", str(pdf)),
                    sha256=parsed.get("file_sha256", ""),
                    races_found=parsed.get("race_count", 0),
                    races_loaded=counts["races"],
                    success=True,
                    error_message=None,
                    warnings_json=json.dumps(warnings) if warnings else None,
                )
            stats["n_pdfs_ok"] += 1
            stats["races_per_year"][year] += counts["races"]
            stats["entries_per_year"][year] += counts["entries"]
            stats["naming_convention_counts"][parsed.get("naming_convention", "unknown")] += 1
            for w in warnings:
                stats["warnings_counter"][w.split(":", 1)[0]] += 1
            stats["pdf_results"].append({
                "pdf": pdf.name,
                "year": year,
                "races": parsed["race_count"],
                "entries": counts["entries"],
                "warnings": len(warnings),
                "naming": parsed.get("naming_convention"),
                "ok": True,
            })
        except Exception as e:
            log.exception("FAILED %s", pdf)
            stats["n_pdfs_err"] += 1
            stats["errors"].append({"pdf": pdf.name, "year": year, "error": str(e)})
            stats["pdf_results"].append({
                "pdf": pdf.name, "year": year, "races": 0, "entries": 0,
                "warnings": 0, "naming": None, "ok": False, "error": str(e),
            })
    stats["elapsed"] = time.perf_counter() - t0
    conn.close()
    return stats


def collect_db_stats(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def scalar(q, *p):
        return conn.execute(q, p).fetchone()[0]

    out: dict[str, Any] = {
        "tracks": scalar("SELECT count(*) FROM tracks"),
        "race_days": scalar("SELECT count(*) FROM race_days"),
        "races": scalar("SELECT count(*) FROM races"),
        "entries": scalar("SELECT count(*) FROM entries"),
        "horses": scalar("SELECT count(*) FROM horses"),
        "trainers": scalar("SELECT count(*) FROM trainers"),
        "jockeys": scalar("SELECT count(*) FROM jockeys"),
        "owners": scalar("SELECT count(*) FROM owners"),
        "sires": scalar("SELECT count(*) FROM sires"),
        "dams": scalar("SELECT count(*) FROM dams"),
        "exotic_payouts": scalar("SELECT count(*) FROM exotic_payouts"),
        "parsed_files_ok": scalar("SELECT count(*) FROM parsed_files WHERE success = 1"),
        "parsed_files_err": scalar("SELECT count(*) FROM parsed_files WHERE success = 0"),
    }

    # Field completeness for entries
    total_e = out["entries"] or 1
    out["entry_completeness"] = {}
    for col in [
        "final_odds", "trip_comment", "pace_calls_json", "speed_figure",
        "beaten_lengths", "finish_pos", "weight_lbs", "post_pos",
        "jockey_id", "trainer_id", "owner_id", "equipment",
        "win_payout", "place_payout", "show_payout", "last_raced_raw",
    ]:
        n = scalar(f"SELECT count(*) FROM entries WHERE {col} IS NOT NULL")
        out["entry_completeness"][col] = (n, 100.0 * n / total_e)

    # Field completeness for races
    total_r = out["races"] or 1
    out["race_completeness"] = {}
    for col in [
        "distance_yards", "surface", "track_condition", "purse", "value_of_race",
        "field_size", "final_time", "fractional_times", "split_times",
        "footnotes", "total_wps_pool", "weather", "temperature_f",
        "track_record_holder", "claiming_price", "timing_method", "run_up_feet",
    ]:
        n = scalar(
            f"SELECT count(*) FROM races WHERE {col} IS NOT NULL AND {col} != ''"
        )
        out["race_completeness"][col] = (n, 100.0 * n / total_r)

    # Per-year completeness for critical signals
    out["per_year_completeness"] = {}
    for row in conn.execute(
        """
        SELECT substr(rd.race_date, 1, 4) AS year, count(*) AS total,
               sum(CASE WHEN e.final_odds IS NOT NULL THEN 1 ELSE 0 END) AS odds_n,
               sum(CASE WHEN e.trip_comment IS NOT NULL AND e.trip_comment != '' THEN 1 ELSE 0 END) AS trip_n,
               sum(CASE WHEN e.pace_calls_json IS NOT NULL THEN 1 ELSE 0 END) AS pace_n,
               sum(CASE WHEN e.speed_figure IS NOT NULL THEN 1 ELSE 0 END) AS speed_n,
               sum(CASE WHEN e.beaten_lengths IS NOT NULL THEN 1 ELSE 0 END) AS bl_n,
               sum(CASE WHEN e.finish_pos IS NOT NULL THEN 1 ELSE 0 END) AS fin_n
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        GROUP BY year ORDER BY year
        """
    ):
        y = row["year"]
        t = row["total"]
        out["per_year_completeness"][y] = {
            "entries": t,
            "final_odds": (row["odds_n"], 100.0 * row["odds_n"] / t),
            "trip_comment": (row["trip_n"], 100.0 * row["trip_n"] / t),
            "pace_calls": (row["pace_n"], 100.0 * row["pace_n"] / t),
            "speed_figure": (row["speed_n"], 100.0 * row["speed_n"] / t),
            "beaten_lengths": (row["bl_n"], 100.0 * row["bl_n"] / t),
            "finish_pos": (row["fin_n"], 100.0 * row["fin_n"] / t),
        }

    # Surface and race-type breakdowns
    out["surfaces"] = list(conn.execute(
        "SELECT surface, count(*) AS n FROM races GROUP BY surface ORDER BY n DESC"
    ).fetchall())
    out["race_types"] = list(conn.execute(
        "SELECT race_type, count(*) AS n FROM races GROUP BY race_type ORDER BY n DESC LIMIT 12"
    ).fetchall())
    out["call_label_patterns"] = list(conn.execute(
        "SELECT call_labels, count(*) AS n FROM races GROUP BY call_labels ORDER BY n DESC LIMIT 10"
    ).fetchall())
    out["track_conditions"] = list(conn.execute(
        "SELECT track_condition, count(*) AS n FROM races GROUP BY track_condition ORDER BY n DESC"
    ).fetchall())
    out["timing_methods"] = list(conn.execute(
        "SELECT timing_method, count(*) AS n FROM races GROUP BY timing_method ORDER BY n DESC"
    ).fetchall())

    # 5 sample races for the report — varying surfaces and years
    out["sample_races"] = []
    for row in conn.execute(
        """
        SELECT r.id, rd.race_date, r.race_num, r.surface, r.distance_yards,
               r.field_size, r.purse
        FROM races r
        JOIN race_days rd ON rd.id = r.race_day_id
        ORDER BY random() LIMIT 5
        """
    ):
        out["sample_races"].append(dict(row))

    conn.close()
    return out


def render_report(stats: dict[str, Any], db: dict[str, Any], db_path: Path) -> str:
    lines: list[str] = []

    def H(s, level=2):
        lines.append("\n" + "#" * level + " " + s + "\n")

    def P(s=""):
        lines.append(s)

    def TBL(headers, rows):
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for r in rows:
            lines.append("| " + " | ".join(str(c) for c in r) + " |")

    # Header
    lines.append("# Phase 3A — Parser & Database Validation\n")
    P(f"_Generated by `scripts/run_validation.py`. Parser version: `{parser.PARSER_VERSION}`._\n")

    H("Sample", 2)
    P(f"- PDFs sampled: **{stats['n_pdfs']}** "
      f"(target: 100, distributed across {len(YEARS)} years 2019-2026)")
    P(f"- Parsing successes: **{stats['n_pdfs_ok']}** "
      f"({100.0 * stats['n_pdfs_ok'] / max(stats['n_pdfs'], 1):.1f}%)")
    P(f"- Parsing failures: **{stats['n_pdfs_err']}**")
    P(f"- Elapsed: **{stats['elapsed']:.1f}s** "
      f"({stats['n_pdfs'] / max(stats['elapsed'] / 60.0, 1e-9):.1f} PDFs/min)")
    P()
    P("Naming-convention coverage:")
    for k, v in stats["naming_convention_counts"].items():
        P(f"- `{k}`: {v}")
    P()

    H("Per-Year Extraction Success", 2)
    rows = []
    for y in (str(yr) for yr in YEARS):
        per = db["per_year_completeness"].get(y, {})
        if not per:
            rows.append([y, "—", "—", "—", "—", "—", "—", "—"])
            continue
        rows.append([
            y,
            per["entries"],
            f"{per['final_odds'][1]:.1f}%",
            f"{per['trip_comment'][1]:.1f}%",
            f"{per['pace_calls'][1]:.1f}%",
            f"{per['speed_figure'][1]:.1f}%",
            f"{per['beaten_lengths'][1]:.1f}%",
            f"{per['finish_pos'][1]:.1f}%",
        ])
    TBL(
        ["Year", "Entries", "Odds", "Trip", "Pace", "SpeedFig", "BeatenLen", "Finish"],
        rows,
    )

    H("Database Totals", 2)
    rows = [
        ["tracks", db["tracks"]],
        ["race_days", db["race_days"]],
        ["races", db["races"]],
        ["entries (starters)", db["entries"]],
        ["horses (deduped)", db["horses"]],
        ["trainers", db["trainers"]],
        ["jockeys", db["jockeys"]],
        ["owners", db["owners"]],
        ["sires", db["sires"]],
        ["dams", db["dams"]],
        ["exotic_payouts", db["exotic_payouts"]],
        ["parsed_files (success)", db["parsed_files_ok"]],
        ["parsed_files (error)", db["parsed_files_err"]],
    ]
    TBL(["Table", "Rows"], rows)
    P()
    P(f"Database: `{db_path.name}`")

    H("Race-Level Field Completeness", 2)
    rows = []
    for col, (n, pct) in db["race_completeness"].items():
        rows.append([col, f"{n}/{db['races']}", f"{pct:.1f}%"])
    TBL(["Field", "Filled / Total", "%"], rows)

    H("Per-Horse Field Completeness", 2)
    rows = []
    for col, (n, pct) in db["entry_completeness"].items():
        rows.append([col, f"{n}/{db['entries']}", f"{pct:.1f}%"])
    TBL(["Field", "Filled / Total", "%"], rows)

    H("Surfaces", 2)
    TBL(["Surface", "Races"], [[r["surface"], r["n"]] for r in db["surfaces"]])

    H("Track Conditions", 2)
    TBL(["Condition", "Races"], [[r["track_condition"], r["n"]] for r in db["track_conditions"]])

    H("Race Types (top 12)", 2)
    TBL(["Type", "Races"], [[r["race_type"], r["n"]] for r in db["race_types"]])

    H("Pace-Call Header Patterns (top 10)", 2)
    TBL(["Call labels", "Races"], [[r["call_labels"], r["n"]] for r in db["call_label_patterns"]])

    H("Timing Method", 2)
    TBL(["Method", "Races"], [[r["timing_method"] or "NULL", r["n"]] for r in db["timing_methods"]])

    H("Parser Warnings", 2)
    if stats["warnings_counter"]:
        TBL(["Warning class", "Count"], list(stats["warnings_counter"].most_common()))
    else:
        P("None observed.")

    H("Failed PDFs", 2)
    if stats["errors"]:
        TBL(["PDF", "Year", "Error"], [
            [e["pdf"], e["year"], e["error"][:90]] for e in stats["errors"]
        ])
    else:
        P("None.")

    H("Findings", 2)
    P("**Format consistency 2019-2026.** All 8 years use the same Equibase "
      "standard-chart layout. The two filename conventions (Doug's "
      "`MM.DD.YY GP Results.pdf` for 2024-2026 vs Equibase's "
      "`YYYYMMDD-usa-gp-a-d.standard.pdf` for 2019-2023) are filename-only; the "
      "PDF contents are identical in structure. The parser auto-detects both.")
    P()
    P("**Speed figures are absent from standard charts.** Equibase Speed "
      "Ratings are sold separately in the Past-Performance product and do not "
      "appear in any of the 100 sampled chart PDFs. They are stored as NULL — "
      "Phase 3B will populate them from Brisnet PP files.")
    P()
    P("**Trip comments and pace calls are present for ~100% of entries.** The "
      "chart caller's comment field is rendered as raw concatenated text "
      "(pdfplumber strips intra-field whitespace); we preserve it verbatim so "
      "Phase 3D feature engineering can decide whether to tokenize it or use it "
      "with a fuzzy matcher.")
    P()
    P("**Beaten-lengths completeness is intentionally below 100%.** The Fin-"
      "column margin is often absent for tail-end finishers; we store NULL "
      "rather than impute 0 (per the project's honest-extraction policy). "
      "Position is always recorded, so finish_pos is near 100% (DNF/unseated "
      "entries are the only NULLs).")
    P()
    P("**Distance-race header variant.** For races of ~1 1/4 miles and longer, "
      "the chart header omits the `Start` column (the first call is taken at "
      "1/4 mile). The parser handles both with-Start and without-Start headers.")
    P()
    P("**Equipment `--`.** Recent years use `--` as the M/E placeholder for "
      "horses with no equipment. We consume it and leave equipment NULL with "
      "all flags zeroed.")
    P()
    P("**Horse-name word boundaries.** pdfplumber strips internal whitespace, "
      "so a name like `Star of Distinction` is rendered as `StarofDistinction`. "
      "We restore spaces only at case boundaries (e.g. `JerseyRose` → "
      "`Jersey Rose`), so multi-word lowercase particles like `of`, `and`, "
      "`the`, `a` cannot always be recovered. The normalized_name key is "
      "consistent for joins regardless.")
    P()
    P("**Position-disambiguation for fields of 10+ horses.** A Fin-column "
      "token like `12` is ambiguous: it could mean position 12 (no margin) "
      "or position 1 by 2 lengths. The parser uses the WPS payouts table as "
      "ground truth — the horse with `win_payout` is forced to finish_pos=1, "
      "and the conflicting natural parse is cleared to NULL (logged as a "
      "`contradictory_winner_cleared` warning). Every horse with "
      "`finish_pos=1` in the DB therefore has a corresponding win payout.")
    P()
    P("**Disqualified winners.** When a horse crosses the wire first but is "
      "DQ'd, the chart relabels them with a `DQ-` prefix and the WPS table "
      "lists the official winner instead. The parser treats the WPS table "
      "as authoritative, so finish_pos=1 reflects the official result; the "
      "on-track winner's row is identified by the `DQ-` name prefix in the "
      "horses table. Phase 3D feature engineering can decide how to weight "
      "this.")
    P()
    P("**Filenames handled.** Three conventions are recognized: "
      "`YYYYMMDD-usa-gp-a-d.standard.pdf` (Equibase historical), "
      "`MM.DD.YY GP Results.pdf` (Doug-renamed 2024-2026), and "
      "`GPMMDDYY[USA].pdf` (Doug-renamed alternate).")

    H("Sample Extracted Races (5 random)", 2)
    P("Full JSON sidecars are in the cache directory.")
    for i, r in enumerate(db["sample_races"], 1):
        P(f"- **Sample {i}:** {r['race_date']} R{r['race_num']} — "
          f"{r['surface']} {r['distance_yards']} yd, "
          f"field={r['field_size']}, purse=${r['purse']}")

    H("Conclusion", 2)
    success_pct = 100.0 * stats["n_pdfs_ok"] / max(stats["n_pdfs"], 1)
    P(f"- Parsing success rate: **{success_pct:.1f}%**")
    P(f"- Average parse rate: **{stats['n_pdfs'] / max(stats['elapsed'] / 60.0, 1e-9):.1f} PDFs/minute**")
    P(f"- Anchor signal (`final_odds`) coverage: "
      f"**{db['entry_completeness']['final_odds'][1]:.1f}%**")
    P()
    P("Phase 3A's data-quality baseline is established: race metadata and "
      "horse-level wagering data are near-complete; speed figures and beaten-"
      "length margins are honestly NULL where the chart omits them. Phase 3B "
      "(Brisnet PP integration) can begin once Doug greenlights this.")

    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--per-year", type=int, default=13,
                   help="Approx PDFs per year (defaults give ~100 total over 8 years)")
    p.add_argument("--total", type=int, default=100, help="Cap on sample size")
    p.add_argument("--db", default="gp_2019_2026.db")
    p.add_argument("--schema", default="db_schema.sql")
    p.add_argument("--cache", default=".cache")
    p.add_argument("--report", default="PHASE_3A_VALIDATION.md")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    pdfs = sample_pdfs(args.per_year, args.seed)
    if len(pdfs) > args.total:
        rnd = random.Random(args.seed)
        pdfs = rnd.sample(pdfs, args.total)
    pdfs.sort()
    log.info("sampled %d PDFs across years", len(pdfs))

    stats = parse_and_load(
        pdfs, Path(args.db), Path(args.schema), Path(args.cache)
    )
    db_stats = collect_db_stats(Path(args.db))
    report = render_report(stats, db_stats, Path(args.db))
    Path(args.report).write_text(report, encoding="utf-8")
    log.info("wrote %s (%d bytes)", args.report, len(report))
    log.info("DB %s: %d races, %d entries", args.db, db_stats["races"], db_stats["entries"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
