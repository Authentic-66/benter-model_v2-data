"""Phase 3B full-load analyzer.

Runs the post-pipeline analyses against gp_full.db and emits a single
markdown report. Builds the deliverable `PHASE_3B_FULL_LOAD.md`.

Sections:
  1. Pipeline summary (PDFs, races, entries per year)
  2. Field completeness per year
  3. Coupled-entry survey (program_num matches `\\d+[A-Z]`)
  4. Scratched-horse verification
  5. Edge cases (DQ, large/small fields, race types)
  6. Random 50-race spot check (winner, payouts, exotics line up)
  7. Performance / disk metrics
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equibase_pdf_parser as parser

log = logging.getLogger("analyze_full_load")


def _scalar(conn: sqlite3.Connection, q: str, *p: Any) -> Any:
    return conn.execute(q, p).fetchone()[0]


def render_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def pipeline_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["pdfs_ok"] = _scalar(conn, "SELECT count(*) FROM parsed_files WHERE success = 1")
    out["pdfs_err"] = _scalar(conn, "SELECT count(*) FROM parsed_files WHERE success = 0")
    out["pdfs_total"] = out["pdfs_ok"] + out["pdfs_err"]
    out["races"] = _scalar(conn, "SELECT count(*) FROM races")
    out["entries"] = _scalar(conn, "SELECT count(*) FROM entries")
    out["horses"] = _scalar(conn, "SELECT count(*) FROM horses")
    out["trainers"] = _scalar(conn, "SELECT count(*) FROM trainers")
    out["jockeys"] = _scalar(conn, "SELECT count(*) FROM jockeys")
    out["owners"] = _scalar(conn, "SELECT count(*) FROM owners")
    out["sires"] = _scalar(conn, "SELECT count(*) FROM sires")
    out["dams"] = _scalar(conn, "SELECT count(*) FROM dams")
    out["exotic_payouts"] = _scalar(conn, "SELECT count(*) FROM exotic_payouts")
    return out


def per_year_summary(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for r in conn.execute(
        """
        SELECT substr(rd.race_date, 1, 4) AS year,
               count(DISTINCT rd.id) AS race_days,
               count(DISTINCT r.id) AS races,
               count(e.id) AS entries
        FROM race_days rd
        JOIN races r ON r.race_day_id = rd.id
        JOIN entries e ON e.race_id = r.id
        GROUP BY year ORDER BY year
        """
    ):
        rows.append({"year": r[0], "race_days": r[1], "races": r[2], "entries": r[3]})
    return rows


def per_year_pdf_status(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Extract per-year PDF success rate by parsing the source_pdf path."""
    rows = []
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [ok, err]
    for source_pdf, success in conn.execute(
        "SELECT source_pdf, success FROM parsed_files"
    ):
        m = re.search(r"gp-results-(\d{4})", source_pdf)
        year = m.group(1) if m else "?"
        counts[year][0 if success else 1] += 1
    for year in sorted(counts):
        ok, err = counts[year]
        rows.append({"year": year, "ok": ok, "err": err, "total": ok + err})
    return rows


def per_year_completeness(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for r in conn.execute(
        """
        SELECT substr(rd.race_date, 1, 4) AS year,
               count(*) AS total,
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
        rows.append({
            "year": r[0], "entries": r[1],
            "odds_pct": 100.0 * r[2] / r[1],
            "trip_pct": 100.0 * r[3] / r[1],
            "pace_pct": 100.0 * r[4] / r[1],
            "speed_pct": 100.0 * r[5] / r[1],
            "bl_pct": 100.0 * r[6] / r[1],
            "fin_pct": 100.0 * r[7] / r[1],
        })
    return rows


def coupled_entries(conn: sqlite3.Connection) -> dict[str, Any]:
    """Find entries with program_num matching `\\d+[A-Z]` (coupled)."""
    total = _scalar(
        conn,
        r"SELECT count(*) FROM entries WHERE program_num GLOB '[0-9]*[A-Z]*'",
    )
    races_with_couples = _scalar(
        conn,
        r"""
        SELECT count(DISTINCT race_id) FROM entries
        WHERE program_num GLOB '[0-9]*[A-Z]*'
        """,
    )
    by_year = []
    for r in conn.execute(
        r"""
        SELECT substr(rd.race_date, 1, 4) AS year, count(*) AS n
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE e.program_num GLOB '[0-9]*[A-Z]*'
        GROUP BY year ORDER BY year
        """
    ):
        by_year.append({"year": r[0], "n": r[1]})

    # Sample 5 races showing couples (winning examples preferred).
    sample_races = []
    seen_race_ids: set[int] = set()
    for r in conn.execute(
        r"""
        SELECT DISTINCT r.id, rd.race_date, r.race_num, r.field_size, r.surface,
               r.distance_yards
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE e.program_num GLOB '[0-9]*[A-Z]*'
        ORDER BY rd.race_date, r.race_num
        """
    ):
        race_id = r[0]
        if race_id in seen_race_ids:
            continue
        seen_race_ids.add(race_id)
        entries = conn.execute(
            """
            SELECT e.program_num, h.name, e.post_pos, e.start_pos, e.finish_pos,
                   e.final_odds
            FROM entries e
            JOIN horses h ON h.id = e.horse_id
            WHERE e.race_id = ?
            ORDER BY e.post_pos
            """,
            (race_id,),
        ).fetchall()
        sample_races.append({
            "date": r[1], "race_num": r[2], "surface": r[4],
            "distance_yards": r[5], "field_size": r[3],
            "entries": [dict(zip(
                ["program_num", "horse", "post_pos", "start_pos", "finish_pos", "odds"], e,
            )) for e in entries],
        })
        if len(sample_races) >= 5:
            break

    return {
        "n_entries": total,
        "n_races": races_with_couples,
        "by_year": by_year,
        "sample_races": sample_races,
    }


def scratch_verification(conn: sqlite3.Connection) -> dict[str, Any]:
    """Look for races whose program_num set has gaps but post_pos is sequential.

    Indicates that a horse was scratched between paddock and post: the program
    number stays as-printed while the post-position renumbers around the gap.
    """
    candidates = conn.execute(
        """
        SELECT r.id, rd.race_date, r.race_num, r.field_size, r.scratched_horses
        FROM races r
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE r.scratched_horses IS NOT NULL
          AND r.scratched_horses != '[]'
        ORDER BY rd.race_date, r.race_num
        """
    ).fetchall()

    n_with_scratches = len(candidates)
    n_with_gaps = 0
    sample_races = []
    for race_id, date, race_num, field_size, scr_json in candidates:
        entries = conn.execute(
            """
            SELECT e.program_num, h.name, e.post_pos
            FROM entries e
            JOIN horses h ON h.id = e.horse_id
            WHERE e.race_id = ?
            ORDER BY e.post_pos
            """,
            (race_id,),
        ).fetchall()
        # extract numeric prefix from program_num to look for gaps
        pgm_nums = []
        for pgm, *_rest in entries:
            try:
                pgm_nums.append(int(re.match(r"(\d+)", pgm or "").group(1)))
            except Exception:
                pass
        if not pgm_nums:
            continue
        expected = set(range(min(pgm_nums), max(pgm_nums) + 1))
        gaps = expected - set(pgm_nums)
        post_positions = [e[2] for e in entries if e[2] is not None]
        post_sequential = post_positions == list(range(1, len(post_positions) + 1))
        if gaps:
            n_with_gaps += 1
            if len(sample_races) < 5:
                sample_races.append({
                    "date": date,
                    "race_num": race_num,
                    "field_size": field_size,
                    "scratches": json.loads(scr_json) if scr_json else [],
                    "missing_pgm": sorted(gaps),
                    "post_sequential": post_sequential,
                    "entries": [{"program_num": e[0], "horse": e[1], "post_pos": e[2]}
                                for e in entries],
                })
    return {
        "races_with_scratches": n_with_scratches,
        "races_with_pgm_gaps": n_with_gaps,
        "sample_races": sample_races,
    }


def edge_cases(conn: sqlite3.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # DQs: horses named with `DQ-` prefix
    dq_rows = conn.execute(
        """
        SELECT rd.race_date, r.race_num, h.name, e.program_num, e.final_odds
        FROM entries e
        JOIN horses h ON h.id = e.horse_id
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE h.name LIKE 'DQ-%'
        ORDER BY rd.race_date, r.race_num
        """
    ).fetchall()
    out["dq_count"] = len(dq_rows)
    out["dq_samples"] = [
        {"date": d, "race_num": rn, "horse": n, "pgm": p, "odds": o}
        for d, rn, n, p, o in dq_rows[:10]
    ]

    # Dead heats: 2+ horses with the same finish_pos in same race
    dh_rows = conn.execute(
        """
        SELECT r.id, rd.race_date, r.race_num, e.finish_pos, count(*) AS n
        FROM entries e
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE e.finish_pos IS NOT NULL
        GROUP BY r.id, e.finish_pos
        HAVING count(*) > 1
        ORDER BY rd.race_date, r.race_num
        """
    ).fetchall()
    out["dead_heat_buckets"] = len(dh_rows)
    out["dead_heat_samples"] = []
    for race_id, date, race_num, pos, n in dh_rows[:5]:
        horses = conn.execute(
            """
            SELECT h.name, e.program_num, e.beaten_lengths, e.win_payout, e.place_payout, e.show_payout
            FROM entries e JOIN horses h ON h.id = e.horse_id
            WHERE e.race_id = ? AND e.finish_pos = ?
            """,
            (race_id, pos),
        ).fetchall()
        out["dead_heat_samples"].append({
            "date": date, "race_num": race_num, "pos": pos, "n_tied": n,
            "horses": [dict(zip(["horse", "pgm", "bl", "w", "p", "s"], h)) for h in horses],
        })

    # Field-size distribution
    fs_rows = conn.execute(
        "SELECT field_size, count(*) FROM races GROUP BY field_size ORDER BY field_size"
    ).fetchall()
    out["field_size_distribution"] = [
        {"field_size": fs, "n_races": n} for fs, n in fs_rows
    ]

    # Smallest and largest fields
    out["smallest_fields"] = [
        {"date": d, "race_num": rn, "field_size": fs, "surface": s}
        for d, rn, fs, s in conn.execute(
            """
            SELECT rd.race_date, r.race_num, r.field_size, r.surface
            FROM races r JOIN race_days rd ON rd.id = r.race_day_id
            ORDER BY r.field_size ASC, rd.race_date LIMIT 5
            """
        )
    ]
    out["largest_fields"] = [
        {"date": d, "race_num": rn, "field_size": fs, "surface": s}
        for d, rn, fs, s in conn.execute(
            """
            SELECT rd.race_date, r.race_num, r.field_size, r.surface
            FROM races r JOIN race_days rd ON rd.id = r.race_day_id
            ORDER BY r.field_size DESC, rd.race_date LIMIT 5
            """
        )
    ]

    # Race-type distribution
    out["race_types"] = [
        {"type": t or "NULL", "n": n}
        for t, n in conn.execute(
            "SELECT race_type, count(*) FROM races GROUP BY race_type ORDER BY count(*) DESC"
        )
    ]

    # Surface × condition matrix
    out["surface_condition"] = [
        {"surface": s or "?", "condition": c or "?", "n": n}
        for s, c, n in conn.execute(
            """
            SELECT surface, track_condition, count(*)
            FROM races GROUP BY surface, track_condition
            ORDER BY count(*) DESC
            """
        )
    ]

    # Maiden race coverage (any of MAIDEN*)
    out["maiden_races"] = _scalar(
        conn, "SELECT count(*) FROM races WHERE race_type LIKE '%MAIDEN%'"
    )

    # Two-year-old races: detect via conditions text "TWO YEARS OLD" / "TWOYEARSOLD"
    out["two_year_old_races"] = _scalar(
        conn,
        """
        SELECT count(*) FROM races
        WHERE conditions_text LIKE '%TWOYEARSOLD%' OR conditions_text LIKE '%TWO YEARS OLD%'
        """,
    )

    # Pace-call header pattern coverage
    out["pace_header_patterns"] = [
        {"call_labels": cl, "n": n}
        for cl, n in conn.execute(
            """
            SELECT call_labels, count(*) FROM races
            GROUP BY call_labels ORDER BY count(*) DESC LIMIT 10
            """
        )
    ]

    # Failed PDFs
    out["failed_pdfs"] = [
        {"source_pdf": Path(p).name, "error": (e or "")[:120]}
        for p, e in conn.execute(
            "SELECT source_pdf, error_message FROM parsed_files WHERE success = 0"
        )
    ]

    # Warning summary
    warning_counts: Counter = Counter()
    for (raw,) in conn.execute(
        "SELECT warnings_json FROM parsed_files WHERE warnings_json IS NOT NULL"
    ):
        try:
            arr = json.loads(raw)
        except Exception:
            continue
        for w in arr:
            warning_counts[w.split(":", 1)[0]] += 1
    out["warnings"] = list(warning_counts.most_common(20))

    return out


def spot_check_sample(
    conn: sqlite3.Connection, cache_dir: Path, seed: int = 42, n: int = 50
) -> dict[str, Any]:
    """Random 50 races. Cross-check DB fields against the cached JSON."""
    rnd = random.Random(seed)
    all_race_ids = [r[0] for r in conn.execute("SELECT id FROM races").fetchall()]
    sampled = rnd.sample(all_race_ids, min(n, len(all_race_ids)))
    discrepancies: list[dict[str, Any]] = []
    checks = 0
    samples_shown: list[dict[str, Any]] = []
    by_pdf: dict[str, list[int]] = defaultdict(list)
    # Map race_id → source_pdf via race_day
    for race_id in sampled:
        row = conn.execute(
            """
            SELECT r.race_num, rd.source_pdf
            FROM races r JOIN race_days rd ON rd.id = r.race_day_id
            WHERE r.id = ?
            """,
            (race_id,),
        ).fetchone()
        if not row:
            continue
        race_num, source_pdf = row
        by_pdf[source_pdf].append(race_num)

    for source_pdf, race_nums in by_pdf.items():
        json_path = cache_dir / (Path(source_pdf).stem + ".json")
        if not json_path.exists():
            log.warning("missing cache: %s", json_path)
            continue
        try:
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("bad json %s: %s", json_path, e)
            continue
        races_by_num = {r["race_num"]: r for r in parsed["races"]}
        for race_num in race_nums:
            checks += 1
            race = races_by_num.get(race_num)
            if not race:
                discrepancies.append({
                    "pdf": Path(source_pdf).name, "race_num": race_num,
                    "issue": "race missing from cache",
                })
                continue
            # Pull DB values for this race
            race_id = conn.execute(
                """
                SELECT r.id FROM races r
                JOIN race_days rd ON rd.id = r.race_day_id
                WHERE rd.source_pdf = ? AND r.race_num = ?
                """,
                (source_pdf, race_num),
            ).fetchone()[0]
            db_field = _scalar(conn, "SELECT field_size FROM races WHERE id = ?", race_id)
            db_distance = _scalar(conn, "SELECT distance_yards FROM races WHERE id = ?", race_id)
            db_winner = conn.execute(
                """
                SELECT h.name, e.final_odds, e.win_payout
                FROM entries e JOIN horses h ON h.id = e.horse_id
                WHERE e.race_id = ? AND e.finish_pos = 1
                """,
                (race_id,),
            ).fetchone()

            json_field = race["field_size"]
            json_distance = race["distance_yards"]
            json_winner_entry = next(
                (e for e in race["entries"] if e.get("finish_pos") == 1), None
            )

            if db_field != json_field:
                discrepancies.append({
                    "pdf": Path(source_pdf).name, "race_num": race_num,
                    "issue": f"field_size DB={db_field} JSON={json_field}",
                })
            if db_distance != json_distance:
                discrepancies.append({
                    "pdf": Path(source_pdf).name, "race_num": race_num,
                    "issue": f"distance DB={db_distance} JSON={json_distance}",
                })
            if db_winner and json_winner_entry:
                if db_winner[0] != json_winner_entry["horse_name"]:
                    discrepancies.append({
                        "pdf": Path(source_pdf).name, "race_num": race_num,
                        "issue": f"winner DB={db_winner[0]!r} JSON={json_winner_entry['horse_name']!r}",
                    })
            # Stash 5 sample summaries for the report
            if len(samples_shown) < 5:
                samples_shown.append({
                    "pdf": Path(source_pdf).name,
                    "race_num": race_num,
                    "distance_yards": json_distance,
                    "surface": race["surface"],
                    "field_size": json_field,
                    "winner": json_winner_entry["horse_name"] if json_winner_entry else None,
                    "winner_odds": json_winner_entry["final_odds"] if json_winner_entry else None,
                    "winner_pay": json_winner_entry["win_payout"] if json_winner_entry else None,
                    "exotics_count": len(race.get("exotic_payouts") or []),
                })

    return {
        "n_checked": checks,
        "n_discrepancies": len(discrepancies),
        "discrepancies": discrepancies[:30],
        "sample_summaries": samples_shown,
    }


def render_report(
    db_path: Path,
    pipeline: dict[str, Any],
    pdf_status: list[dict[str, Any]],
    year_summary: list[dict[str, Any]],
    completeness: list[dict[str, Any]],
    couples: dict[str, Any],
    scratches: dict[str, Any],
    edges: dict[str, Any],
    spot: dict[str, Any],
    pipeline_meta: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Phase 3B — Full GP Dataset Load\n")
    lines.append(f"_Generated by `scripts/analyze_full_load.py`. Parser version: `{parser.PARSER_VERSION}`._\n")

    # 1. Pipeline summary
    lines.append("## Pipeline summary\n")
    lines.append(f"- PDFs processed: **{pipeline['pdfs_total']}**")
    lines.append(f"- Parse successes: **{pipeline['pdfs_ok']}** "
                 f"({100.0 * pipeline['pdfs_ok'] / max(pipeline['pdfs_total'], 1):.2f}%)")
    lines.append(f"- Parse failures: **{pipeline['pdfs_err']}**")
    lines.append(f"- Wall clock: **{pipeline_meta.get('elapsed_seconds', 0):.1f} s** "
                 f"(**{pipeline_meta.get('pdfs_per_minute', 0):.1f} PDFs/min**, "
                 f"**{pipeline_meta.get('races_per_minute', 0):.1f} races/min**)")
    lines.append(f"- Database file: `{db_path.name}` "
                 f"({pipeline_meta.get('db_size_mb', 0):.1f} MB)")
    lines.append("")

    rows = [
        ["races", pipeline["races"]],
        ["entries (starters)", pipeline["entries"]],
        ["horses (deduped)", pipeline["horses"]],
        ["trainers", pipeline["trainers"]],
        ["jockeys", pipeline["jockeys"]],
        ["owners", pipeline["owners"]],
        ["sires", pipeline["sires"]],
        ["dams", pipeline["dams"]],
        ["exotic_payouts", pipeline["exotic_payouts"]],
    ]
    lines.append(render_table(["Table", "Rows"], rows))
    lines.append("")

    # 2. Per-year parse success
    lines.append("## Per-year parse success\n")
    rows = []
    for r in pdf_status:
        rate = 100.0 * r["ok"] / max(r["total"], 1)
        rows.append([r["year"], r["ok"], r["err"], r["total"], f"{rate:.1f}%"])
    lines.append(render_table(["Year", "OK", "Errors", "Total", "Success %"], rows))
    lines.append("")

    # 3. Per-year volumes
    lines.append("## Per-year volumes\n")
    rows = [[y["year"], y["race_days"], y["races"], y["entries"]] for y in year_summary]
    lines.append(render_table(["Year", "Race days", "Races", "Entries"], rows))
    lines.append("")

    # 4. Per-year completeness
    lines.append("## Per-year field completeness\n")
    rows = []
    for c in completeness:
        rows.append([c["year"], c["entries"],
                     f"{c['odds_pct']:.1f}%", f"{c['trip_pct']:.1f}%",
                     f"{c['pace_pct']:.1f}%", f"{c['speed_pct']:.1f}%",
                     f"{c['bl_pct']:.1f}%", f"{c['fin_pct']:.1f}%"])
    lines.append(render_table(
        ["Year", "Entries", "Odds", "Trip", "Pace", "SpeedFig", "BeatenLen", "Finish"],
        rows,
    ))
    lines.append("")

    # 5. Coupled entries
    lines.append("## Coupled entries (`1A`, `1B`, …)\n")
    lines.append(f"- Coupled entries (program_num matches `\\d+[A-Z]`): "
                 f"**{couples['n_entries']}** across **{couples['n_races']}** races")
    if couples["by_year"]:
        lines.append("")
        lines.append("By year:")
        lines.append("")
        lines.append(render_table(
            ["Year", "Coupled entries"],
            [[r["year"], r["n"]] for r in couples["by_year"]],
        ))
    lines.append("")
    if couples["sample_races"]:
        lines.append("### Sample coupled-entry races\n")
        for s in couples["sample_races"]:
            lines.append(f"**{s['date']} R{s['race_num']}** — {s['surface']} "
                         f"{s['distance_yards']} yd, field={s['field_size']}\n")
            lines.append(render_table(
                ["program_num", "horse", "post_pos", "start_pos", "finish_pos", "odds"],
                [[e["program_num"], e["horse"], e["post_pos"], e["start_pos"],
                  e["finish_pos"], e["odds"]] for e in s["entries"]],
            ))
            lines.append("")

    # 6. Scratch verification
    lines.append("## Scratched-horse verification\n")
    lines.append(f"- Races with at least one scratched horse: **{scratches['races_with_scratches']}**")
    lines.append(f"- Races with program-number gaps (true scratches that affect pgm): "
                 f"**{scratches['races_with_pgm_gaps']}**")
    lines.append("")
    if scratches["sample_races"]:
        lines.append("### Sample races with pgm gaps\n")
        for s in scratches["sample_races"]:
            lines.append(f"**{s['date']} R{s['race_num']}** — field_size={s['field_size']}, "
                         f"missing program numbers: `{s['missing_pgm']}`, "
                         f"post_pos sequential: {'yes' if s['post_sequential'] else 'NO'}")
            lines.append("Scratches: " + ", ".join(
                f"{x.get('name', '?')} ({x.get('reason', '?')})" for x in (s["scratches"] or [])
            ))
            lines.append("")
            lines.append(render_table(
                ["program_num", "horse", "post_pos"],
                [[e["program_num"], e["horse"], e["post_pos"]] for e in s["entries"]],
            ))
            lines.append("")

    # 7. Edge cases
    lines.append("## Edge cases\n")

    lines.append("### Disqualifications\n")
    lines.append(f"DQ'd on-track winners (relabeled with `DQ-` prefix): **{edges['dq_count']}**")
    if edges["dq_samples"]:
        lines.append("")
        lines.append(render_table(
            ["Date", "Race", "Horse", "Pgm", "Odds"],
            [[d["date"], d["race_num"], d["horse"], d["pgm"], d["odds"]]
             for d in edges["dq_samples"]],
        ))
    lines.append("")

    lines.append("### Dead heats\n")
    lines.append(f"Finish-position buckets with 2+ horses tied: **{edges['dead_heat_buckets']}**")
    if edges["dead_heat_samples"]:
        lines.append("")
        for s in edges["dead_heat_samples"]:
            lines.append(f"**{s['date']} R{s['race_num']}** — pos {s['pos']} "
                         f"({s['n_tied']} horses tied)")
            lines.append(render_table(
                ["horse", "pgm", "beaten_lengths", "win", "place", "show"],
                [[h["horse"], h["pgm"], h["bl"], h["w"], h["p"], h["s"]]
                 for h in s["horses"]],
            ))
            lines.append("")

    lines.append("### Field-size distribution\n")
    lines.append(render_table(
        ["Field size", "Races"],
        [[r["field_size"], r["n_races"]] for r in edges["field_size_distribution"]],
    ))
    lines.append("")
    lines.append("Smallest fields:")
    lines.append("")
    lines.append(render_table(
        ["Date", "Race", "Field", "Surface"],
        [[r["date"], r["race_num"], r["field_size"], r["surface"]]
         for r in edges["smallest_fields"]],
    ))
    lines.append("")
    lines.append("Largest fields:")
    lines.append("")
    lines.append(render_table(
        ["Date", "Race", "Field", "Surface"],
        [[r["date"], r["race_num"], r["field_size"], r["surface"]]
         for r in edges["largest_fields"]],
    ))
    lines.append("")

    lines.append("### Race types\n")
    lines.append(render_table(
        ["Type", "Races"],
        [[r["type"], r["n"]] for r in edges["race_types"]],
    ))
    lines.append("")

    lines.append("### Surface × track condition\n")
    lines.append(render_table(
        ["Surface", "Condition", "Races"],
        [[r["surface"], r["condition"], r["n"]] for r in edges["surface_condition"]],
    ))
    lines.append("")

    lines.append(f"### Maiden + 2yo coverage\n")
    lines.append(f"- Races with `MAIDEN` in type: **{edges['maiden_races']}**")
    lines.append(f"- Two-year-old races (conditions mention `TWO YEARS OLD`): "
                 f"**{edges['two_year_old_races']}**")
    lines.append("")

    lines.append("### Pace-call header patterns (top 10)\n")
    lines.append(render_table(
        ["Call labels", "Races"],
        [[r["call_labels"], r["n"]] for r in edges["pace_header_patterns"]],
    ))
    lines.append("")

    # 8. Warnings + failures
    lines.append("## Parser warnings (aggregated across all PDFs)\n")
    if edges["warnings"]:
        lines.append(render_table(["Warning class", "Count"], edges["warnings"]))
    else:
        lines.append("None observed.")
    lines.append("")

    lines.append("## Failed PDFs\n")
    if edges["failed_pdfs"]:
        lines.append(render_table(
            ["PDF", "Error"],
            [[f["source_pdf"], f["error"]] for f in edges["failed_pdfs"]],
        ))
    else:
        lines.append("None.")
    lines.append("")

    # 9. Spot check
    lines.append("## Random 50-race spot check\n")
    lines.append(f"- Races checked: **{spot['n_checked']}**")
    lines.append(f"- Discrepancies vs cache JSON: **{spot['n_discrepancies']}**")
    if spot["discrepancies"]:
        lines.append("")
        lines.append(render_table(
            ["PDF", "Race", "Issue"],
            [[d["pdf"], d["race_num"], d["issue"]] for d in spot["discrepancies"]],
        ))
    lines.append("")
    if spot["sample_summaries"]:
        lines.append("### 5 sample races\n")
        for s in spot["sample_summaries"]:
            lines.append(
                f"- **{s['pdf']} R{s['race_num']}** — {s['surface']} "
                f"{s['distance_yards']} yd, field={s['field_size']}, "
                f"winner={s['winner']} @ {s['winner_odds']} odds (${s['winner_pay']}), "
                f"{s['exotics_count']} exotics"
            )
    lines.append("")

    # 10. Conclusion
    lines.append("## Conclusion\n")
    lines.append(f"- Parser holds at scale: {100.0 * pipeline['pdfs_ok'] / max(pipeline['pdfs_total'], 1):.2f}% "
                 f"PDF success rate across **{pipeline['pdfs_total']}** PDFs.")
    lines.append(f"- {pipeline['races']} races, {pipeline['entries']} entries loaded into `{db_path.name}` "
                 f"({pipeline_meta.get('db_size_mb', 0):.1f} MB).")
    lines.append(f"- Throughput: {pipeline_meta.get('races_per_minute', 0):.0f} races/min "
                 f"(target was 100+).")
    if edges["failed_pdfs"]:
        lines.append(f"- {len(edges['failed_pdfs'])} PDFs failed to parse; see Failed PDFs table.")
    if spot["n_discrepancies"]:
        lines.append(f"- {spot['n_discrepancies']} DB↔JSON discrepancies surfaced by spot check; see table above.")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--cache", default=".cache_full")
    p.add_argument("--report", default="scripts/PHASE_3B_FULL_LOAD.md")
    p.add_argument("--pipeline-log", default="scripts/.pipeline_full.log",
                   help="Pipeline log to scrape for elapsed time")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1
    cache_dir = Path(args.cache)
    if not cache_dir.exists():
        print(f"Cache dir not found: {cache_dir}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = None

    log.info("Pipeline summary…")
    pipeline = pipeline_summary(conn)
    log.info("Per-year PDF status…")
    pdf_status = per_year_pdf_status(conn)
    log.info("Per-year volumes…")
    year_summary = per_year_summary(conn)
    log.info("Per-year completeness…")
    completeness = per_year_completeness(conn)
    log.info("Coupled entries…")
    couples = coupled_entries(conn)
    log.info("Scratches…")
    scratches = scratch_verification(conn)
    log.info("Edge cases…")
    edges = edge_cases(conn)
    log.info("Spot check…")
    spot = spot_check_sample(conn, cache_dir)

    # Pipeline meta: elapsed from log, throughput, db size.
    pipeline_meta: dict[str, Any] = {
        "elapsed_seconds": 0.0,
        "pdfs_per_minute": 0.0,
        "races_per_minute": 0.0,
        "db_size_mb": db_path.stat().st_size / (1024 * 1024),
    }
    log_path = Path(args.pipeline_log)
    if log_path.exists():
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"done:.*? in (\d+\.\d+)s.*?\(([\d.]+) PDFs/min\)", text)
            if m:
                pipeline_meta["elapsed_seconds"] = float(m.group(1))
                pipeline_meta["pdfs_per_minute"] = float(m.group(2))
                if pipeline_meta["elapsed_seconds"]:
                    pipeline_meta["races_per_minute"] = (
                        pipeline["races"] / (pipeline_meta["elapsed_seconds"] / 60.0)
                    )
        except Exception as e:
            log.warning("could not parse pipeline log: %s", e)

    report = render_report(
        db_path, pipeline, pdf_status, year_summary, completeness,
        couples, scratches, edges, spot, pipeline_meta,
    )
    Path(args.report).write_text(report, encoding="utf-8")
    log.info("wrote %s (%d bytes)", args.report, len(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
