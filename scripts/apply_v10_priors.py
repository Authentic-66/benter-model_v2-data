"""Apply Doug's v10 workbook signals as new features on every entry.

For each entry in ``entries``, we check whether any *approved* v10 signal
fires on that entry's (sire, trainer, jockey) triple under the race
conditions (surface, distance, track). The result is a small set of
signal-flag features that the fundamental model can consume alongside
the existing 67 Phase 3C features.

Feature schema (new table ``entry_v10_flags``, one row per entry):

    entry_id                  PK
    v10_sire_bet              # of matching sire BET signals
    v10_sire_fade             # of matching sire FADE signals
    v10_trainer_bet           # of matching trainer BET signals
    v10_trainer_fade          # of matching trainer FADE signals
    v10_jockey_bet            # of matching jockey BET signals
    v10_jockey_fade           # of matching jockey FADE signals
    v10_universal_fade        1 if this entry is a "universal fade" target
                              (currently: is-leading-jockey at meet)
    v10_signal_score          Weighted sum, BET positive / FADE negative.
                              Weight = confidence tier: iron=3, high=2, med=1.

Signal-matching rules
---------------------
* **Entity matching** is case-insensitive substring: signal name like
  ``"Casse Trainer Turf"`` produces entity token ``"Casse"``, which fires
  on any DB trainer whose canonical name contains ``"Casse"``. This
  matches both ``"Casse, Norm"`` and ``"Casse, Mark"``. Doug flagged some
  signals as trainer-family-wide (e.g., Joseph Jr) and we intentionally
  match wide.

* **Surface conditions** parsed from signal name: "Dirt" / "Turf" /
  "AW" / "Both Surfaces" / "Dirt/AW". If no surface is named, the signal
  fires on any surface.

* **Distance conditions**: "Sprint" (< 1540 yards, ~7f), "Route" (>= 1540y).
  If not named, fires on any distance.

* **Track conditions**: for signals with ``tracks_confirmed`` list and NOT
  ``scope='universal'``, the signal fires only on those tracks. Universal-
  scope signals fire everywhere.

* **Direction override for GP**: signals flagged
  ``gp_direction_needs_review=True`` in Doug's reviewed JSON are treated
  as *fade* at GP (per the notes text "FADE at GP") regardless of the
  primary direction. Confirmed with Doug in the review pass.

Usage
-----
    python apply_v10_priors.py \\
        --db scripts/gp_full.db \\
        --signals scripts/v10_iron_rules_extracted.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


log = logging.getLogger("apply_v10_priors")

CONFIDENCE_WEIGHT = {"iron": 3.0, "high": 2.0, "medium": 1.0}

# Surface tokens present in signal names and how they map to DB surface
SURFACE_TOKEN_MAP = {
    "DIRT": {"Dirt"},
    "TURF": {"Turf"},
    "AW": {"AllWeather", "Tapeta"},
    "ALLWEATHER": {"AllWeather", "Tapeta"},
    "ALL SURFACES": {"Dirt", "Turf", "AllWeather", "Tapeta"},
    "BOTH SURFACES": {"Dirt", "Turf", "AllWeather", "Tapeta"},
    "BOTH": {"Dirt", "Turf", "AllWeather", "Tapeta"},
}

DISTANCE_SPRINT_MAX_YARDS = 1540  # < 7f is sprint, >= 7f is route


# ---------------------------------------------------------------------------
# Signal parsing
# ---------------------------------------------------------------------------

_SURFACE_WORD_RE = re.compile(
    r"\b(TURF|DIRT|AW|ALLWEATHER|ALL SURFACES|BOTH SURFACES|BOTH)\b",
    re.IGNORECASE,
)
_SPRINT_WORD_RE = re.compile(r"\bSPRINT\b", re.IGNORECASE)
_ROUTE_WORD_RE = re.compile(r"\bROUTE\b", re.IGNORECASE)


@dataclass
class ParsedSignal:
    """One v10 signal reduced to matchable predicates."""

    id: str
    signal_type: str            # 'sire' | 'trainer' | 'jockey' | 'universal'
    direction: str              # 'bet' | 'fade'
    entity_token: str | None    # substring to match on entity canonical name
    surfaces: set[str] | None   # DB surface strings; None = any
    distance_category: str | None  # 'sprint' | 'route' | None
    tracks: set[str]            # set of track codes; empty = any
    universal_scope: bool
    confidence_weight: float
    original_signal_name: str


def _extract_entity_token(signal_name: str, signal_type: str) -> str | None:
    """Extract the leading entity token from a signal name.

    Heuristics:
      * Split on whitespace
      * Consume tokens that look like a proper name (title-case words,
        including apostrophes) until a surface/distance/role keyword or
        the token ``at`` is hit.
      * Return the joined result, or None if we can't identify anything.

    Examples:
        "Casse Trainer Turf"     -> "Casse"
        "Joe Bravo at GP"        -> "Joe Bravo"
        "Curlin Dirt Route"      -> "Curlin"
        "Union Rags Dirt Route"  -> "Union Rags"
        "Twirling Candy Sprint"  -> "Twirling Candy"
        "Anthony Farrior"        -> "Anthony Farrior"
        "Leading Jockey Trap"    -> None (universal, no entity)
    """
    if signal_type == "universal":
        return None
    stop_words = {
        "trainer", "trainers", "jockey", "jockeys", "sire", "sires",
        "dirt", "turf", "aw", "allweather", "route", "sprint",
        "at", "both", "surfaces", "surface", "gp",
        # track codes that can appear in signal names as scope qualifiers
        "kee", "bel", "sar", "cd", "op", "sa", "dmr", "aqu", "tam",
        "mth", "mvr", "fp", "ct", "mnr", "pen", "prm", "rp", "cby", "fan",
        "evd", "ded", "fg", "lad", "ind",
    }
    # Drop parentheticals like " (all surfaces)" first
    clean_name = re.sub(r"\s*\([^)]*\)", "", signal_name)
    # Break slash-joined tokens like "Dirt/AW" into separate words
    clean_name = clean_name.replace("/", " ")
    tokens = clean_name.split()
    entity_parts: list[str] = []
    for tok in tokens:
        clean = re.sub(r"[^\w']", "", tok)
        if clean.lower() in stop_words:
            break
        if not clean:
            continue
        entity_parts.append(tok)
    entity = " ".join(entity_parts).strip()
    return entity or None


def _parse_surfaces(signal_name: str) -> set[str] | None:
    matches = _SURFACE_WORD_RE.findall(signal_name)
    if not matches:
        return None
    surfaces: set[str] = set()
    for m in matches:
        for token, mapped in SURFACE_TOKEN_MAP.items():
            if token == m.upper() or token in m.upper():
                surfaces |= mapped
    return surfaces or None


def _parse_distance_category(signal_name: str) -> str | None:
    if _SPRINT_WORD_RE.search(signal_name):
        return "sprint"
    if _ROUTE_WORD_RE.search(signal_name):
        return "route"
    return None


def _parse_signals(signals_json: dict) -> list[ParsedSignal]:
    """Convert Doug's reviewed JSON into matchable ParsedSignal objects.

    Skips signals with ``review_status`` other than 'approved' or 'modified'.
    """
    out: list[ParsedSignal] = []
    for s in signals_json["signals"]:
        if s["review_status"] not in ("approved", "modified"):
            continue
        signal_type = s["signal_type"]
        direction = s["direction"]
        tracks = set(s.get("tracks_confirmed") or [])
        # Handle GP direction override: signals where notes say the sign
        # flips at GP have their primary direction reversed AND GP added
        # to the applicable tracks (originally only the positive tracks
        # were listed in tracks_confirmed).
        if s.get("gp_direction_needs_review"):
            direction = "fade" if direction == "bet" else "bet"
            tracks = {"GP"}    # signal now fires ONLY at GP with flipped dir
        entity_token = _extract_entity_token(s["signal_name"], signal_type)
        surfaces = _parse_surfaces(s["signal_name"])
        distance_cat = _parse_distance_category(s["signal_name"])
        universal = s.get("scope") == "universal" or "ALL" in tracks
        weight = CONFIDENCE_WEIGHT.get(s["confidence"], 1.0)
        out.append(ParsedSignal(
            id=s["id"],
            signal_type=signal_type,
            direction=direction,
            entity_token=entity_token,
            surfaces=surfaces,
            distance_category=distance_cat,
            tracks=tracks - {"ALL"},
            universal_scope=universal,
            confidence_weight=weight,
            original_signal_name=s["signal_name"],
        ))
    return out


# ---------------------------------------------------------------------------
# Matching per entry
# ---------------------------------------------------------------------------

def _match_series(names: pd.Series, token: str | None) -> np.ndarray:
    """Vectorised token-aware substring match against a pandas Series.

    Returns a boolean numpy array of length ``len(names)``; every element
    is ``True`` iff *all* tokens from ``token`` appear as substrings of the
    corresponding row's lowercased name.
    """
    n = len(names)
    if not token:
        return np.zeros(n, dtype=bool)
    parts = [re.sub(r"[^\w']", "", p).lower() for p in token.split()]
    parts = [p for p in parts if p]
    if not parts:
        return np.zeros(n, dtype=bool)
    lower = names.astype("string").str.lower().fillna("")
    mask = np.ones(n, dtype=bool)
    for p in parts:
        mask &= lower.str.contains(p, na=False, regex=False).to_numpy(dtype=bool)
    return mask


def _entity_matches(
    canonical: str | None,
    token: str | None,
) -> bool:
    """All tokens in `token` must appear as substrings of `canonical`.

    The DB stores people as ``"Lastname, Firstname"`` (e.g. ``"Bravo, Joe"``)
    while signals name people as ``"Firstname Lastname"`` (``"Joe Bravo"``).
    A naive substring on the whole thing would miss because the orders
    differ. Splitting on whitespace and requiring EACH signal token to
    appear somewhere in the DB name handles both orderings and single-word
    surnames like ``"Casse"`` (matches ``"Casse, Norm"`` and ``"Casse, Mark"``).
    """
    if canonical is None or token is None:
        return False
    canon_l = canonical.lower()
    for part in token.split():
        clean = re.sub(r"[^\w']", "", part).lower()
        if not clean:
            continue
        if clean not in canon_l:
            return False
    return True


def _distance_matches(dist_yards: float | None, category: str | None) -> bool:
    if category is None:
        return True
    if dist_yards is None or np.isnan(dist_yards):
        return False
    is_sprint = dist_yards < DISTANCE_SPRINT_MAX_YARDS
    return (category == "sprint") == is_sprint


def _surface_matches(surface: str | None, allowed: set[str] | None) -> bool:
    if allowed is None:
        return True
    if surface is None:
        return False
    return surface in allowed


def _track_matches(track_code: str | None, allowed_tracks: set[str],
                    universal: bool) -> bool:
    if universal or not allowed_tracks:
        return True
    if track_code is None:
        return False
    return track_code in allowed_tracks


# ---------------------------------------------------------------------------
# Vectorised per-entry evaluation
# ---------------------------------------------------------------------------

@dataclass
class MatchTally:
    sire_bet: np.ndarray
    sire_fade: np.ndarray
    trainer_bet: np.ndarray
    trainer_fade: np.ndarray
    jockey_bet: np.ndarray
    jockey_fade: np.ndarray
    universal_fade: np.ndarray
    signal_score: np.ndarray


def _tally_matches(
    entries: pd.DataFrame, signals: list[ParsedSignal],
) -> MatchTally:
    n = len(entries)
    tally = MatchTally(
        sire_bet=np.zeros(n, dtype=np.int32),
        sire_fade=np.zeros(n, dtype=np.int32),
        trainer_bet=np.zeros(n, dtype=np.int32),
        trainer_fade=np.zeros(n, dtype=np.int32),
        jockey_bet=np.zeros(n, dtype=np.int32),
        jockey_fade=np.zeros(n, dtype=np.int32),
        universal_fade=np.zeros(n, dtype=np.int32),
        signal_score=np.zeros(n, dtype=np.float64),
    )

    # Precompute normalised strings for the entry columns
    sire_names = entries["sire_name"].astype("string")
    trainer_names = entries["trainer_name"].astype("string")
    jockey_names = entries["jockey_name"].astype("string")
    surfaces = entries["surface"].astype("string")
    tracks = entries["track_code"].astype("string")
    distance = entries["distance_yards"].astype(float)

    # "Leading jockey" definition per Doug's Iron Rule 002: leading jockey
    # at the meet is the tote-heavy overbet. Proxy: jockey with highest
    # starts_30d ranks 1 within their (track, race_date) day.
    # For simplicity we use the field-level rank of jockey_starts_30d
    # already present in entries.
    is_leading_jockey = entries.get("is_leading_jockey", pd.Series(np.zeros(n, dtype=bool)))
    is_leading_jockey = is_leading_jockey.fillna(False).astype(bool).to_numpy()

    for sig in signals:
        # Fast filter: surface / distance / track (broadcasted vectors)
        surf_mask = (
            np.ones(n, dtype=bool)
            if sig.surfaces is None
            else surfaces.isin(sig.surfaces).to_numpy(dtype=bool)
        )
        dist_mask = (
            np.ones(n, dtype=bool)
            if sig.distance_category is None
            else (
                (distance < DISTANCE_SPRINT_MAX_YARDS)
                == (sig.distance_category == "sprint")
            ) & np.isfinite(distance)
        )
        track_mask = (
            np.ones(n, dtype=bool)
            if sig.universal_scope or not sig.tracks
            else tracks.isin(sig.tracks).to_numpy(dtype=bool)
        )
        base_mask = surf_mask & dist_mask & track_mask

        if sig.signal_type == "sire":
            entity_mask = _match_series(sire_names, sig.entity_token)
            fire = base_mask & entity_mask
            if sig.direction == "bet":
                tally.sire_bet += fire.astype(np.int32)
            else:
                tally.sire_fade += fire.astype(np.int32)
        elif sig.signal_type == "trainer":
            entity_mask = _match_series(trainer_names, sig.entity_token)
            fire = base_mask & entity_mask
            if sig.direction == "bet":
                tally.trainer_bet += fire.astype(np.int32)
            else:
                tally.trainer_fade += fire.astype(np.int32)
        elif sig.signal_type == "jockey":
            entity_mask = _match_series(jockey_names, sig.entity_token)
            fire = base_mask & entity_mask
            if sig.direction == "bet":
                tally.jockey_bet += fire.astype(np.int32)
            else:
                tally.jockey_fade += fire.astype(np.int32)
        elif sig.signal_type == "universal":
            # Iron Rule 002: leading jockey overbet
            fire = base_mask & is_leading_jockey
            tally.universal_fade += fire.astype(np.int32)

        # Score: bet is +weight per firing entry, fade is -weight
        sign = 1.0 if sig.direction == "bet" else -1.0
        tally.signal_score += fire.astype(np.float64) * sign * sig.confidence_weight

    return tally


# ---------------------------------------------------------------------------
# Data loading + writing
# ---------------------------------------------------------------------------

def load_entries(conn: sqlite3.Connection) -> pd.DataFrame:
    """Join everything we need to evaluate signals against each entry."""
    log.info("Loading entries with sire/trainer/jockey names…")
    df = pd.read_sql_query(
        """
        SELECT e.id                  AS entry_id,
               e.race_id              AS race_id,
               e.trainer_id           AS trainer_id,
               e.jockey_id            AS jockey_id,
               t.code                 AS track_code,
               r.surface              AS surface,
               r.distance_yards       AS distance_yards,
               h.sire_id              AS sire_id,
               s.name                 AS sire_name,
               tr.name                AS trainer_name,
               jk.name                AS jockey_name
        FROM entries e
        JOIN races r        ON r.id = e.race_id
        JOIN race_days rd   ON rd.id = r.race_day_id
        JOIN tracks t       ON t.id = rd.track_id
        LEFT JOIN horses h  ON h.id = e.horse_id
        LEFT JOIN sires s   ON s.id = h.sire_id
        LEFT JOIN trainers tr ON tr.id = e.trainer_id
        LEFT JOIN jockeys jk  ON jk.id = e.jockey_id
        """,
        conn,
    )
    # Leading-jockey proxy: within (track, race_date), the jockey with the
    # highest starts_30d rank on the race day. We fetch this from the
    # feature table where jockey_starts_30d already exists.
    log.info("Deriving leading-jockey flags per race day…")
    date_stats = pd.read_sql_query(
        """
        SELECT e.id AS entry_id, jk.name AS jockey_name,
               f.jockey_starts_30d AS starts_30d,
               t.code AS track_code, rd.race_date AS race_date
        FROM entries e
        JOIN entry_features_v1 f ON f.entry_id = e.id
        JOIN races r        ON r.id = e.race_id
        JOIN race_days rd   ON rd.id = r.race_day_id
        JOIN tracks t       ON t.id = rd.track_id
        JOIN jockeys jk     ON jk.id = e.jockey_id
        """,
        conn,
    )
    # For each (track, race_date), the jockey with the max starts_30d is
    # "leading". Multiple jockeys with same max all get the flag.
    date_stats["max_starts"] = (
        date_stats.groupby(["track_code", "race_date"])["starts_30d"]
                  .transform("max")
    )
    date_stats["is_leading_jockey"] = (
        date_stats["starts_30d"] == date_stats["max_starts"]
    ).astype(bool)
    df = df.merge(
        date_stats[["entry_id", "is_leading_jockey"]],
        on="entry_id", how="left",
    )
    df["is_leading_jockey"] = df["is_leading_jockey"].fillna(False)
    return df


def write_flags_table(conn: sqlite3.Connection, tally: MatchTally,
                      entries: pd.DataFrame) -> int:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entry_v10_flags (
            entry_id            INTEGER PRIMARY KEY REFERENCES entries(id),
            v10_sire_bet        INTEGER NOT NULL DEFAULT 0,
            v10_sire_fade       INTEGER NOT NULL DEFAULT 0,
            v10_trainer_bet     INTEGER NOT NULL DEFAULT 0,
            v10_trainer_fade    INTEGER NOT NULL DEFAULT 0,
            v10_jockey_bet      INTEGER NOT NULL DEFAULT 0,
            v10_jockey_fade     INTEGER NOT NULL DEFAULT 0,
            v10_universal_fade  INTEGER NOT NULL DEFAULT 0,
            v10_signal_score    REAL    NOT NULL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_v10_flags_score
            ON entry_v10_flags(v10_signal_score);
    """)
    conn.execute("DELETE FROM entry_v10_flags")
    df = pd.DataFrame({
        "entry_id": entries["entry_id"].to_numpy(),
        "v10_sire_bet": tally.sire_bet,
        "v10_sire_fade": tally.sire_fade,
        "v10_trainer_bet": tally.trainer_bet,
        "v10_trainer_fade": tally.trainer_fade,
        "v10_jockey_bet": tally.jockey_bet,
        "v10_jockey_fade": tally.jockey_fade,
        "v10_universal_fade": tally.universal_fade,
        "v10_signal_score": tally.signal_score,
    })
    df.to_sql("entry_v10_flags", conn, if_exists="append", index=False)
    conn.commit()
    return len(df)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _summary(tally: MatchTally) -> dict:
    """Diagnostic summary of firing counts + a quick sanity check."""
    return {
        "n_entries": len(tally.sire_bet),
        "any_signal_fired": int(np.any(
            [tally.sire_bet, tally.sire_fade,
             tally.trainer_bet, tally.trainer_fade,
             tally.jockey_bet, tally.jockey_fade,
             tally.universal_fade], axis=0,
        ).sum()),
        "sire_bet_entries":     int((tally.sire_bet > 0).sum()),
        "sire_fade_entries":    int((tally.sire_fade > 0).sum()),
        "trainer_bet_entries":  int((tally.trainer_bet > 0).sum()),
        "trainer_fade_entries": int((tally.trainer_fade > 0).sum()),
        "jockey_bet_entries":   int((tally.jockey_bet > 0).sum()),
        "jockey_fade_entries":  int((tally.jockey_fade > 0).sum()),
        "universal_fade_entries": int((tally.universal_fade > 0).sum()),
        "signal_score_mean":    float(tally.signal_score.mean()),
        "signal_score_std":     float(tally.signal_score.std()),
        "signal_score_nonzero": int((tally.signal_score != 0).sum()),
    }


def _cli() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--signals", default="scripts/v10_iron_rules_extracted.json")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    signals_doc = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    parsed = _parse_signals(signals_doc)
    approved_total = sum(
        1 for s in signals_doc["signals"]
        if s["review_status"] in ("approved", "modified")
    )
    log.info("Parsed %d approved signals out of %d total.",
             len(parsed), approved_total)

    conn = sqlite3.connect(args.db)
    entries = load_entries(conn)
    log.info("Entries loaded: %d", len(entries))

    log.info("Tallying signal matches…")
    t0 = time.perf_counter()
    tally = _tally_matches(entries, parsed)
    log.info("Match tally done in %.1fs", time.perf_counter() - t0)

    log.info("Writing entry_v10_flags…")
    n = write_flags_table(conn, tally, entries)
    log.info("Wrote %d rows.", n)

    summary = _summary(tally)
    log.info("Summary:")
    for k, v in summary.items():
        log.info("  %-24s %s", k, v)

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
