"""Equibase result-chart PDF parser.

Phase 3A — Benter Model v2.

Reads a single Equibase standard result-chart PDF (or a directory of them) and
emits a structured dict / JSON document per source file. Designed to be format-
agnostic across years and tracks: parses the chart's logical structure rather
than relying on coordinate positions.

Honest extraction policy:
  * Missing fields become NULL — never imputed, never substituted with defaults.
  * Trip comments are preserved as raw text.
  * Speed figures are NULL when absent (most Equibase standard charts do not
    include them; the PP files in Phase 3B will).
  * Pace calls are stored as raw `<position><margin>` tokens. Feature
    engineering in Phase 3D decides what to do with them.

Filename handling: both `20190101-usa-gp-a-d.standard.pdf` (2019-2023) and
`01.01.26 GP Results.pdf` (2024-2026) are supported. Date and track are first
read from filename, then verified against the chart header text. Header wins
on conflict.

Usage:
  # Parse one PDF, print summary
  python equibase_pdf_parser.py parse <path.pdf> [--json out.json]

  # Parse a directory tree, write per-PDF JSON sidecars to a cache dir
  python equibase_pdf_parser.py batch <directory> --cache <cache_dir> [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

PARSER_VERSION = "0.1.0"

log = logging.getLogger("equibase_parser")


# ---------------------------------------------------------------------------
# Filename / date normalization
# ---------------------------------------------------------------------------

# 2019-2023 standard: 20190101-usa-gp-a-d.standard.pdf
_FN_STANDARD = re.compile(
    r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})-(?P<country>[a-z]{2,3})-(?P<track>[a-z]{2,4})",
    re.IGNORECASE,
)
# 2024-2026 doug naming: 01.01.26 GP Results.pdf
_FN_DOUG = re.compile(
    r"^(?P<m>\d{1,2})\.(?P<d>\d{1,2})\.(?P<y>\d{2,4})\s+(?P<track>[A-Za-z]{2,4})\s+Results",
    re.IGNORECASE,
)
# 2026 alternate doug naming: GP020126.pdf, GP041626USA.pdf
_FN_COMPACT = re.compile(
    r"^(?P<track>[A-Z]{2,4})(?P<m>\d{2})(?P<d>\d{2})(?P<y>\d{2})(?:USA)?\.pdf$",
    re.IGNORECASE,
)


@dataclass
class FilenameInfo:
    track_code: str | None = None
    date_iso: str | None = None
    naming_convention: str = "unknown"


def parse_filename(path: Path) -> FilenameInfo:
    """Extract (track_code, ISO date) from filename. Returns blanks on failure."""
    name = path.name
    if (m := _FN_STANDARD.match(name)):
        return FilenameInfo(
            track_code=m.group("track").upper(),
            date_iso=f"{m.group('y')}-{m.group('m')}-{m.group('d')}",
            naming_convention="equibase_standard",
        )
    if (m := _FN_DOUG.match(name)):
        y = m.group("y")
        if len(y) == 2:
            y = "20" + y  # 26 → 2026; safe inside the 21st century
        return FilenameInfo(
            track_code=m.group("track").upper(),
            date_iso=f"{y}-{int(m.group('m')):02d}-{int(m.group('d')):02d}",
            naming_convention="doug_short",
        )
    if (m := _FN_COMPACT.match(name)):
        y = m.group("y")
        if len(y) == 2:
            y = "20" + y
        return FilenameInfo(
            track_code=m.group("track").upper(),
            date_iso=f"{y}-{int(m.group('m')):02d}-{int(m.group('d')):02d}",
            naming_convention="doug_compact",
        )
    return FilenameInfo()


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Jun": 6, "Jul": 7,
    "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def normalize_name(name: str) -> str:
    """Canonical key for dedup: lowercase, strip punctuation/whitespace."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def strip_country_code(name: str) -> tuple[str, str | None]:
    """Split a bloodstock name into (base_name, country_code or None)."""
    m = re.search(r"\(([A-Z]{2,3})\)\s*$", name.strip())
    if m:
        return name[: m.start()].strip(), m.group(1)
    return name.strip(), None


def insert_spaces(camel: str) -> str:
    """Add spaces before capital letters in a CamelCase token.

    `JerseyRose` → `Jersey Rose`, `MrsRamonaG` → `Mrs Ramona G`,
    `D'wildcat` → `D'wildcat` (unchanged, no internal caps).
    """
    # don't split inside apostrophe contractions or single-letter trailing tokens
    out = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", camel)
    out = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", out)
    return out.strip()


def parse_comma_name(name: str) -> str:
    """`Ortiz,Jr.,Irad` → `Ortiz, Jr., Irad`. Just adds spaces after commas."""
    return re.sub(r",(?=\S)", ", ", name).strip()


def to_int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.replace(",", "").replace("$", "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def to_float(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.replace(",", "").replace("$", "").replace("*", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date_long(text: str) -> str | None:
    """`January 1, 2019` → `2019-01-01`."""
    m = re.search(r"(?P<mon>[A-Za-z]+)\s*(?P<d>\d{1,2}),\s*(?P<y>\d{4})", text)
    if not m:
        return None
    mon = _MONTHS.get(m.group("mon"))
    if mon is None:
        return None
    return f"{int(m.group('y')):04d}-{mon:02d}-{int(m.group('d')):02d}"


# ---------------------------------------------------------------------------
# Distance normalization
# ---------------------------------------------------------------------------

_WORD_TO_NUM = {
    "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6,
    "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10, "Eleven": 11, "Twelve": 12,
    "Half": 0.5, "Quarter": 0.25, "Sixteenth": 1 / 16, "Eighth": 0.125,
    "Sixteen": 16, "Seventy": 70,
}

# Yards per unit
_UNIT_YARDS = {
    "Furlong": 220,
    "Furlongs": 220,
    "Mile": 1760,
    "Miles": 1760,
    "Yards": 1,
    "Yard": 1,
}


def _words_to_number(words: list[str]) -> float | None:
    """Convert ['One','And','One','Sixteenth'] → 1.0625 etc.

    Handles 'One And One Half', 'Five And One Half', 'One And Seventy', etc.
    Pretty fragile; falls back to None on anything weird.
    """
    if not words:
        return None
    parts = [w for w in words if w not in ("And", "and")]
    total = 0.0
    i = 0
    while i < len(parts):
        w = parts[i]
        if w in _WORD_TO_NUM:
            v = _WORD_TO_NUM[w]
            # Look ahead for "One Half" / "Three Eighths" patterns
            if i + 1 < len(parts) and parts[i + 1] in _WORD_TO_NUM:
                v2 = _WORD_TO_NUM[parts[i + 1]]
                if v2 < 1:  # combining whole + fraction OR numerator + unit
                    total += v * v2
                    i += 2
                    continue
            total += v
            i += 1
            continue
        return None
    return total if total else None


def normalize_distance(text: str) -> tuple[int | None, str | None]:
    """Convert a distance string like 'Five And One Half Furlongs On The Dirt'
    or 'About Seven And One Half Furlongs On The Turf' or 'One And One
    Sixteenth Miles On The Turf' into (yards, surface).

    Returns (yards_or_None, surface_or_None)."""
    s = text.strip()
    # Surface — must come first since "On The X" is a stable token
    surface = None
    surface_map = [
        ("All Weather", "AllWeather"),
        ("AllWeather", "AllWeather"),
        ("Tapeta Course", "Tapeta"),
        ("TapetaCourse", "Tapeta"),
        ("Tapeta", "Tapeta"),
        ("Turf", "Turf"),
        ("Dirt", "Dirt"),
        ("Main Track", "Dirt"),
    ]
    for keyword, sname in surface_map:
        if re.search(rf"On\s*The\s*{re.escape(keyword)}", s, re.IGNORECASE):
            surface = sname
            break

    # Strip "About " prefix and surface tail
    s_clean = re.sub(r"^About\s+", "", s, flags=re.IGNORECASE)
    s_clean = re.split(r"\s*On\s*The\s*", s_clean, maxsplit=1, flags=re.IGNORECASE)[0]

    # Some descriptions are like "Five And One Half Furlongs", "Seventy Yards" (rare),
    # or "One And One Sixteenth Miles And Seventy Yards"
    # We split on "And" only between unit boundaries.
    # Tokenize CamelCase to words
    words = insert_spaces(s_clean).split()
    # Find unit positions
    unit_positions = [(i, w) for i, w in enumerate(words) if w in _UNIT_YARDS]
    if not unit_positions:
        return None, surface

    yards_total = 0
    last_pos = 0
    for pos, unit in unit_positions:
        chunk = words[last_pos:pos]
        n = _words_to_number(chunk)
        if n is None:
            return None, surface
        yards_total += int(round(n * _UNIT_YARDS[unit]))
        last_pos = pos + 1
        # skip an "And" after the unit if present
        if last_pos < len(words) and words[last_pos] in ("And", "and"):
            last_pos += 1
    return yards_total, surface


# ---------------------------------------------------------------------------
# Race-block splitting
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"(?P<track>[A-Z][A-Z\s\.&'-]*?)\s*-\s*(?P<date>[A-Z][a-z]+\s*\d{1,2},\s*\d{4})\s*-\s*Race\s*(?P<num>\d+)",
)


def split_into_races(full_text: str) -> list[dict[str, Any]]:
    """Find each race block in the concatenated PDF text.

    Returns a list of {header: match-dict, body: str} segments.
    """
    matches = list(_HEADER_RE.finditer(full_text))
    if not matches:
        return []

    blocks: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[body_start:body_end]
        blocks.append(
            {
                "track_text": m.group("track").strip(),
                "date_text": m.group("date").strip(),
                "race_num": int(m.group("num")),
                "body": body,
            }
        )
    return blocks


# ---------------------------------------------------------------------------
# Horse-row parsing
# ---------------------------------------------------------------------------

_HORSE_NAME_PAREN = re.compile(r"^(?P<name>.+?)\((?P<jockey>[^()]+)\)$")
_RUNRECORD_RE = re.compile(r"^(?:---|\d{1,2}[A-Za-z]{3}\d{2}\d{1,2}[A-Z]{2,4}\d{1,2})$")
_ODDS_RE = re.compile(r"^\d+\.\d+\*?$")
_INT_RE = re.compile(r"^\d+$")
# Equipment is either letter codes (`L`, `Lb`, `Lbf`) or "--" meaning none.
_EQUIPMENT_RE = re.compile(r"^(?:[A-Za-z]+|--)$")
_CALL_HEADER_RE = re.compile(
    r"LastRaced\s+Pgm\s+HorseName\(Jockey\)\s+Wgt\s*M/E\s+PP\s+(?P<calls>.+?)\s+Odds\s+Comments?",
)


@dataclass
class CallHeader:
    """Order of pace columns in this race's horse table, e.g. ['Start','1/4','3/8','Str','Fin']."""

    columns: list[str]

    @property
    def n_calls(self) -> int:
        return len(self.columns)


def parse_call_header(header_line: str) -> CallHeader | None:
    """Read 'Start 1/4 3/8 Str Fin' from inside the header line."""
    m = _CALL_HEADER_RE.search(header_line)
    if not m:
        return None
    cols = m.group("calls").split()
    return CallHeader(columns=cols)


def split_horsename_jockey(token: str) -> tuple[str, str | None]:
    """`Liberale(FR)(Lopez,Paco)` → ('Liberale(FR)', 'Lopez, Paco').

    Find the LAST top-level paren group: that's the jockey.
    Everything before is the (possibly country-coded) horse name.
    """
    # find last balanced (...) at end
    if not token.endswith(")"):
        return token, None
    depth = 0
    last_open = None
    for i in range(len(token) - 1, -1, -1):
        c = token[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                last_open = i
                break
    if last_open is None:
        return token, None
    jockey_raw = token[last_open + 1 : -1]
    horse_raw = token[:last_open]
    return horse_raw, parse_comma_name(jockey_raw)


def parse_pace_token(tok: str, field_size: int | None = None) -> tuple[int | None, str | None]:
    """Split a chart pace token into (position, margin_text).

    Examples:
      `64` → (6, '4'),  `1Head` → (1, 'Head'),  `21/2` → (2, '1/2'),
      `15` → (1, '5'),  `2Nose` → (2, 'Nose'),  `7` → (7, None),
      `10` → (10, None),  `101/2` → (10, '1/2'),  `11` → (11, None)

    Disambiguation: a 2-digit token `1X` could mean either "position 1 by X
    lengths" or "position 1X (10-19) by no margin". We use field_size when
    available — positions can never exceed field_size, so `15` in a 7-horse
    race must be position 1 by 5 lengths.
    """
    if tok == "---" or tok == "":
        return None, None
    # Special: exact 2-digit tokens 10..14 are bare positions only when the
    # field is that large and they aren't followed by anything.
    if tok in ("10", "11", "12", "13", "14"):
        n = int(tok)
        if field_size is not None and n > field_size:
            # Must be position 1, margin = second digit
            return 1, tok[1]
        return n, None
    # `10X..14X` where X is more chars: position 10-14, margin X
    m = re.match(r"^(1[0-4])([A-Za-z].*|\d+/\d+|\d+)$", tok)
    if m:
        pos = int(m.group(1))
        margin = m.group(2)
        if field_size is not None and pos > field_size:
            # field too small for pos 10+, fall through to single-digit parse
            pass
        else:
            return pos, margin
    # Single digit position with margin
    m = re.match(r"^([1-9])([A-Za-z].*|\d+/\d+|\d+)?$", tok)
    if m:
        return int(m.group(1)), m.group(2)
    return None, tok


def margin_to_lengths(margin: str | None) -> float | None:
    """Convert margin text into lengths.

    'Head' → 0.1, 'Neck' → 0.25, 'Nose' → 0.05, '1/2' → 0.5, '11/2' → 1.5,
    '213/4' would mean 21 3/4 = 21.75, etc. Returns None when no margin
    information is present (don't impute zero).
    """
    if margin is None or margin == "":
        return None
    m = margin.lower().strip()
    fixed = {"head": 0.1, "neck": 0.25, "nose": 0.05}
    if m in fixed:
        return fixed[m]
    # number with optional fraction: '11/2' = 1 + 1/2, '13/4' = 1 + 3/4
    # but also '1/2' = 0.5 alone
    mat = re.match(r"^(\d+)?(\d/\d)?$", margin)
    if mat:
        whole = int(mat.group(1) or 0)
        frac = 0.0
        if mat.group(2):
            a, b = mat.group(2).split("/")
            frac = int(a) / int(b)
        return whole + frac
    # try generic '21/2' = 2.5 etc by greedy splitting last 'a/b'
    mat = re.match(r"^(\d+?)(\d+)/(\d+)$", margin)
    if mat:
        return int(mat.group(1)) + int(mat.group(2)) / int(mat.group(3))
    return None


def equipment_flags(code: str | None) -> dict[str, int]:
    """Parse Equibase M/E codes.

    L = Lasix, b = blinkers, f = front bandages,
    B = first-time blinkers (uppercase), F = first-time front bandages.
    """
    if not code:
        return {
            "has_lasix": 0, "has_blinkers": 0, "has_front_bandages": 0,
            "first_time_blinkers": 0, "first_time_bandages": 0,
        }
    return {
        "has_lasix": int("L" in code or "l" in code),
        "has_blinkers": int("b" in code or "B" in code),
        "has_front_bandages": int("f" in code or "F" in code),
        "first_time_blinkers": int("B" in code),
        "first_time_bandages": int("F" in code),
    }


def parse_horse_row(row: str, header: CallHeader) -> dict[str, Any] | None:
    """Parse a single horse data line into a dict.

    Strategy: tokenize on whitespace, then identify each field by anchor:
      1. last token group: trip comment (after odds)
      2. odds: first token matching `\\d+\\.\\d+\\*?`
      3. horse(jockey) token: the one ending in ')'
      4. weight: first int after horse token
      5. equipment: optional letter-only token between weight and PP
      6. PP, Start, then N call columns, then odds, then comments
    """
    tokens = row.split()
    if len(tokens) < 6:
        return None

    # find horse(jockey) token — contains a '('
    horse_idx = None
    for i, t in enumerate(tokens):
        if "(" in t and t.endswith(")"):
            horse_idx = i
            break
    if horse_idx is None or horse_idx < 1:
        return None

    last_raced_tokens = tokens[:horse_idx - 1]
    pgm = tokens[horse_idx - 1]
    horse_token = tokens[horse_idx]

    last_raced = " ".join(last_raced_tokens) if last_raced_tokens else None
    horse_raw, jockey = split_horsename_jockey(horse_token)
    horse_name = insert_spaces(horse_raw)
    horse_clean, country = strip_country_code(horse_name)

    # Right of horse token
    rest = tokens[horse_idx + 1 :]
    if not rest:
        return None
    weight = to_int(rest[0])
    if weight is None:
        return None
    rest = rest[1:]
    # Equipment is optional letters-only or "--"; otherwise PP/integer.
    # "--" is the chart's placeholder for "no equipment" (common in chart years
    # where every horse gets neither Lasix nor blinkers).
    equipment = None
    if rest and _EQUIPMENT_RE.match(rest[0]) and not _INT_RE.match(rest[0]):
        if rest[0] != "--":
            equipment = rest[0]
        # else: leave equipment None — flags will all be 0
        rest = rest[1:]

    # Find odds token from left so we can split call columns ↔ comments.
    # In rare rows, pdfplumber glues the Fin-call token and odds together with
    # no whitespace (e.g. `10101/2122.60` for Fin=10 by 10 1/2L + odds 122.60).
    # Fall back to splitting such a glued token.
    odds_idx = None
    odds_token = None
    for i, t in enumerate(rest):
        if _ODDS_RE.match(t):
            odds_idx = i
            odds_token = t
            break
    if odds_idx is None:
        # Try the glued case: find a token ending in `<digits>.<digits>[*]`
        # whose prefix is a valid pace token.
        for i, t in enumerate(rest):
            mg = re.match(r"^(.+?)(\d+\.\d+\*?)$", t)
            if mg and mg.group(1):
                pace_prefix, glued_odds = mg.group(1), mg.group(2)
                # Only accept if the prefix looks like a pace token.
                if re.match(r"^\d+(?:Head|Neck|Nose|\d+/\d+|\d+)?$", pace_prefix):
                    rest[i:i + 1] = [pace_prefix, glued_odds]
                    odds_idx = i + 1
                    odds_token = glued_odds
                    break
        if odds_idx is None:
            return None
    is_fav = odds_token.endswith("*")
    odds_value = to_float(odds_token)

    # Expected layout in `rest`: PP, [Start], *call_columns, ODDS, *comment.
    # "Start" appears in the header for most races but is omitted in some
    # distance races where the first call is taken at 1/4 mile (so the start
    # position simply isn't recorded). Honor whichever header we're given.
    if odds_idx < 1:
        return None
    pp = to_int(rest[0])
    has_start_col = bool(header.columns) and header.columns[0].lower() == "start"
    if has_start_col:
        if odds_idx < 2:
            return None
        start = to_int(rest[1])
        call_values = rest[2:odds_idx]
    else:
        start = None
        call_values = rest[1:odds_idx]
    comment_tokens = rest[odds_idx + 1 :]
    trip_comment = " ".join(comment_tokens) if comment_tokens else None

    # Map call columns to header labels. Header may start with "Start" or
    # directly with the first fractional call.
    pace_calls: dict[str, str] = {}
    if header.columns:
        if has_start_col:
            pace_calls["Start"] = str(start) if start is not None else None
            call_labels_after_start = header.columns[1:]
        else:
            call_labels_after_start = header.columns
        for label, val in zip(call_labels_after_start, call_values):
            pace_calls[label] = val
        # extra unmatched values are stored under numeric keys (defensive)
        if len(call_values) > len(call_labels_after_start):
            for i, val in enumerate(call_values[len(call_labels_after_start) :], start=1):
                pace_calls[f"_extra_{i}"] = val

    # Defer finish-pos / beaten-lengths derivation: we need to know field_size
    # to disambiguate "1X" tokens. parse_race_block does this in a second pass.
    finish_pos: int | None = None
    margin_text: str | None = None
    beaten_lengths: float | None = None

    eq_flags = equipment_flags(equipment)

    return {
        "program_num": pgm,
        "horse_name": horse_clean,
        "horse_country": country,
        "jockey": jockey,
        "last_raced_raw": last_raced,
        "weight_lbs": weight,
        "equipment": equipment,
        **eq_flags,
        "post_pos": pp,
        "start_pos": start,
        "pace_calls": pace_calls,
        "finish_pos": finish_pos,
        "winning_margin_text": margin_text,
        "beaten_lengths": beaten_lengths,
        "final_odds": odds_value,
        "is_favorite": int(is_fav),
        "trip_comment": trip_comment,
        "speed_figure": None,  # not present in standard charts
    }


# ---------------------------------------------------------------------------
# Race-block field extraction
# ---------------------------------------------------------------------------

@dataclass
class RaceParseWarnings:
    items: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.items.append(msg)


def _line_iter(body: str) -> list[str]:
    return [ln.rstrip() for ln in body.splitlines() if ln.strip()]


def _extract_simple(pattern: str, text: str, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _parse_purse(text: str) -> int | None:
    m = re.search(r"Purse:\s*\$?([\d,]+)", text)
    return to_int(m.group(1)) if m else None


def _parse_value_of_race(text: str) -> tuple[int | None, str | None]:
    # Strict comma-grouping so that `$22,4701st$12,600,...` cleanly splits into
    # value=22,470 and breakdown=`1st$12,600,...`.
    m = re.search(r"ValueofRace:\s*\$?(\d{1,3}(?:,\d{3})*|\d+)\s*(.*)", text)
    if not m:
        return None, None
    return to_int(m.group(1)), m.group(2).strip() or None


def _parse_available_money(text: str) -> int | None:
    m = re.search(r"AvailableMoney:\s*\$?([\d,]+)", text)
    return to_int(m.group(1)) if m else None


def _parse_track_record(text: str) -> tuple[str | None, str | None, str | None]:
    """`CurrentTrackRecord:(DiscreetDancer-1:02.34-December3,2011)`."""
    m = re.search(
        r"CurrentTrackRecord:\s*\(([^-]+)-([\d:.]+)-([A-Za-z]+\s*\d{1,2},\s*\d{4})\)",
        text,
    )
    if not m:
        return None, None, None
    return insert_spaces(m.group(1).strip()), m.group(2).strip(), parse_date_long(m.group(3))


def _parse_weather(text: str) -> tuple[str | None, int | None, str | None]:
    m = re.search(r"Weather:\s*([A-Za-z]+),(\d+)\W+Track:\s*([A-Za-z]+)", text)
    if not m:
        return None, None, None
    return m.group(1), to_int(m.group(2)), m.group(3)


def _parse_off_at(text: str) -> tuple[str | None, str | None, str | None]:
    # Split into independent extractions — combining them in one regex causes
    # non-greedy matching to settle for the shortest match without TimingMethod.
    off_at = None
    start_note = None
    timing = None

    mo = re.search(r"Offat:\s*(\d[\d:]*)", text)
    if mo:
        off_at = mo.group(1)

    # Start note: from "Start:" up to either TimingMethod or end-of-line.
    ms = re.search(r"Start:(.+?)(?:\s*TimingMethod:|\n|$)", text)
    if ms:
        start_note = ms.group(1).strip() or None

    # Timing method runs to the end of the line — explicitly stop at newline
    # so we don't suck in the table header that follows on the next line.
    mt = re.search(r"TimingMethod:\s*([^\n\r]+)", text)
    if mt:
        timing = mt.group(1).strip()

    return off_at, start_note, timing


def _parse_fractionals(text: str) -> tuple[list[str], str | None, str | None]:
    """`FractionalTimes:22.56 46.23 59.21 FinalTime:1:05.90 TimefromGate:1:03.65`."""
    m = re.search(
        r"FractionalTimes:\s*([\d:.\s]+?)\s*FinalTime:\s*([\d:.]+)(?:\s*TimefromGate:\s*([\d:.]+))?",
        text,
    )
    if not m:
        return [], None, None
    fracs = [t for t in m.group(1).split() if t]
    return fracs, m.group(2), m.group(3)


def _parse_split_times(text: str) -> list[str]:
    m = re.search(r"SplitTimes:\s*(.+?)$", text, re.MULTILINE)
    if not m:
        return []
    return re.findall(r"\(([^)]+)\)", m.group(1))


def _parse_run_up(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"Run-Up:\s*(\d+)feet(?:TemporaryRail:\s*(\d+)feet)?", text)
    if not m:
        return None, None
    return to_int(m.group(1)), to_int(m.group(2)) if m.group(2) else None


def _parse_distance_line(text: str) -> tuple[str | None, int | None, str | None]:
    # Prefer the form with a track record (clean delimiter). Some races (esp.
    # newer AllWeather meets, or surfaces with no record yet) omit
    # CurrentTrackRecord — fall back to end-of-line.
    m = re.search(r"Distance:\s*(.+?)CurrentTrackRecord:", text)
    if not m:
        m = re.search(r"Distance:\s*(.+?)(?:\n|Purse:|AvailableMoney:)", text)
    if not m:
        return None, None, None
    raw = m.group(1).strip()
    distance_text = insert_spaces(raw)
    yards, surface = normalize_distance(distance_text)
    return distance_text, yards, surface


def _parse_claiming_price(text: str) -> int | None:
    """Pull top claiming price from the conditions line.

    `ClaimingPrice:$12,500` or `ClaimingPrice:$30,000-$25,000`.
    """
    m = re.search(r"ClaimingPrice:\s*\$([\d,]+)", text)
    return to_int(m.group(1)) if m else None


def _parse_winner_pedigree(text: str) -> dict[str, Any]:
    """`Winner: JerseyRose,BayFilly,byMuchoMachoManoutofSweetRedemption,byD'wildcat.FoaledMar17,2016inKentucky.`."""
    out: dict[str, Any] = {}
    m = re.search(
        r"Winner:\s*(?P<name>[^,]+?),(?P<color_sex>[^,]+),by(?P<sire>.+?)outof(?P<dam>.+?),by(?P<dam_sire>.+?)\.Foaled\s*(?P<foaled>[A-Za-z]+\s*\d{1,2},\s*\d{4})(?:\s*in\s*(?P<place>[A-Za-z\s]+?)\.)?",
        text,
    )
    if not m:
        return out
    out["name"] = insert_spaces(m.group("name").strip())
    color_sex = insert_spaces(m.group("color_sex").strip())
    # color is everything except the last word (which is sex)
    parts = color_sex.split()
    if len(parts) >= 2:
        out["color"] = " ".join(parts[:-1])
        out["sex"] = parts[-1]
    out["sire"] = insert_spaces(m.group("sire").strip().lstrip("="))
    out["dam"] = insert_spaces(m.group("dam").strip().lstrip("="))
    out["dam_sire"] = insert_spaces(m.group("dam_sire").strip().lstrip("="))
    out["foaled_date"] = parse_date_long(m.group("foaled"))
    out["foaled_place"] = m.group("place").strip() if m.group("place") else None
    return out


def _parse_breeder_owner_trainer(text: str) -> dict[str, str | None]:
    def _clean(s: str | None) -> str | None:
        if s is None:
            return None
        return insert_spaces(parse_comma_name(s))
    return {
        "breeder": _clean(_extract_simple(r"Breeder:\s*(.+?)$", text, re.MULTILINE)),
        "owner_winner": _clean(_extract_simple(r"^Owner:\s*(.+?)$", text, re.MULTILINE)),
        "trainer_winner": _clean(_extract_simple(r"^Trainer:\s*(.+?)$", text, re.MULTILINE)),
    }


def _parse_scratched(text: str) -> list[dict[str, str | None]]:
    m = re.search(r"ScratchedHorse\(s\):\s*(.+?)(?:TotalWPSPool|Pgm\s+Horse|PastPerformance|Trainers:|Owners:|$)",
                  text, re.DOTALL)
    if not m:
        return []
    raw = m.group(1).strip().rstrip(",").replace("\n", "")
    out: list[dict[str, str | None]] = []
    # Match `Name(Reason)` repeatedly. Allow ',' or end-of-string after the
    # close-paren so the final scratched horse isn't dropped.
    for tok in re.finditer(r"([A-Za-z][A-Za-z'\-\.\s]*?)\(([^)]+)\)", raw):
        name, reason = tok.group(1), tok.group(2)
        out.append({"name": insert_spaces(name.strip()), "reason": reason.strip()})
    return out


def _parse_total_wps_pool(text: str) -> int | None:
    m = re.search(r"TotalWPSPool:\s*\$([\d,]+)", text)
    return to_int(m.group(1)) if m else None


def _parse_payouts_block(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Returns (wps_payouts, exotics, money_columns).

    Payouts block sits between the `Pgm Horse Win [Place] [Show] WagerType ...`
    header line and `PastPerformanceRunningLinePreview` (or similar terminator).

    The `money_columns` list documents which of Win/Place/Show actually exist
    in this chart (small fields without Show, very small fields with only Win).
    Caller uses it to align variable-length amount rows to the correct columns.
    """
    m = re.search(
        r"Pgm\s+Horse\s+(?P<cols>Win(?:\s+Place(?:\s+Show)?)?)\s+WagerType\s+WinningNumbers\s+Payoff\s+Pool(?:\s+Carryover)?\s*\n(?P<block>.+?)(?:PastPerformance|Trainers:|Footnotes)",
        text,
        re.DOTALL,
    )
    wps: list[dict[str, Any]] = []
    exotics: list[dict[str, Any]] = []
    if not m:
        return wps, exotics, ["Win", "Place", "Show"]
    money_columns = m.group("cols").split()
    block = m.group("block")

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Try to split into left-side (WPS) and right-side (exotic). The left
        # side starts with `<pgm> <horsename>` and 1-3 dollar amounts; the right
        # starts with `$<amt>WagerType`.
        # The pdfplumber output puts both halves on the same line separated by
        # spaces. We find the start of the right side by looking for the first
        # `$\d` token; that's where the exotic begins.
        right_match = re.search(r"(\$[\d.]+\S+\s+[\d\-A-Za-z()/]+\s+[\d,.]+(?:\s+[\d,]+)?(?:\s+[\d,]+)?)\s*$", line)
        if right_match:
            right = right_match.group(1).strip()
            left = line[: right_match.start()].strip()
        else:
            right = None
            left = line

        if left:
            # left may be "<pgm> <horse name tokens...> <win> <place> <show>"
            # tokens at the end are dollar amounts (1, 2, or 3 of them)
            ltoks = left.split()
            # collect trailing decimal/integer money tokens
            money_tail: list[str] = []
            while ltoks and re.match(r"^\d+(?:\.\d+)?$", ltoks[-1]):
                money_tail.insert(0, ltoks.pop())
            if ltoks and money_tail:
                pgm = ltoks[0]
                horse_tokens = ltoks[1:] or []
                horse_name = insert_spaces(" ".join(horse_tokens))
                horse_name, _country = strip_country_code(horse_name)
                wps_entry = {"pgm": pgm, "horse_name": horse_name.strip()}
                # money_tail is win/place/show in order
                if len(money_tail) >= 1:
                    wps_entry["win_payout"] = to_float(money_tail[0])
                if len(money_tail) >= 2:
                    wps_entry["place_payout"] = to_float(money_tail[1])
                if len(money_tail) >= 3:
                    wps_entry["show_payout"] = to_float(money_tail[2])
                wps.append(wps_entry)

        if right:
            # Right-side exotic: `$<base><Name> <numbers> <payoff> <pool> [carryover]`
            rm = re.match(
                r"\$(?P<base>[\d.]+)(?P<name>[A-Za-z][A-Za-z0-9\-\s/]*?)\s+(?P<nums>[\d\-A-Za-z()]+?)\s+(?P<payoff>[\d,]+(?:\.\d+)?)(?:\s+(?P<pool>[\d,]+))?(?:\s+(?P<carry>[\d,]+))?\s*$",
                right,
            )
            if rm:
                name_raw = rm.group("name").strip()
                # split qualifier like "(3correct)" off the numbers
                nums_raw = rm.group("nums")
                qual_match = re.search(r"\(([^)]+)\)$", nums_raw)
                qualifier = None
                if qual_match:
                    qualifier = qual_match.group(1)
                    nums_raw = nums_raw[: qual_match.start()]
                wager_name_clean = insert_spaces(name_raw.replace("-", " ")).strip() or name_raw
                exotics.append(
                    {
                        "wager_type": f"${rm.group('base')} {wager_name_clean}",
                        "base_amount": to_float(rm.group("base")),
                        "wager_name": wager_name_clean,
                        "winning_numbers": nums_raw,
                        "qualifier": qualifier,
                        "payoff": to_float(rm.group("payoff")),
                        "pool": to_int(rm.group("pool")),
                        "carryover": to_int(rm.group("carry")),
                    }
                )
    return wps, exotics, money_columns


def _parse_trainers_list(text: str) -> dict[str, str]:
    """`Trainers: 4-Ritvo,Katherine;6-Gold,Stanley;1-Bates,Larry;...`"""
    m = re.search(r"Trainers:\s*(.+?)(?:Owners:|Footnotes|$)", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    raw = m.group(1).replace("\n", "").rstrip(" ;")
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # `4-Ritvo,Katherine`  OR  `4-Joseph,Jr.,Saffie`
        m2 = re.match(r"([0-9A-Za-z]+)\s*-\s*(.+)", chunk)
        if m2:
            out[m2.group(1).strip()] = parse_comma_name(m2.group(2))
    return out


def _parse_owners_list(text: str) -> dict[str, str]:
    m = re.search(r"Owners:\s*(.+?)(?:Footnotes|$)", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    raw = m.group(1).replace("\n", "").rstrip(" ;")
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m2 = re.match(r"([0-9A-Za-z]+)\s*-\s*(.+)", chunk)
        if m2:
            out[m2.group(1).strip()] = m2.group(2).strip()
    return out


def _parse_claimed(text: str) -> list[dict[str, str | None]]:
    """`1ClaimedHorse(s): Mertz NewTrainer:LuisOlivares NewOwner:RubenValdes`.

    Multiple claims appear stacked, e.g.:
      `2ClaimedHorse(s): DaybyDay NewTrainer:Elizabeth NewOwner:Imaginary
       MisschiefMaas NewTrainer:Saffie NewOwner:Collarmele`
    """
    m = re.search(
        r"\d+ClaimedHorse\(s\):\s*(.+?)(?:ClaimingPrices:|ScratchedHorse|TotalWPSPool)",
        text,
        re.DOTALL,
    )
    if not m:
        return []
    out: list[dict[str, str | None]] = []
    block = m.group(1)
    for ch in re.finditer(
        r"([A-Za-z][A-Za-z'\-\(\)\s]+?)\s*NewTrainer:\s*(.+?)\s*NewOwner:\s*(.+?)(?=\s*[A-Z][A-Za-z'\-\(\)]+\s*NewTrainer:|$)",
        block,
        re.DOTALL,
    ):
        out.append(
            {
                "horse_name": insert_spaces(ch.group(1).strip()),
                "new_trainer": insert_spaces(parse_comma_name(ch.group(2).strip())),
                "new_owner": insert_spaces(ch.group(3).strip()),
            }
        )
    return out


def _parse_claiming_prices(text: str) -> dict[str, int]:
    """`ClaimingPrices: 4-JerseyRose:$12,500;6-Mertz:$12,500;...`"""
    m = re.search(r"ClaimingPrices:\s*(.+?)(?:ScratchedHorse|TotalWPSPool|Pgm\s+Horse)", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, int] = {}
    raw = m.group(1).replace("\n", "").rstrip(" ;")
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # `4-JerseyRose:$12,500`
        m2 = re.match(r"([0-9A-Za-z]+)\s*-\s*[^:]+:\s*\$?([\d,]+)", chunk)
        if m2:
            price = to_int(m2.group(2))
            if price is not None:
                out[m2.group(1).strip()] = price
    return out


def _parse_footnotes(text: str) -> str | None:
    m = re.search(
        r"Footnotes\|ViewGlossaryOfTerms\s*(.+?)(?:Copyright\d+|DenotesOBSGraduate|$)",
        text,
        re.DOTALL,
    )
    if not m:
        return None
    return m.group(1).strip()


def _parse_horse_table(body: str, warnings: RaceParseWarnings) -> tuple[CallHeader | None, list[dict[str, Any]]]:
    """Locate the horse table header line, then the rows under it up to
    `FractionalTimes:`.
    """
    lines = body.splitlines()
    header_idx = None
    header = None
    for i, ln in enumerate(lines):
        if "LastRaced" in ln and "HorseName(Jockey)" in ln and "M/E" in ln:
            header = parse_call_header(ln)
            header_idx = i
            break
    if header is None or header_idx is None:
        warnings.add("horse_table_header_not_found")
        return None, []

    entries: list[dict[str, Any]] = []
    for ln in lines[header_idx + 1 :]:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("FractionalTimes:"):
            break
        # Some lines might be artifacts. Try to parse — skip on failure.
        row = parse_horse_row(s, header)
        if row is None:
            warnings.add(f"horse_row_unparsed:{s[:60]}")
            continue
        entries.append(row)
    return header, entries


# ---------------------------------------------------------------------------
# Top-level race assembly
# ---------------------------------------------------------------------------

def parse_race_block(track_text: str, date_iso: str | None, race_num: int, body: str) -> dict[str, Any]:
    """Turn one race block into a structured dict."""
    warnings = RaceParseWarnings()

    distance_text, distance_yards, surface = _parse_distance_line(body)
    purse = _parse_purse(body)
    available_money = _parse_available_money(body)
    value_of_race, value_breakdown = _parse_value_of_race(body)
    tr_holder, tr_time, tr_date = _parse_track_record(body)
    weather, temp, condition = _parse_weather(body)
    off_at, start_note, timing_method = _parse_off_at(body)
    fracs, final_time, time_from_gate = _parse_fractionals(body)
    splits = _parse_split_times(body)
    run_up, temp_rail = _parse_run_up(body)
    winner = _parse_winner_pedigree(body)
    bot = _parse_breeder_owner_trainer(body)
    scratched = _parse_scratched(body)
    total_wps_pool = _parse_total_wps_pool(body)
    wps_payouts, exotics, money_columns = _parse_payouts_block(body)
    trainers_by_pgm = _parse_trainers_list(body)
    owners_by_pgm = _parse_owners_list(body)
    claimed = _parse_claimed(body)
    claiming_by_pgm = _parse_claiming_prices(body)
    footnotes = _parse_footnotes(body)

    # Race-type lines come BEFORE the conditions paragraph. Two forms appear:
    #   `CLAIMING-Thoroughbred`
    #   `STAKESOurDearPeggyS.BlackType-Thoroughbred`  (stakes name appended to
    #     STAKES; mixed case after the leading uppercase category).
    # Match against a known-category list (longest first) rather than a greedy
    # uppercase regex — otherwise `STAKESMaidenS` would capture `STAKESM` as
    # the category because `M` is uppercase.
    _CATEGORIES = (
        "MAIDENSPECIALWEIGHT",
        "MAIDENOPTIONALCLAIMING",
        "MAIDENCLAIMING",
        "ALLOWANCEOPTIONALCLAIMING",
        "STARTEROPTIONALCLAIMING",
        "STARTERHANDICAP",
        "STARTERALLOWANCE",
        "OPTIONALCLAIMING",
        "ALLOWANCE",
        "CLAIMING",
        "HANDICAP",
        "STAKES",
        "TRIAL",
        "MATCH",
    )
    race_type = None
    stakes_name = None
    breed = None
    for ln in body.splitlines()[:8]:
        s = ln.strip()
        if not s:
            continue
        m = re.match(
            r"(.+?)\s*-\s*(Thoroughbred|Quarter\s*Horse|Arabian|Mixed)",
            s,
        )
        if not m:
            continue
        category_blob = m.group(1).strip()
        breed = m.group(2).strip()
        # Try each known category prefix from longest to shortest.
        for cat in _CATEGORIES:
            if category_blob.startswith(cat):
                race_type = insert_spaces(cat)
                tail = category_blob[len(cat):].strip()
                if tail:
                    stakes_name = insert_spaces(tail)
                break
        else:
            # Unknown category — keep raw with spaces inserted.
            race_type = insert_spaces(category_blob)
        break

    # Off-turf detection: if Distance says Turf but Track condition is dirt-typical
    # OR conditions paragraph says "if deemed inadvisable to run this race over the
    # turf course, it will be run on the main track".
    is_off_turf = 0
    if surface == "Turf" and condition and condition.lower() in {"sloppy", "muddy", "fast", "wet", "good"}:
        # ambiguous — only flag if we have evidence from conditions
        is_off_turf = 0
    # Most reliable: look for "main track" phrase + turf words in same paragraph
    if surface == "Turf" and condition in {"Sloppy", "Muddy"}:
        is_off_turf = 1

    conditions_text = _extract_conditions(body)
    claiming_price = _parse_claiming_price(conditions_text or body)

    horse_header, entries = _parse_horse_table(body, warnings)

    # Second-pass: finish position + beaten lengths, now that we know field_size.
    field_size = len(entries)
    if horse_header and horse_header.columns:
        final_label = horse_header.columns[-1]
        for e in entries:
            fin_token = e["pace_calls"].get(final_label) if e.get("pace_calls") else None
            if fin_token is None or fin_token == "---":
                e["finish_pos"] = None
                e["winning_margin_text"] = None
                e["beaten_lengths"] = None
                continue
            pos, margin = parse_pace_token(fin_token, field_size=field_size)
            e["finish_pos"] = pos
            e["winning_margin_text"] = margin
            if pos == 1:
                e["beaten_lengths"] = 0.0
            else:
                e["beaten_lengths"] = margin_to_lengths(margin)

    # Attach trainer/owner names + claiming prices + claim flags onto each entry.
    claimed_horse_names = {normalize_name(c["horse_name"]) for c in claimed if c.get("horse_name")}
    claimed_index = {normalize_name(c["horse_name"]): c for c in claimed if c.get("horse_name")}
    for e in entries:
        pgm = e["program_num"]
        e["trainer"] = trainers_by_pgm.get(pgm)
        e["owner"] = owners_by_pgm.get(pgm)
        e["claiming_price"] = claiming_by_pgm.get(pgm)
        e["claimed_in_race"] = int(normalize_name(e["horse_name"]) in claimed_horse_names)
        if e["claimed_in_race"]:
            c = claimed_index.get(normalize_name(e["horse_name"]), {})
            e["new_trainer_after"] = c.get("new_trainer")
            e["new_owner_after"] = c.get("new_owner")
        else:
            e["new_trainer_after"] = None
            e["new_owner_after"] = None

    # Disambiguate fin-call positions for 10+ horse fields using the WPS table
    # as ground truth. A fin token like `12` in a 12-horse field could mean
    # either "position 12" or "position 1 by 2 lengths"; the WPS payouts tell
    # us which. Whoever earned Win is finish_pos=1; Place+Show alone is 2nd;
    # Show alone is 3rd.
    forced_positions: dict[str, int] = {}
    for p in wps_payouts:
        amounts = [
            p.get(k) for k in ("win_payout", "place_payout", "show_payout")
            if p.get(k) is not None
        ]
        if not amounts:
            continue
        target_cols = [c.lower() for c in money_columns[-len(amounts):]]
        if "win" in target_cols:
            forced_positions[p["pgm"]] = 1
        elif target_cols == ["place", "show"]:
            forced_positions[p["pgm"]] = 2
        elif target_cols == ["show"]:
            forced_positions[p["pgm"]] = 3
        elif target_cols == ["place"]:
            forced_positions[p["pgm"]] = 2

    if horse_header and horse_header.columns and forced_positions:
        final_label = horse_header.columns[-1]
        forced_winner_pgm = next(
            (pgm for pgm, pos in forced_positions.items() if pos == 1), None
        )
        # First pass: apply WPS-derived positions.
        for e in entries:
            forced = forced_positions.get(e["program_num"])
            if forced is None:
                continue
            fin_token = e["pace_calls"].get(final_label) if e.get("pace_calls") else None
            if not fin_token or fin_token == "---":
                continue
            if forced == 1 and fin_token[0] == "1":
                margin = fin_token[1:] or None
                e["finish_pos"] = 1
                e["winning_margin_text"] = margin
                e["beaten_lengths"] = 0.0
            elif forced in (2, 3) and fin_token[0] == str(forced):
                margin = fin_token[1:] or None
                e["finish_pos"] = forced
                e["winning_margin_text"] = margin
                e["beaten_lengths"] = margin_to_lengths(margin)
        # Second pass: WPS is ground truth — clear any naturally-parsed pos=1
        # that contradicts the WPS winner. Rare chart-text artifacts (e.g.
        # pdfplumber merging adjacent table cells) can produce Fin tokens
        # starting with `1` for non-winners. Leave finish_pos NULL rather than
        # guess.
        if forced_winner_pgm is not None:
            for e in entries:
                if e.get("finish_pos") == 1 and e["program_num"] != forced_winner_pgm:
                    e["finish_pos"] = None
                    e["winning_margin_text"] = None
                    e["beaten_lengths"] = None
                    warnings.add(
                        f"contradictory_winner_cleared:pgm={e['program_num']}"
                    )

    # Stitch WPS payouts into corresponding entries. The payouts table reserves
    # 1-3 money columns (Win/Place/Show) depending on field size — small fields
    # drop the Show column, very small fields drop Place too. Each horse row
    # has 0-3 dollar amounts. A horse that finished N-th earns the right-most
    # `count(amounts)` of the available columns:
    #   columns=[Win,Place,Show], amounts=3 → W+P+S (winner)
    #   columns=[Win,Place,Show], amounts=2 → P+S (2nd)
    #   columns=[Win,Place,Show], amounts=1 → S (3rd)
    #   columns=[Win,Place],      amounts=2 → W+P (winner in tiny field)
    #   columns=[Win,Place],      amounts=1 → P (2nd in tiny field)
    wps_by_pgm: dict[str, dict[str, Any]] = {}
    for p in wps_payouts:
        amounts = [
            p.get(k) for k in ("win_payout", "place_payout", "show_payout")
            if p.get(k) is not None
        ]
        assigned = {"win": None, "place": None, "show": None}
        if amounts:
            target_cols = money_columns[-len(amounts):]
            for col, amt in zip(target_cols, amounts):
                assigned[col.lower()] = amt
        wps_by_pgm[p["pgm"]] = assigned

    for e in entries:
        wp = wps_by_pgm.get(e["program_num"])
        if wp:
            e["win_payout"] = wp["win"]
            e["place_payout"] = wp["place"]
            e["show_payout"] = wp["show"]
        else:
            e["win_payout"] = None
            e["place_payout"] = None
            e["show_payout"] = None

    return {
        "race_num": race_num,
        "race_type": race_type,
        "stakes_name": stakes_name,
        "breed": breed,
        "conditions_text": conditions_text,
        "claiming_price": claiming_price,
        "distance_text": distance_text,
        "distance_yards": distance_yards,
        "surface": surface,
        "is_off_turf": is_off_turf,
        "track_condition": condition,
        "purse": purse,
        "available_money": available_money,
        "value_of_race": value_of_race,
        "value_breakdown": value_breakdown,
        "track_record_holder": tr_holder,
        "track_record_time": tr_time,
        "track_record_date": tr_date,
        "weather": weather,
        "temperature_f": temp,
        "off_at": off_at,
        "start_note": start_note,
        "timing_method": timing_method,
        "call_labels": horse_header.columns if horse_header else None,
        "fractional_times": fracs,
        "final_time": final_time,
        "time_from_gate": time_from_gate,
        "split_times": splits,
        "run_up_feet": run_up,
        "temporary_rail_feet": temp_rail,
        "winner": winner,
        "breeder": bot.get("breeder"),
        "owner_winner": bot.get("owner_winner"),
        "trainer_winner": bot.get("trainer_winner"),
        "scratched_horses": scratched,
        "claimed_horses": claimed,
        "claiming_prices_by_pgm": claiming_by_pgm,
        "total_wps_pool": total_wps_pool,
        "field_size": len(entries),
        "entries": entries,
        "wps_payouts": wps_payouts,
        "exotic_payouts": exotics,
        "footnotes": footnotes,
        "warnings": warnings.items,
    }


def _extract_conditions(body: str) -> str | None:
    """The conditions paragraph lives between the breed line and the
    `Distance:` line. We grab everything in between."""
    m = re.search(
        r"-\s*(?:Thoroughbred|Quarter\s*Horse|Arabian|Mixed)\s*\n(.*?)Distance:",
        body,
        re.DOTALL,
    )
    if not m:
        return None
    text = m.group(1).strip()
    # Squash repeated whitespace
    text = re.sub(r"\s+", " ", text)
    return text or None


# ---------------------------------------------------------------------------
# PDF entry points
# ---------------------------------------------------------------------------

def _read_pdf_text(pdf_path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
            parts.append("\n")
    return "\n".join(parts)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """Top-level entry: returns a dict for one PDF."""
    fn_info = parse_filename(pdf_path)
    text = _read_pdf_text(pdf_path)
    race_blocks = split_into_races(text)

    # Cross-check filename date vs header date
    header_dates: list[str] = []
    track_text: str | None = None
    for block in race_blocks:
        d = parse_date_long(block["date_text"])
        if d:
            header_dates.append(d)
        if not track_text:
            track_text = block["track_text"]

    header_date = header_dates[0] if header_dates else None
    chosen_date = header_date or fn_info.date_iso

    # Track code: prefer the filename (already normalized 2-letter form).
    # Fall back to a small lookup against the header text. Last resort: take
    # the leading uppercase letters from the header.
    track_code = fn_info.track_code
    if not track_code and track_text:
        header_upper = re.sub(r"[^A-Z]", "", track_text)
        header_codes = {
            "GULFSTREAMPARK": "GP",
            "CHARLESTOWN": "CT",
            "EVANGELINEDOWNS": "EVD",
            "MAHONINGVALLEY": "MVR",
            "FAIRGROUNDS": "FG",
            "DELTADOWNS": "DD",
            "FAIRMOUNTPARK": "FP",
        }
        track_code = header_codes.get(header_upper) or header_upper[:2] or None

    parsed_races: list[dict[str, Any]] = []
    for block in race_blocks:
        race = parse_race_block(
            track_text=block["track_text"],
            date_iso=chosen_date,
            race_num=block["race_num"],
            body=block["body"],
        )
        parsed_races.append(race)

    return {
        "parser_version": PARSER_VERSION,
        "source_pdf": str(pdf_path),
        "file_sha256": _sha256(pdf_path),
        "track_code": track_code,
        "track_text": track_text,
        "race_date": chosen_date,
        "filename_date": fn_info.date_iso,
        "header_date": header_date,
        "naming_convention": fn_info.naming_convention,
        "race_count": len(parsed_races),
        "races": parsed_races,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _cmd_parse(args: argparse.Namespace) -> int:
    pdf = Path(args.path)
    if not pdf.exists():
        log.error("not found: %s", pdf)
        return 1
    t0 = time.perf_counter()
    result = parse_pdf(pdf)
    elapsed = time.perf_counter() - t0
    log.info(
        "parsed %s: %d races in %.2fs",
        pdf.name,
        result["race_count"],
        elapsed,
    )
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        log.info("wrote %s", args.json)
    else:
        for r in result["races"]:
            log.info(
                "  Race %s: %s, %s, %s yards, %s starters, %d entries parsed",
                r["race_num"],
                r["surface"],
                r["track_condition"],
                r["distance_yards"],
                r["field_size"],
                len(r["entries"]),
            )
            if r["warnings"]:
                for w in r["warnings"]:
                    log.warning("    %s", w)
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    root = Path(args.directory)
    if not root.exists():
        log.error("not found: %s", root)
        return 1
    cache = Path(args.cache) if args.cache else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(root.rglob("*.pdf"))
    if args.limit:
        pdfs = pdfs[: args.limit]
    log.info("scanning %d PDFs under %s", len(pdfs), root)
    n_ok = 0
    n_err = 0
    n_skipped = 0
    t0 = time.perf_counter()
    races_total = 0
    for pdf in pdfs:
        # Resume support: skip if cached JSON already exists with matching sha.
        cache_file = cache / (pdf.stem + ".json") if cache else None
        if cache_file and cache_file.exists() and not args.force:
            try:
                existing = json.loads(cache_file.read_text(encoding="utf-8"))
                if existing.get("file_sha256") == _sha256(pdf):
                    n_skipped += 1
                    races_total += existing.get("race_count", 0)
                    continue
            except Exception:
                pass
        try:
            result = parse_pdf(pdf)
            if cache_file:
                cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
            n_ok += 1
            races_total += result["race_count"]
        except Exception as e:
            log.exception("FAILED %s: %s", pdf, e)
            n_err += 1
    elapsed = time.perf_counter() - t0
    rate = (n_ok + n_skipped) / max(elapsed / 60.0, 1e-9)
    log.info(
        "done: %d ok, %d skipped (cached), %d errors, %d races, %.1f PDFs/min",
        n_ok, n_skipped, n_err, races_total, rate,
    )
    return 0 if n_err == 0 else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Equibase result-chart PDF parser")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="Parse one PDF")
    p_parse.add_argument("path")
    p_parse.add_argument("--json", help="Write full result JSON to this path")
    p_parse.set_defaults(func=_cmd_parse)

    p_batch = sub.add_parser("batch", help="Parse a directory tree")
    p_batch.add_argument("directory")
    p_batch.add_argument("--cache", required=True, help="Directory to write JSON sidecars to")
    p_batch.add_argument("--limit", type=int, default=0)
    p_batch.add_argument("--force", action="store_true", help="Re-parse even if cache is fresh")
    p_batch.set_defaults(func=_cmd_batch)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
