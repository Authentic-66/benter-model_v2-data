"""Phase 6B: put an unraced card into ``racing_full.db`` so DPv1 can score it.

The problem this solves
----------------------
DPv1's 95 features are built by ``feature_builder_dpv1.py`` from the *result*
corpus — expanding-window trainer rates, shrunk jockey win rates, track bias,
class ladders, prior-start history. Phase 6A measured what happens without
them: a hand-entered card supplies 26 of 95 features, keeps only rho=0.61 of
the full-feature ranking, and changes the top pick in 56% of races. Sparse
entry is not a degraded prediction, it is a different one.

The fix is not to hand-enter more fields. It is to give the feature builder a
row to build against. A Brisnet PP file names the horses, trainers, jockeys and
conditions of a race that has not run yet; that is exactly the input
``entries`` and ``races`` want, minus the results. So this module writes the
card into the database with ``finish_pos`` NULL, and then the ordinary builder
computes the ordinary features for it.

Why this is safe
----------------
The obvious worry is leakage — a future-dated row contaminating the corpus it
is scored against. It cannot, for two independent reasons:

1. Every historical statistic in the DPv1 pipeline is computed over strictly
   *earlier* race dates (``_prior_by_entity_expanding`` and friends). A card
   dated in the future is later than everything, so no existing row can see it.
2. The card carries no results. ``is_win`` and ``is_itm`` derive from
   ``finish_pos``, which is NULL, so even a same-day sibling contributes
   nothing but a row count.

The card is also marked in ``race_days.source_pdf`` as a PP-sourced scheduled
card, so it is distinguishable from a real chart at any later point.

What is approximate
-------------------
A PP header gives conditions as prose (``Clm 30000n2L 1^ Mile (T) 3&up``),
not as the normalised fields a chart provides. ``parse_conditions`` maps that
onto the corpus vocabulary. Two mappings are worth naming because they are
judgement calls rather than lookups:

* ``1^ Mile`` is Brisnet's mangled ``1 1/16``. Confirmed against ELP history:
  117 turf races at 1,870 yards, and no other one-and-something turf distance
  that fits. Encoded in ``FURLONG_WORDS``.
* Race-type tokens are mapped to the chart vocabulary DPv1's ``class_score``
  ladder expects (``MC`` -> MAIDENCLAIMING, ``Moc`` -> MAIDENOPTIONALCLAIMING,
  a stakes name -> STAKES). An unrecognised token is left NULL rather than
  guessed, because ``class_score`` reads race_type and a wrong tier is worse
  than a missing one.

The parser's own ``conditions`` field is not used. It silently returned empty
for two of the nine races on the test card (``TMElPTurfB175K`` and
``Moc 50000`` both defeated its regex), and a race with no conditions gets no
class, no distance and no surface. The header line is re-extracted here from
the raw text instead, where the format is rigidly consistent:

    Ellis Park <conditions> Sunday, August 23, 2026 Race 8

Usage
-----
    python scripts_dpv1/load_pp_card.py inspect Ellis/elp-pps-files/elp0823y.pdf
    python scripts_dpv1/load_pp_card.py load    Ellis/elp-pps-files/elp0823y.pdf
    python scripts_dpv1/load_pp_card.py remove  --track ELP --date 2026-08-23
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

DPV1_DIR_ = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR_))
sys.path.insert(0, str(DPV1_DIR_.parent / "scripts"))

import db_loader  # noqa: E402
from equibase_pdf_parser import normalize_name  # noqa: E402

from brisnet_pp_parser import (  # noqa: E402
    PP_FEATURE_COLUMNS, extract_text, parse_pp_file, track_from_filename,
)

log = logging.getLogger("load_pp_card")

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
DEFAULT_DB = REPO / "scripts" / "racing_full.db"

# Marks a race_day as a PP-sourced card rather than a parsed result chart.
SCHEDULED_TAG = "PP-SCHEDULED"


# ---------------------------------------------------------------------------
# Conditions parsing
# ---------------------------------------------------------------------------

# Brisnet writes fractions as a caret or a unicode vulgar fraction.
FURLONG_WORDS: dict[str, float] = {
    "1^": 8.5,      # 1 1/16 miles -> 8.5f -> 1870y (see module docstring)
    "1¹": 8.5,
    "1": 8.0,
    "1½": 12.0,
    "1¼": 10.0,
    "1⅛": 9.0,
    "1⅜": 11.0,
}

_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅜": 0.375, "⅝": 0.625,
              "⅛": 0.125, "^": 0.0625}

# PP class token -> chart race_type. Ordered longest-first at match time so
# "MC" never swallows "Moc" and "Mdn" never swallows "MdnClm".
RACE_TYPE_TOKENS: list[tuple[str, str]] = [
    ("MOC", "MAIDENOPTIONALCLAIMING"),
    ("MSW", "MAIDENSPECIALWEIGHT"),
    ("MDN", "MAIDENSPECIALWEIGHT"),
    ("MCL", "MAIDENCLAIMING"),
    ("MC", "MAIDENCLAIMING"),
    ("AOC", "ALLOWANCEOPTIONALCLAIMING"),
    ("ALW", "ALLOWANCE"),
    ("STK", "STAKES"),
    ("HCP", "HANDICAP"),
    ("SOC", "STARTEROPTIONALCLAIMING"),
    ("STR", "STARTERALLOWANCE"),
    ("WCL", "WAIVERCLAIMING"),
    ("CLM", "CLAIMING"),
    ("OC", "ALLOWANCEOPTIONALCLAIMING"),
]


def parse_distance(conditions: str) -> tuple[float | None, int | None]:
    """``(furlongs, yards)`` from a PP conditions string."""
    if not conditions:
        return None, None
    c = conditions.replace("Miles", "Mile")

    m = re.search(r"(\d+)?\s*([½¼¾⅜⅝⅛^])?\s*Mile", c)
    if m and "Furlong" not in c:
        whole = float(m.group(1)) if m.group(1) else 1.0
        frac = _FRACTIONS.get(m.group(2) or "", 0.0)
        furlongs = (whole + frac) * 8.0
        return furlongs, int(round(furlongs * 220))

    m = re.search(r"(\d+)\s*([½¼¾⅜⅝⅛^])?\s*Furlong", c)
    if m:
        whole = float(m.group(1))
        frac = _FRACTIONS.get(m.group(2) or "", 0.0)
        furlongs = whole + frac
        return furlongs, int(round(furlongs * 220))
    return None, None


# Rendering artifacts Brisnet drops on the front of headers.
# ™ ® curly-quotes ' ' " " prime marks — all common in y-format PPs.
_HEAD_ARTIFACTS = "™®`´'\"\u2018\u2019\u201C\u201D\u201E\u2032\u2033\u00B4"


def parse_race_type(conditions: str) -> str | None:
    """Map the PP class token onto the chart ``races.race_type`` vocabulary."""
    if not conditions:
        return None
    head = conditions.split()[0] if conditions.split() else ""
    # Strip Unicode prefix artifacts (™ ' etc.) before any matching.
    head = head.lstrip(_HEAD_ARTIFACTS)
    up = head.upper()
    # ASCII "TM" prefix artifact (page rendering, "TMMC" -> "MC")
    if up.startswith("TM") and len(up) > 2:
        up = up[2:]
    for token, race_type in RACE_TYPE_TOKENS:
        if up.startswith(token):
            return race_type
    # A named stakes ("ElPTurfB175K", "LadyBird175k") — no class token at all.
    if re.search(r"\d+K$", up) or "STAKES" in up or up.endswith("S."):
        return "STAKES"
    # Graded stakes without a purse suffix ("CTOaks-G2", "CTClssic-G2").
    if re.search(r"-G[123]\b", up):
        return "STAKES"
    return None

def parse_claiming_price(conditions: str, race_type: str | None) -> int | None:
    """The claiming tag, for the claiming tiers of the class ladder."""
    if not conditions or not race_type or "CLAIMING" not in race_type:
        return None
    m = re.search(r"(\d{4,6})", conditions.split("n")[0])
    return int(m.group(1)) if m else None


def parse_purse(conditions: str, fallback: float | None) -> int | None:
    """Purse from a ``100k`` / ``175K`` / ``102000`` token, else the parser's."""
    if conditions:
        m = re.search(r"(\d+(?:\.\d+)?)\s*[kK]\b", conditions)
        if m:
            return int(float(m.group(1)) * 1000)
    return int(fallback) if fallback else None


# ---------------------------------------------------------------------------
# Header re-extraction
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"QuickPlay\s+Comments\s+(?P<rest>\S.*?)\s+"
    r"(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),\s+"
    r"[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+Race\s+(?P<num>\d+)"
)


def _strip_track_name(segments: list[str]) -> list[str]:
    """Drop the track name that prefixes every header's conditions segment.

    The header runs ``... Comments <Track Name> <conditions> Sunday, ...``, and
    there is no reliable way to tell where a track name ends and a class token
    begins by shape alone — ``Ellis Park Clm 30000`` and ``Fair Grounds Alw``
    have the same form. But the track name is identical on every page of the
    file and the conditions are not, so the shared leading words *are* the
    track name. Taking the common word-prefix across all headers recovers it
    without hardcoding a track list.
    """
    if not segments:
        return segments
    splits = [s.split() for s in segments]
    common = 0
    for i in range(min(len(w) for w in splits)):
        tok = splits[0][i]
        if all(w[i] == tok for w in splits) and i < 4:
            common += 1
        else:
            break
    # Guard: if every header is identical the "common prefix" is the whole
    # line, which would leave nothing. Only strip what looks like a name.
    if common and common < min(len(w) for w in splits):
        return [" ".join(w[common:]) for w in splits]
    return segments


def headers_from_text(text: str) -> dict[int, str]:
    """Race number -> conditions string, taken from the running page header.

    Every page of a Brisnet PP repeats the same header for its race, so the
    first occurrence per race number is taken and the rest ignored.
    """
    found: dict[int, str] = {}
    for line in text.splitlines():
        m = _HEADER_RE.search(line)
        if not m:
            continue
        num = int(m.group("num"))
        if num in found:
            continue
        found[num] = m.group("rest").strip()
    if not found:
        return {}
    nums = sorted(found)
    cleaned = _strip_track_name([found[n] for n in nums])
    # Strip the page artefact prefix ("TMMC 30000" -> "MC 30000").
    return {n: re.sub(r"^TM(?=[A-Z])", "", c).strip()
            for n, c in zip(nums, cleaned)}


def surface_from_conditions(conditions: str, parser_surface: str | None) -> str:
    """``Dirt`` / ``Turf``, matching the chart vocabulary."""
    if conditions and re.search(r"\(\s*T\s*\)|Turf", conditions, re.I):
        return "Turf"
    if parser_surface in ("Turf", "Dirt"):
        return parser_surface
    return "Dirt"


# ---------------------------------------------------------------------------
# Card assembly
# ---------------------------------------------------------------------------

def build_card(pdf: str | Path, track_code: str | None = None) -> dict:
    """Parse a PP file into a DB-ready card."""
    path = Path(pdf)
    parsed = parse_pp_file(path, track_code)
    if parsed["error"]:
        raise SystemExit(f"{path.name}: {parsed['error']}")

    text = extract_text(path)
    headers = headers_from_text(text)

    races = []
    for rc in parsed["races"]:
        num = int(rc["race_num"])
        cond = headers.get(num) or rc.get("conditions") or ""
        race_type = parse_race_type(cond)
        furlongs, yards = parse_distance(cond)
        races.append({
            "race_num": num,
            "conditions": cond,
            "race_type": race_type,
            "surface": surface_from_conditions(cond, rc.get("surface")),
            "distance_yards": yards,
            "distance_furlongs": furlongs,
            "purse": parse_purse(cond, rc.get("class_money")),
            "claiming_price": parse_claiming_price(cond, race_type),
            "horses": rc.get("horses", []),
        })

    return {
        "track": parsed["track"],
        "race_date": parsed["race_date"],
        "source_pdf": str(path),
        "races": races,
        "n_horses": sum(len(r["horses"]) for r in races),
    }


# ---------------------------------------------------------------------------
# Database write
# ---------------------------------------------------------------------------

def _get_or_create(conn: sqlite3.Connection, table: str, name: str | None):
    """Delegate to the loader's own upsert so keys match the corpus exactly.

    ``trainers`` / ``jockeys`` / ``horses`` all key on ``normalized_name``,
    which is produced by ``equibase_pdf_parser.normalize_name``. Reimplementing
    that normalisation here would silently create duplicate rows for
    connections that already exist — and a duplicate trainer has no history,
    which is precisely the thing this module exists to avoid.
    """
    return db_loader._get_or_create(conn, table, name)


def _horse_id(conn: sqlite3.Connection, name: str) -> int | None:
    """Match a PP horse name to an existing horse, else create one.

    A hit is what gives the new entry a real prior-start history to build
    features from. A miss creates a bare row, which is correct for a genuine
    first-time starter and is the honest outcome for a shipper whose past races
    are at tracks outside this corpus.
    """
    if not name or not str(name).strip():
        return None
    return db_loader._get_or_create(conn, "horses", str(name).strip())


def remove_card(conn: sqlite3.Connection, track: str, race_date: str) -> int:
    """Delete a previously loaded scheduled card. Refuses to touch real charts."""
    row = conn.execute(
        """
        SELECT rd.id, rd.source_pdf FROM race_days rd
        JOIN tracks t ON t.id = rd.track_id
        WHERE t.code = ? AND rd.race_date = ?
        """, (track.upper(), race_date)).fetchone()
    if not row:
        return 0
    rd_id, source = int(row[0]), row[1] or ""
    if SCHEDULED_TAG not in source:
        raise SystemExit(
            f"{track} {race_date} is a real result chart (source_pdf={source!r}), "
            "not a scheduled PP card. Refusing to delete it.")
    race_ids = [int(r[0]) for r in conn.execute(
        "SELECT id FROM races WHERE race_day_id = ?", (rd_id,))]
    n = 0
    for rid in race_ids:
        n += conn.execute("DELETE FROM entries WHERE race_id = ?", (rid,)).rowcount
    conn.execute("DELETE FROM races WHERE race_day_id = ?", (rd_id,))
    conn.execute("DELETE FROM race_days WHERE id = ?", (rd_id,))
    return n


def load_card(db: str | Path, card: dict, replace: bool = True) -> dict:
    """Write the card as races + resultless entries. Returns a summary."""
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        track = card["track"]
        race_date = card["race_date"]
        trow = conn.execute("SELECT id FROM tracks WHERE code = ?",
                            (track,)).fetchone()
        if not trow:
            raise SystemExit(
                f"track {track} is not in the database. Load its result "
                f"corpus first — a card with no history behind it scores at "
                f"near-zero feature coverage.")
        track_id = int(trow[0])

        if replace:
            removed = remove_card(conn, track, race_date)
            if removed:
                log.info("replaced existing scheduled card (%d entries)", removed)

        cur = conn.execute(
            "INSERT INTO race_days (track_id, race_date, source_pdf) "
            "VALUES (?, ?, ?)",
            (track_id, race_date, f"{SCHEDULED_TAG}:{card['source_pdf']}"))
        race_day_id = int(cur.lastrowid)

        n_races = n_entries = 0
        for r in card["races"]:
            if not r["horses"]:
                continue
            cur = conn.execute(
                """
                INSERT INTO races (race_day_id, race_num, race_type,
                                   distance_yards, surface, track_condition,
                                   purse, claiming_price, field_size,
                                   conditions_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (race_day_id, r["race_num"], r["race_type"],
                 r["distance_yards"], r["surface"], "Fast",
                 r["purse"], r["claiming_price"], len(r["horses"]),
                 r["conditions"]))
            race_id = int(cur.lastrowid)
            n_races += 1

            for h in r["horses"]:
                conn.execute(
                    """
                    INSERT INTO entries (race_id, horse_id, trainer_id,
                                         jockey_id, program_num, post_pos,
                                         finish_pos, final_odds)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (race_id,
                     _horse_id(conn, h.get("horse_name")),
                     _get_or_create(conn, "trainers", h.get("trainer")),
                     _get_or_create(conn, "jockeys", h.get("jockey")),
                     str(h.get("program_num")),
                     _to_int(h.get("program_num"))))
                n_entries += 1
        conn.commit()
    finally:
        conn.close()

    return {"track": card["track"], "race_date": card["race_date"],
            "races": n_races, "entries": n_entries}


def _to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def known_horse_rate(db: str | Path, card: dict) -> dict:
    """How many of the card's horses already have starts in the corpus.

    This is the number that decides whether the whole exercise was worth it. A
    horse the corpus has never seen gets a bare row and NULL history, so its
    features come out no better than hand entry no matter how good the PP file
    is.
    """
    conn = sqlite3.connect(str(db))
    try:
        total = known = with_starts = 0
        for r in card["races"]:
            for h in r["horses"]:
                total += 1
                name = (h.get("horse_name") or "").strip()
                if not name:
                    continue
                row = conn.execute(
                    "SELECT id FROM horses WHERE normalized_name = ?",
                    (normalize_name(name),)).fetchone()
                if not row:
                    continue
                known += 1
                n = conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE horse_id = ? "
                    "AND finish_pos IS NOT NULL", (int(row[0]),)).fetchone()[0]
                if n:
                    with_starts += 1
    finally:
        conn.close()
    return {"horses": total, "name_in_corpus": known,
            "with_prior_starts": with_starts,
            "pct_with_history": round(100 * with_starts / total, 1) if total else 0.0}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_card(card: dict) -> None:
    print(f"\n{card['track']} {card['race_date']}   "
          f"{len(card['races'])} races, {card['n_horses']} horses")
    print(f"source: {card['source_pdf']}\n")
    rows = [{
        "R": r["race_num"], "horses": len(r["horses"]),
        "surface": r["surface"], "yards": r["distance_yards"],
        "race_type": r["race_type"], "purse": r["purse"],
        "claim": r["claiming_price"],
        "conditions": (r["conditions"] or "")[:46],
    } for r in card["races"]]
    print(pd.DataFrame(rows).to_string(index=False))
    missing = [r["race_num"] for r in card["races"]
               if not r["race_type"] or not r["distance_yards"]]
    if missing:
        print(f"\nWARNING: race_type or distance unresolved for races "
              f"{missing}. class_score and the distance features will be NULL "
              f"for them.")


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("inspect", "load"):
        s = sub.add_parser(name)
        s.add_argument("pdf")
        s.add_argument("--track", default=None)
        s.add_argument("--db", default=str(DEFAULT_DB))

    s = sub.add_parser("remove")
    s.add_argument("--track", required=True)
    s.add_argument("--date", required=True)
    s.add_argument("--db", default=str(DEFAULT_DB))

    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if args.cmd == "remove":
        conn = sqlite3.connect(args.db)
        try:
            n = remove_card(conn, args.track, args.date)
            conn.commit()
        finally:
            conn.close()
        print(f"removed {n} entries")
        return 0

    card = build_card(args.pdf, args.track)
    _print_card(card)

    hist = known_horse_rate(args.db, card)
    print(f"\ncorpus history: {hist['with_prior_starts']}/{hist['horses']} "
          f"horses ({hist['pct_with_history']}%) have prior starts in "
          f"racing_full.db")
    if hist["pct_with_history"] < 50:
        print("  Under half the field has history here. Features for the rest "
              "will be NULL,")
        print("  and their predictions carry the same caveat as hand entry.")

    if args.cmd == "load":
        summary = load_card(args.db, card)
        print(f"\nloaded: {summary['races']} races, {summary['entries']} "
              f"entries into {args.db}")
        print("\nNext: rebuild features so the card gets scored on the full "
              "feature set:")
        print("  python scripts_dpv1/speed_figures_dpv1.py compute")
        print("  python scripts_dpv1/feature_builder_dpv1.py build")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
