"""Phase 5A: batch-parse the Brisnet PP catalogue and match it to results.

Two steps, both idempotent (drop-and-replace):

``parse``
    Walk the five ``*-pps-files`` directories, run
    ``brisnet_pp_parser.parse_pp_file`` on every PDF, and stage every parsed
    starter into ``pp_entries_raw`` in ``scripts/racing_full.db``. Per-file
    outcomes land in ``pp_parsed_files`` so the failure rate is auditable
    rather than inferred from a missing row count.

``match``
    Join the staged rows to ``entries`` on (track, race_date, race_num,
    horse name) and write the matched ones to ``entry_pp_features``, keyed by
    ``entries.id`` so the DPv1 pipeline can join it like any other feature
    table. Unmatched rows keep their reason in ``pp_entries_raw.match_status``.

Scope note
----------
``racing_full.db`` holds GP + CT + MNR only (Phase 4A). FP and EVD PP files
parse fine and are staged, but there is no result corpus to match them to, so
they are reported separately rather than counted as parser failures.

Usage
-----
    python scripts_dpv1/parse_pp_files.py parse
    python scripts_dpv1/parse_pp_files.py match
    python scripts_dpv1/parse_pp_files.py report
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brisnet_pp_parser import (  # noqa: E402
    PP_FEATURE_COLUMNS, parse_pp_file, track_from_filename,
)

log = logging.getLogger("parse_pp_files")

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
DEFAULT_DB = REPO / "scripts" / "racing_full.db"

PARSER_VERSION = "dpv1-pp-5a.1"

# Where the PP catalogue lives, per track.
PP_DIRS: dict[str, Path] = {
    "CT": REPO / "CharlesTown" / "ct-pps-files",
    "GP": REPO / "Gulfstream Park" / "gp-pps-files",
    "FP": REPO / "Fairmount Park" / "fp-pps-files",
    "EVD": REPO / "Evangeline Downs" / "evd-pps-files",
    "MNR": REPO / "Mountaineer" / "mnr-pps-files",
    "ELP": REPO / "Ellis" / "elp-pps-files",
}

# Tracks with a result corpus in racing_full.db. ELP joined in Phase 6B.
CORPUS_TRACKS = ("GP", "CT", "MNR", "ELP")

RAW_TABLE = "pp_entries_raw"
FILES_TABLE = "pp_parsed_files"
FEATURES_TABLE = "entry_pp_features"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _feature_ddl() -> str:
    cols = ",\n    ".join(
        f'"{c}" {"TEXT" if c == "pp_running_style" else "REAL"}'
        for c in PP_FEATURE_COLUMNS
    )
    return cols


DDL = f"""
DROP TABLE IF EXISTS {RAW_TABLE};
CREATE TABLE {RAW_TABLE} (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_pdf    TEXT NOT NULL,
    track         TEXT NOT NULL,
    race_date     TEXT NOT NULL,
    race_num      INTEGER NOT NULL,
    program_num   TEXT,
    horse_name    TEXT,
    horse_norm    TEXT,
    pp_trainer    TEXT,
    pp_jockey     TEXT,
    pp_sire       TEXT,
    pp_ml_text    TEXT,
    pp_surface    TEXT,
    pp_conditions TEXT,
    entry_id      INTEGER,          -- filled by `match`
    match_status  TEXT,             -- matched / no_race / no_horse / no_corpus
    match_method  TEXT,             -- exact_name / program_num
    {_feature_ddl()}
);
CREATE INDEX idx_{RAW_TABLE}_key
    ON {RAW_TABLE}(track, race_date, race_num, horse_norm);
CREATE INDEX idx_{RAW_TABLE}_entry ON {RAW_TABLE}(entry_id);

DROP TABLE IF EXISTS {FILES_TABLE};
CREATE TABLE {FILES_TABLE} (
    source_pdf     TEXT PRIMARY KEY,
    track          TEXT,
    race_date      TEXT,
    parsed_at      TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    races_found    INTEGER,
    horses_found   INTEGER,
    success        INTEGER NOT NULL,
    error_message  TEXT
);
"""

# Non-dropping variants for --incremental. Derived from DDL by swapping the
# DROP/CREATE pair for CREATE IF NOT EXISTS, so the column list has exactly one
# definition and the two modes cannot produce different schemas.
INCREMENTAL_DDL = (DDL
                   .replace(f"DROP TABLE IF EXISTS {RAW_TABLE};", "")
                   .replace(f"DROP TABLE IF EXISTS {FILES_TABLE};", "")
                   .replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
                   .replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS "))


FEATURES_DDL = f"""
DROP TABLE IF EXISTS {FEATURES_TABLE};
CREATE TABLE {FEATURES_TABLE} (
    entry_id      INTEGER PRIMARY KEY,
    race_id       INTEGER,
    horse_id      INTEGER,
    track         TEXT,
    race_date     TEXT,
    race_num      INTEGER,
    source_pdf    TEXT,
    {_feature_ddl()}
);
CREATE INDEX idx_{FEATURES_TABLE}_race ON {FEATURES_TABLE}(race_id);
"""


def normalize_name(name: str | None) -> str | None:
    """Same key the chart loader uses (scripts/equibase_pdf_parser.py)."""
    if not name:
        return None
    return re.sub(r"[^a-z0-9]+", "", name.lower())


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def iter_pp_files() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for track, d in PP_DIRS.items():
        if not d.is_dir():
            log.warning("missing PP directory: %s", d)
            continue
        for f in sorted(d.glob("*.pdf")):
            # Trust the directory over the filename stem: CT20260618()_4x9PPs.pdf
            # does not follow the TRKxMMDD convention.
            out.append((track_from_filename(f) or track, f))
    return out


def replace_card(conn: sqlite3.Connection, track: str, race_date: str,
                 source_pdf: str) -> tuple[int, set[str]]:
    """Clear one card's staged rows. Returns ``(rows removed, prior sources)``.

    Card-grain replacement rather than row-grain UPSERT on
    ``(track, race_date, race_num, program_num)``, for two reasons.

    The table carries no UNIQUE constraint on that tuple, and adding one is not
    safe: the parser has been observed emitting **two horses on the same
    program number** in one race (``gpx0509a.pdf``, race 1), so a unique index
    would turn a mis-parse into a hard insert failure.

    And row-grain upserting strands rows. A re-parse can legitimately yield a
    *different* set of horses — a scratch dropped, a program number corrected —
    and upserting each row leaves the originals behind. Replacing the card
    reaches the same end state for the natural key while handling the horses
    that disappear.

    This is the same semantics ``load_pp_card.stage_pp_entries`` already uses,
    so the two writers agree.
    """
    prior = {r[0] for r in conn.execute(
        f"SELECT DISTINCT source_pdf FROM {RAW_TABLE} "
        f"WHERE track = ? AND race_date = ?", (track, race_date))}
    n = conn.execute(f"DELETE FROM {RAW_TABLE} WHERE track = ? AND race_date = ?",
                     (track, race_date)).rowcount
    return n, prior - {source_pdf}


def cmd_parse(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    incremental = getattr(args, "incremental", False)
    # Default stays drop-and-replace so existing behaviour is untouched.
    conn.executescript(INCREMENTAL_DDL if incremental else DDL)
    if incremental:
        log.info("incremental mode: existing rows are kept, each parsed card "
                 "replaces only its own")

    files = iter_pp_files()
    log.info("found %d PP files across %d directories", len(files), len(PP_DIRS))

    feat_cols = list(PP_FEATURE_COLUMNS)
    insert_cols = (["source_pdf", "track", "race_date", "race_num",
                    "program_num", "horse_name", "horse_norm", "pp_trainer",
                    "pp_jockey", "pp_sire", "pp_ml_text", "pp_surface",
                    "pp_conditions"] + feat_cols)
    sql = (f"INSERT INTO {RAW_TABLE} ({','.join(insert_cols)}) "
           f"VALUES ({','.join('?' * len(insert_cols))})")

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    n_ok = n_fail = n_rows = n_dup = 0
    for track, path in files:
        t0 = time.perf_counter()
        res = parse_pp_file(path, track)
        ok = res["error"] is None and res["n_horses"] > 0
        err = res["error"] or (None if ok else "parsed 0 horses")
        conn.execute(
            f"INSERT OR REPLACE INTO {FILES_TABLE} VALUES (?,?,?,?,?,?,?,?,?)",
            (path.name, res["track"], res["race_date"], now, PARSER_VERSION,
             len(res["races"]), res["n_horses"], int(ok), err),
        )
        if ok:
            n_ok += 1
            if incremental:
                removed, others = replace_card(
                    conn, res["track"], res["race_date"], path.name)
                if others:
                    # This is how GP 2026-05-09 ended up with 425 rows for an
                    # 85-horse card: five Brisnet products for one day, each
                    # inserted without clearing the last. Replacing the card
                    # prevents it; the warning makes the collision visible so
                    # nobody has to rediscover it from a row count.
                    n_dup += 1
                    log.warning(
                        "  %s %s already staged from %s -- replacing %d row(s); "
                        "one card should have one source",
                        res["track"], res["race_date"],
                        ", ".join(sorted(others)), removed)
            rows = []
            for race in res["races"]:
                for h in race["horses"]:
                    rows.append(
                        [path.name, res["track"], res["race_date"],
                         race["race_num"], str(h["program_num"]),
                         h["horse_name"], normalize_name(h["horse_name"]),
                         h.get("trainer"), h.get("jockey"), h.get("sire"),
                         h.get("ml"), race.get("surface"),
                         race.get("conditions")]
                        + [h.get(c) for c in feat_cols]
                    )
            conn.executemany(sql, rows)
            n_rows += len(rows)
            log.info("  %-28s %s %s  %2d races %3d horses  (%.1fs)",
                     path.name, res["track"], res["race_date"],
                     len(res["races"]), res["n_horses"],
                     time.perf_counter() - t0)
        else:
            n_fail += 1
            log.error("  %-28s FAILED: %s", path.name, err)
        conn.commit()

    log.info("parsed %d/%d files OK, %d failed, %d starters staged",
             n_ok, len(files), n_fail, n_rows)
    if incremental:
        total = conn.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
        dupes = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM {RAW_TABLE} "
            f"GROUP BY track, race_date, race_num, program_num "
            f"HAVING COUNT(*) > 1)").fetchone()[0]
        log.info("incremental: %d row(s) in %s, %d duplicated natural key(s), "
                 "%d card(s) had a competing source", total, RAW_TABLE,
                 dupes, n_dup)
    conn.close()
    return 0


# ---------------------------------------------------------------------------
# match
# ---------------------------------------------------------------------------

MATCH_SQL = f"""
UPDATE {RAW_TABLE}
   SET entry_id = (
        SELECT e.id
          FROM entries e
          JOIN races r      ON r.id = e.race_id
          JOIN race_days rd ON rd.id = r.race_day_id
          JOIN tracks t     ON t.id = rd.track_id
          JOIN horses h     ON h.id = e.horse_id
         WHERE t.code            = {RAW_TABLE}.track
           AND rd.race_date      = {RAW_TABLE}.race_date
           AND r.race_num        = {RAW_TABLE}.race_num
           AND h.normalized_name = {RAW_TABLE}.horse_norm
         LIMIT 1),
       match_method = 'exact_name'
 WHERE track IN ({','.join('?' * len(CORPUS_TRACKS))});
"""


def cmd_match(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    conn.execute(f"UPDATE {RAW_TABLE} SET entry_id = NULL, "
                 f"match_status = NULL, match_method = NULL")
    conn.execute(MATCH_SQL, CORPUS_TRACKS)

    # Classify every unmatched row so "no match" is never a bare number.
    conn.execute(f"""
        UPDATE {RAW_TABLE} SET match_method = NULL WHERE entry_id IS NULL
    """)
    conn.execute(f"""
        UPDATE {RAW_TABLE} SET match_status = 'matched' WHERE entry_id IS NOT NULL
    """)
    conn.execute(f"""
        UPDATE {RAW_TABLE} SET match_status = 'no_corpus'
         WHERE entry_id IS NULL
           AND track NOT IN ({','.join('?' * len(CORPUS_TRACKS))})
    """, CORPUS_TRACKS)
    conn.execute(f"""
        UPDATE {RAW_TABLE} SET match_status = 'no_race'
         WHERE match_status IS NULL
           AND NOT EXISTS (
                SELECT 1 FROM races r
                  JOIN race_days rd ON rd.id = r.race_day_id
                  JOIN tracks t     ON t.id = rd.track_id
                 WHERE t.code       = {RAW_TABLE}.track
                   AND rd.race_date = {RAW_TABLE}.race_date
                   AND r.race_num   = {RAW_TABLE}.race_num)
    """)
    conn.execute(f"""
        UPDATE {RAW_TABLE} SET match_status = 'no_horse'
         WHERE match_status IS NULL
    """)
    conn.commit()

    # ---- one PP file per race-day ------------------------------------------
    # TwinSpires publishes the same card in several products (GP 2026-05-09 has
    # five: a/p/u/y/z). They are not interchangeable — the "Condensed PPs" and
    # "Race Summary" variants number their pages differently and gpx0509a.pdf
    # comes out offset by one race. Rather than let an arbitrary row win a
    # GROUP BY, pick the file that matched the most starters on that day and
    # break ties toward the 'y' product (Ultimate PP's w/ QuickPlay Comments),
    # which the parser targets.
    winners = {}
    for track, day, pdf, n in conn.execute(f"""
            SELECT track, race_date, source_pdf, COUNT(*)
              FROM {RAW_TABLE} WHERE entry_id IS NOT NULL
             GROUP BY track, race_date, source_pdf"""):
        key = (track, day)
        score = (n, Path(pdf).stem.lower().endswith("y"))
        if key not in winners or score > winners[key][1]:
            winners[key] = (pdf, score)
    chosen = sorted(v[0] for v in winners.values())
    log.info("selected %d of %d PP files as the per-race-day source",
             len(chosen), conn.execute(
                 f"SELECT COUNT(DISTINCT source_pdf) FROM {RAW_TABLE} "
                 f"WHERE entry_id IS NOT NULL").fetchone()[0])

    conn.execute(f"UPDATE {RAW_TABLE} SET match_status = 'duplicate_card' "
                 f"WHERE match_status = 'matched' AND source_pdf NOT IN "
                 f"({','.join('?' * len(chosen))})", chosen)
    conn.commit()

    # Project matched rows into the entry-grain feature table.
    conn.executescript(FEATURES_DDL)
    feat_cols = list(PP_FEATURE_COLUMNS)
    conn.execute(f"""
        INSERT INTO {FEATURES_TABLE}
            (entry_id, race_id, horse_id, track, race_date, race_num,
             source_pdf, {','.join(feat_cols)})
        SELECT p.entry_id, e.race_id, e.horse_id, p.track, p.race_date,
               p.race_num, p.source_pdf, {','.join('p.' + c for c in feat_cols)}
          FROM {RAW_TABLE} p
          JOIN entries e ON e.id = p.entry_id
         WHERE p.match_status = 'matched'
         GROUP BY p.entry_id
    """)
    conn.commit()

    for row in conn.execute(
            f"SELECT track, match_status, COUNT(*) FROM {RAW_TABLE} "
            f"GROUP BY track, match_status ORDER BY track, match_status"):
        log.info("  %-4s %-10s %5d", *row)
    n = conn.execute(f"SELECT COUNT(*) FROM {FEATURES_TABLE}").fetchone()[0]
    log.info("%s: %d entries", FEATURES_TABLE, n)
    conn.close()
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    import pandas as pd
    conn = sqlite3.connect(args.db)

    files = pd.read_sql_query(f"SELECT * FROM {FILES_TABLE}", conn)
    print("\n=== PARSE OUTCOME BY TRACK ===")
    g = files.groupby("track").agg(
        files=("source_pdf", "count"), ok=("success", "sum"),
        races=("races_found", "sum"), horses=("horses_found", "sum"))
    g["parse_rate"] = (g["ok"] / g["files"] * 100).round(1)
    print(g.to_string())
    bad = files[files["success"] == 0]
    if len(bad):
        print("\nFailures:")
        print(bad[["source_pdf", "track", "race_date",
                   "error_message"]].to_string(index=False))

    raw = pd.read_sql_query(f"SELECT * FROM {RAW_TABLE}", conn)
    print("\n=== MATCH OUTCOME BY TRACK ===")
    piv = (raw.pivot_table(index="track", columns="match_status",
                           values="id", aggfunc="count", fill_value=0))
    piv["total"] = piv.sum(axis=1)
    if "matched" in piv:
        piv["match_rate"] = (piv["matched"] / piv["total"] * 100).round(1)
    print(piv.to_string())

    corpus = raw[raw["track"].isin(CORPUS_TRACKS)]
    if len(corpus):
        mr = (corpus["match_status"] == "matched").mean() * 100
        print(f"\nMatch rate, all corpus-track PP rows: {mr:.1f}% "
              f"({(corpus['match_status'] == 'matched').sum()}/{len(corpus)})")
        # The honest denominator: PP rows on race-days the corpus actually
        # holds, excluding duplicate products of a card already covered.
        avail = corpus[~corpus["match_status"].isin(
            ["no_race", "duplicate_card"])]
        if len(avail):
            print(f"Match rate, race-days present in corpus: "
                  f"{(avail['match_status'] == 'matched').mean() * 100:.1f}% "
                  f"({(avail['match_status'] == 'matched').sum()}/{len(avail)})"
                  f"  [unmatched here are mostly scratches — a PP card lists "
                  f"entrants, a result chart lists starters]")

    # Completeness: of the DB starters in races the PP catalogue covers, how
    # many got a PP row? This is the number that limits the prediction test,
    # and a dropped horse block shows up here rather than as a failed match.
    print("\n=== COVERAGE OF RESULT RACES ===")
    cov = pd.read_sql_query(f"""
        SELECT t.code AS track, COUNT(DISTINCT r.id) AS races,
               COUNT(e.id) AS starters,
               SUM(CASE WHEN f.entry_id IS NOT NULL THEN 1 ELSE 0 END) AS with_pp
          FROM races r
          JOIN race_days rd ON rd.id = r.race_day_id
          JOIN tracks t     ON t.id = rd.track_id
          JOIN entries e    ON e.race_id = r.id
          LEFT JOIN {FEATURES_TABLE} f ON f.entry_id = e.id
         WHERE r.id IN (SELECT race_id FROM {FEATURES_TABLE})
         GROUP BY t.code""", conn)
    if len(cov):
        cov["pct"] = (cov["with_pp"] / cov["starters"] * 100).round(1)
        print(cov.to_string(index=False))

    print("\n=== UNMATCHED SAMPLE (no_horse) ===")
    nh = raw[raw["match_status"] == "no_horse"]
    print(f"{len(nh)} rows")
    if len(nh):
        print(nh[["track", "race_date", "race_num", "program_num",
                  "horse_name"]].head(30).to_string(index=False))

    feat = pd.read_sql_query(f"SELECT * FROM {FEATURES_TABLE}", conn)
    print(f"\n=== FEATURE COVERAGE ({len(feat)} matched entries) ===")
    if len(feat):
        cov = pd.DataFrame({
            "overall": feat[list(PP_FEATURE_COLUMNS)].notna().mean() * 100})
        for t in CORPUS_TRACKS:
            sub = feat[feat["track"] == t]
            if len(sub):
                cov[t] = sub[list(PP_FEATURE_COLUMNS)].notna().mean() * 100
        cov = cov.round(1).sort_values("overall")
        print(cov.to_string())
        low = cov[cov["overall"] < 50]
        print(f"\n{len(low)} feature(s) below 50% coverage: {list(low.index)}")
    conn.close()
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("parse", cmd_parse), ("match", cmd_match),
                     ("report", cmd_report)):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(DEFAULT_DB))
        if name == "parse":
            s.add_argument(
                "--incremental", action="store_true",
                help="do not drop the table; replace only the cards parsed on "
                     "this run, keeping every other card's rows. Use this to "
                     "add newly acquired PP files without a full rebuild.")
        s.set_defaults(func=fn)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
