"""Phase 4A validation queries for racing_full.db (GP + CT + MNR).

Prints a text report to stdout. Meant to be redirected into the phase report.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main(db_path: str) -> int:
    con = sqlite3.connect(db_path)

    section("Track dimension")
    for row in q(con, "SELECT id, code, name FROM tracks ORDER BY id"):
        print(f"  id={row[0]:>3}  code={row[1]:<4}  name={row[2]}")

    section("Totals per track")
    for row in q(con, """
        SELECT t.code,
               COUNT(DISTINCT rd.id) AS race_days,
               COUNT(DISTINCT r.id)  AS races,
               COUNT(e.id)           AS entries
        FROM tracks t
        LEFT JOIN race_days rd ON rd.track_id = t.id
        LEFT JOIN races     r  ON r.race_day_id = rd.id
        LEFT JOIN entries   e  ON e.race_id = r.id
        GROUP BY t.code
        ORDER BY t.code
    """):
        print(f"  {row[0]:<4}  race_days={row[1]:>5}   races={row[2]:>6}   entries={row[3]:>7}")

    total_races = q(con, "SELECT COUNT(*) FROM races")[0][0]
    total_entries = q(con, "SELECT COUNT(*) FROM entries")[0][0]
    print(f"  {'ALL':<4}  race_days={q(con, 'SELECT COUNT(*) FROM race_days')[0][0]:>5}   "
          f"races={total_races:>6}   entries={total_entries:>7}")

    section("Per-track x per-year race counts")
    print(f"  {'track':<4}  {'year':<6}  {'race_days':>10}  {'races':>8}  {'entries':>8}")
    for row in q(con, """
        SELECT t.code,
               substr(rd.race_date, 1, 4) AS yr,
               COUNT(DISTINCT rd.id) AS days,
               COUNT(DISTINCT r.id)  AS races,
               COUNT(e.id)           AS entries
        FROM tracks t
        JOIN race_days rd ON rd.track_id = t.id
        JOIN races     r  ON r.race_day_id = rd.id
        LEFT JOIN entries e ON e.race_id = r.id
        GROUP BY t.code, yr
        ORDER BY t.code, yr
    """):
        print(f"  {row[0]:<4}  {row[1]:<6}  {row[2]:>10}  {row[3]:>8}  {row[4]:>8}")

    section("Average field size per track")
    for row in q(con, """
        SELECT t.code,
               ROUND(AVG(fs.field_size), 2) AS avg_field,
               MIN(fs.field_size), MAX(fs.field_size)
        FROM tracks t
        JOIN race_days rd ON rd.track_id = t.id
        JOIN races r ON r.race_day_id = rd.id
        JOIN (
            SELECT race_id, COUNT(*) AS field_size FROM entries GROUP BY race_id
        ) fs ON fs.race_id = r.id
        GROUP BY t.code
        ORDER BY t.code
    """):
        print(f"  {row[0]:<4}  avg={row[1]}  min={row[2]}  max={row[3]}")

    section("Favorite win rate per track (odds sanity: healthy ~ 30-40%)")
    for row in q(con, """
        SELECT t.code,
               COUNT(*)                                       AS favorites,
               SUM(CASE WHEN e.finish_pos = 1 THEN 1 ELSE 0 END) AS fav_wins,
               ROUND(100.0 * SUM(CASE WHEN e.finish_pos = 1 THEN 1 ELSE 0 END)
                     / NULLIF(COUNT(*), 0), 2)                AS win_pct
        FROM entries e
        JOIN races r      ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        JOIN tracks t     ON t.id = rd.track_id
        WHERE e.is_favorite = 1
        GROUP BY t.code
        ORDER BY t.code
    """):
        print(f"  {row[0]:<4}  favorites={row[1]:>6}  wins={row[2]:>5}  win%={row[3]}")

    section("Odds coverage per track (share of entries with a final_odds value)")
    for row in q(con, """
        SELECT t.code,
               COUNT(*)                                       AS n_entries,
               SUM(CASE WHEN e.final_odds IS NOT NULL THEN 1 ELSE 0 END) AS n_odds,
               ROUND(100.0 * SUM(CASE WHEN e.final_odds IS NOT NULL THEN 1 ELSE 0 END)
                     / NULLIF(COUNT(*), 0), 2) AS pct
        FROM entries e
        JOIN races r      ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        JOIN tracks t     ON t.id = rd.track_id
        GROUP BY t.code
        ORDER BY t.code
    """):
        print(f"  {row[0]:<4}  entries={row[1]:>7}  with_odds={row[2]:>7}  pct={row[3]}")

    section("Cross-track jockey overlap (jockeys who rode at 2+ tracks)")
    total_jockeys = q(con, "SELECT COUNT(*) FROM jockeys")[0][0]
    rows = q(con, """
        SELECT j.name,
               GROUP_CONCAT(DISTINCT t.code) AS tracks,
               COUNT(DISTINCT t.code) AS n_tracks,
               COUNT(*) AS mounts
        FROM jockeys j
        JOIN entries e     ON e.jockey_id = j.id
        JOIN races r       ON r.id = e.race_id
        JOIN race_days rd  ON rd.id = r.race_day_id
        JOIN tracks t      ON t.id = rd.track_id
        GROUP BY j.id
        HAVING n_tracks >= 2
        ORDER BY n_tracks DESC, mounts DESC
    """)
    print(f"  total jockeys: {total_jockeys}")
    print(f"  jockeys w/ mounts at 2+ tracks: {len(rows)}")
    tri = [r for r in rows if r[2] == 3]
    print(f"  jockeys w/ mounts at all 3 tracks: {len(tri)}")
    print("  top 20 cross-track riders by mount volume:")
    for r in rows[:20]:
        print(f"    {r[0]:<32}  tracks={r[1]:<12}  mounts={r[3]}")

    section("Cross-track trainer overlap (2+ tracks)")
    total_trainers = q(con, "SELECT COUNT(*) FROM trainers")[0][0]
    rows = q(con, """
        SELECT t2.name,
               GROUP_CONCAT(DISTINCT t.code) AS tracks,
               COUNT(DISTINCT t.code) AS n_tracks,
               COUNT(*) AS starts
        FROM trainers t2
        JOIN entries e     ON e.trainer_id = t2.id
        JOIN races r       ON r.id = e.race_id
        JOIN race_days rd  ON rd.id = r.race_day_id
        JOIN tracks t      ON t.id = rd.track_id
        GROUP BY t2.id
        HAVING n_tracks >= 2
        ORDER BY n_tracks DESC, starts DESC
    """)
    print(f"  total trainers: {total_trainers}")
    print(f"  trainers w/ starts at 2+ tracks: {len(rows)}")
    tri = [r for r in rows if r[2] == 3]
    print(f"  trainers w/ starts at all 3 tracks: {len(tri)}")
    print("  top 20 cross-track trainers by start volume:")
    for r in rows[:20]:
        print(f"    {r[0]:<32}  tracks={r[1]:<12}  starts={r[3]}")

    section("Cross-track horse overlap (shippers, 2+ tracks)")
    total_horses = q(con, "SELECT COUNT(*) FROM horses")[0][0]
    rows = q(con, """
        SELECT h.name,
               GROUP_CONCAT(DISTINCT t.code) AS tracks,
               COUNT(DISTINCT t.code) AS n_tracks,
               COUNT(*) AS starts
        FROM horses h
        JOIN entries e     ON e.horse_id = h.id
        JOIN races r       ON r.id = e.race_id
        JOIN race_days rd  ON rd.id = r.race_day_id
        JOIN tracks t      ON t.id = rd.track_id
        GROUP BY h.id
        HAVING n_tracks >= 2
        ORDER BY n_tracks DESC, starts DESC
    """)
    print(f"  total horses: {total_horses}")
    print(f"  horses that raced at 2+ tracks: {len(rows)}")
    tri = [r for r in rows if r[2] == 3]
    print(f"  horses that raced at all 3 tracks: {len(tri)}")
    print("  top 20 shippers by starts:")
    for r in rows[:20]:
        print(f"    {r[0]:<32}  tracks={r[1]:<12}  starts={r[3]}")

    section("Anthony Farrior spot check (Doug's flagged rider)")
    rows = q(con, """
        SELECT t.code,
               COUNT(*) AS mounts,
               SUM(CASE WHEN e.finish_pos = 1 THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN e.finish_pos <= 3 THEN 1 ELSE 0 END) AS itm
        FROM jockeys j
        JOIN entries e     ON e.jockey_id = j.id
        JOIN races r       ON r.id = e.race_id
        JOIN race_days rd  ON rd.id = r.race_day_id
        JOIN tracks t      ON t.id = rd.track_id
        WHERE j.normalized_name = 'farrioranthony'
           OR j.normalized_name = 'farriorata'
           OR j.name LIKE 'Farrior%'
        GROUP BY t.code
        ORDER BY t.code
    """)
    if rows:
        for r in rows:
            print(f"    {r[0]:<4}  mounts={r[1]:>5}  wins={r[2]:>4}  ITM={r[3]:>4}")
    else:
        print("    (no rows)")

    section("Parser file outcomes")
    for row in q(con, """
        SELECT success, COUNT(*) FROM parsed_files GROUP BY success
    """):
        label = "OK" if row[0] == 1 else "FAIL"
        print(f"  {label}: {row[1]}")
    err_rows = q(con, """
        SELECT source_pdf, error_message FROM parsed_files
        WHERE success = 0 ORDER BY source_pdf
    """)
    if err_rows:
        print(f"  failed/skipped files ({len(err_rows)} total, showing first 20):")
        for r in err_rows[:20]:
            print(f"    {Path(r[0]).name}: {r[1]}")

    section("Warnings summary (races that flagged any warning)")
    row = q(con, """
        SELECT COUNT(*) FROM parsed_files
        WHERE warnings_json IS NOT NULL AND success = 1
    """)[0]
    print(f"  PDFs with >=1 warning: {row[0]}")

    con.close()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    raise SystemExit(main(args.db))
