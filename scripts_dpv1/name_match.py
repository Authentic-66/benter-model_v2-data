"""Jockey / trainer name matching for PP-loaded cards.

Switch: ``name_match_config.json`` turns it ON for DED cards dated
2026-11-05 onward (approved by Doug 2026-11-04; PHASE_6E). Earlier cards,
other tracks, and any parse with no card date are OFF. For a comparison run,
``BENTER_NAME_MATCH=0`` forces it OFF and ``BENTER_NAME_MATCH=1`` forces it
ON, for any card. When it is off, the PP parser and ``load_pp_card`` behave
exactly as before this module existed.

Why: a Brisnet PP spells people "Barrera Elio J" or "RAMIREZ, JR. JULIO",
while the result charts spell them "Barrera, Elio" and "Ramirez, Jr., Julio".
The corpus key (``normalize_name``: lowercase, punctuation stripped) turns
those into different keys, so the loader created a bare jockey or trainer
row with no history. Every jockey/trainer feature for that horse then fell
back to its prior, and ``new_trainer_flag`` fired. Charts are unaffected.
See tracking/name_matching_validation_2026-11-04.md.

Matching rule (``resolve_person``):
 1. ``exact``: the corpus key already names someone with chart history.
 1b. ``alias``: the PP spelling is listed in ``name_aliases.csv`` and its
    chart name has chart history (for names the rule below cannot link).
 2. Otherwise compare *core keys*: the name with single-letter initials and
    the suffixes Jr/Sr/II/III/IV removed, the rest joined in order
    ("Barrera Elio J" and "Barrera, Elio" are both ``barreraelio``).
    Only people with at least one charted start count as candidates.
    * one candidate -> ``core`` (logged with a note when the suffixes differ);
    * several -> tie-break on the suffix, then on middle initials
      (``core+suffix`` / ``core+initials``);
    * still several, or none -> a new row as before (``ambiguous`` / ``new``).
Every resolution is appended to a JSONL log (``BENTER_NAME_MATCH_LOG``,
default ``scripts_dpv1/logs/name_matches.jsonl``).
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ENV = "BENTER_NAME_MATCH"
LOG_ENV = "BENTER_NAME_MATCH_LOG"
DEFAULT_LOG = Path(__file__).resolve().parent / "logs" / "name_matches.jsonl"
ALIAS_FILE = Path(__file__).resolve().parent / "name_aliases.csv"
CONFIG_FILE = Path(__file__).resolve().parent / "name_match_config.json"
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


ON_VALUES = {"1", "on", "true", "yes"}
OFF_VALUES = {"0", "off", "false", "no"}
_CARD: dict = {"track": None, "date": None}


def set_card(track: str | None, card_date) -> None:
    """Tell the switch which card is being parsed / loaded / scored.
    ``parse_pp_file`` calls this as soon as it knows the track and date, and
    ``card_picks`` at start-up, so every caller in the process agrees."""
    _CARD["track"] = (track or "").upper() or None
    _CARD["date"] = str(card_date)[:10] if card_date else None


def load_config(path: Path = CONFIG_FILE) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def state(track: str | None = None, card_date=None) -> tuple[bool, str]:
    """``(on, why)`` for a card. Precedence:

    1. ``BENTER_NAME_MATCH`` set to 1/on/true/yes or 0/off/false/no: that,
       for any card (the comparison override);
    2. otherwise ``name_match_config.json``: ON for cards on the listed
       tracks dated on or after ``on_from_card_date``, OFF before it;
    3. no card known yet, or no config: OFF.
    """
    raw = os.environ.get(ENV, "").strip().lower()
    if raw in ON_VALUES:
        return True, f"override {ENV}={raw}"
    if raw in OFF_VALUES:
        return False, f"override {ENV}={raw}"
    track = (track or _CARD["track"] or "").upper()
    d = str(card_date)[:10] if card_date else _CARD["date"]
    cfg = load_config()
    start = cfg.get("on_from_card_date")
    tracks = {t.upper() for t in cfg.get("tracks", [])}
    if not start:
        return False, "no config"
    if not d:
        return False, "card date not known"
    if tracks and track not in tracks:
        return False, f"config: {track or '?'} not in {sorted(tracks)}"
    if d >= start:
        return True, f"config: ON from {start}"
    return False, f"config: card before {start}"


def enabled() -> bool:
    return state()[0]


def card_counts(track: str, card_date: str, path: Path | None = None) -> dict | None:
    """Method counts from the LATEST load of this card in the match log
    (``{"alias": n, "new": n, ...}``), or None if the card has no log
    lines (it was loaded with matching OFF)."""
    path = Path(path or os.environ.get(LOG_ENV) or DEFAULT_LOG)
    if not path.exists():
        return None
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("track") == track.upper() and r.get("race_date") == card_date:
                recs.append(r)
    if not recs:
        return None
    last = max(r.get("logged_at", "") for r in recs)
    counts: dict = {}
    for r in recs:
        if r.get("logged_at", "") == last:
            counts[r["method"]] = counts.get(r["method"], 0) + 1
    return counts


def corpus_key(name: str) -> str:
    """Same key as equibase_pdf_parser.normalize_name / db_loader._norm."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def name_parts(name: str) -> tuple[str, str, str]:
    """``(core, suffix, initials)`` for a person's name in either spelling.

    Commas, periods and hyphens split tokens ("C.J." gives two initials,
    "Nava-Marin" and "Nava Marin" both give ``navamarin`` once joined).
    Single letters are initials; Jr/Sr/II/III/IV are the suffix.
    """
    toks = [t for t in re.split(r"[\s,.\-]+", name.lower()) if t]
    toks = [re.sub(r"[^a-z0-9]", "", t) for t in toks]
    core, suffix, initials = [], "", []
    for t in toks:
        if not t:
            continue
        if t in SUFFIXES:
            suffix = t
        elif len(t) == 1:
            initials.append(t)
        else:
            core.append(t)
    return "".join(core), suffix, "".join(sorted(initials))


_HIST_CACHE: dict = {}
_ALIASES: dict = {}


def load_aliases(path: Path = ALIAS_FILE) -> dict:
    """``{(table, pp corpus key): chart name}`` from name_aliases.csv, for
    people the rule cannot link (the charts use a different first name or
    initial, e.g. PP "Calhoun W. Bret" vs chart "Calhoun, W.")."""
    if not _ALIASES and path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                _ALIASES[(r["table"].strip(), corpus_key(r["pp_name"]))] = r["chart_name"].strip()
    return _ALIASES


def reset_cache() -> None:
    """Call at the start of each card load (the DB may have changed)."""
    _HIST_CACHE.clear()
    _ALIASES.clear()


def _charted_people(conn: sqlite3.Connection, table: str) -> dict:
    """``{core: [(id, name, suffix, initials), ...]}`` for people with a
    charted start (scheduled PP cards excluded). Cached per connection."""
    key = (id(conn), table)
    if key in _HIST_CACHE:
        return _HIST_CACHE[key]
    col = {"jockeys": "jockey_id", "trainers": "trainer_id"}[table]
    rows = conn.execute(
        f"""SELECT x.id, x.name, x.normalized_name FROM {table} x
            WHERE EXISTS (SELECT 1 FROM entries e
                          JOIN races r ON r.id = e.race_id
                          JOIN race_days d ON d.id = r.race_day_id
                          WHERE e.{col} = x.id AND e.finish_pos IS NOT NULL
                            AND d.source_pdf NOT LIKE 'PP-SCHEDULED%')""").fetchall()
    by_core: dict = {}
    by_key = {}
    for pid, nm, nk in rows:
        core, suf, ini = name_parts(nm)
        if core:
            by_core.setdefault(core, []).append((int(pid), nm, suf, ini))
        by_key[nk] = (int(pid), nm)
    _HIST_CACHE[key] = (by_core, by_key)
    return _HIST_CACHE[key]


def resolve_person(conn: sqlite3.Connection, table: str, name: str | None,
                   context: dict | None = None):
    """Return ``(person_id or None, record)``; ``person_id`` None means the
    caller should fall back to its usual get-or-create."""
    rec = {"table": table, "pp_name": name, **(context or {})}
    if not name or name.strip() in {"", "?"}:
        rec.update(method="skip", matched_id=None)
        return None, rec
    by_core, by_key = _charted_people(conn, table)
    exact = by_key.get(corpus_key(name))
    if exact:
        rec.update(method="exact", matched_id=exact[0], matched_name=exact[1])
        return exact[0], rec
    target = load_aliases().get((table, corpus_key(name)))
    if target:
        hit = by_key.get(corpus_key(target))
        if hit:
            rec.update(method="alias", matched_id=hit[0], matched_name=hit[1])
            return hit[0], rec
        rec["note"] = f"alias target '{target}' has no charted start; rule matching used"
    core, suf, ini = name_parts(name)
    cands = by_core.get(core, []) if core else []
    rec["candidates"] = [c[1] for c in cands]
    pick, method = None, None
    if len(cands) == 1:
        pick, method = cands[0], "core"
    elif len(cands) > 1:
        same_suf = [c for c in cands if c[2] == suf]
        if len(same_suf) == 1:
            pick, method = same_suf[0], "core+suffix"
        else:
            pool = same_suf or cands
            same_ini = [c for c in pool if ini and c[3] and c[3] == ini]
            if len(same_ini) == 1:
                pick, method = same_ini[0], "core+initials"
    if pick is None:
        rec.update(method="ambiguous" if cands else "new", matched_id=None)
        return None, rec
    rec.update(method=method, matched_id=pick[0], matched_name=pick[1])
    if pick[2] != suf:
        rec["note"] = f"suffix differs (pp '{suf}' vs chart '{pick[2]}')"
    if ini and pick[3] and pick[3] != ini:
        rec["note"] = (rec.get("note", "") + f" initials differ (pp '{ini}' vs chart '{pick[3]}')").strip()
    return pick[0], rec


def write_log(records: list[dict]) -> Path | None:
    if not records:
        return None
    path = Path(os.environ.get(LOG_ENV) or DEFAULT_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"logged_at": stamp, **r}, default=str) + "\n")
    return path
