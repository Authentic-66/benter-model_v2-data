"""Brisnet past-performance parser — DPv1 port (Phase 5A).

Ported from the v1 repo's ``scripts/brisnet_parser_v2.py`` (2,417 lines).
The **extraction** logic is kept verbatim — it is the asset. Everything that
made the v1 parser part of a betting workflow is not:

Dropped in the port
-------------------
* ``IRON_TRAINERS`` / ``SIRE_SIGNALS`` / ``IRON_HORSES`` / ``TRAINER_RULES`` —
  ~250 lines of hand-curated v10 signal constants (emoji-tagged trainer and
  sire lists). DPv1 learns connection and pedigree strength from the corpus;
  a hardcoded "🔥 IRON CT #1" is a prior baked into the parser where the model
  cannot see, audit or decay it. The equivalent DPv1 features already exist
  (``trainer_at_track_winrate_shrunk``, ``sire_*``, ...).
* ``print_card`` / ``write_picks_file`` / ``is_strong_pick`` / Kelly sizing /
  the ``prob_predict.py`` shell-out. Phase 5A is a data-extraction phase.
* ``write_entries_db`` against ``benter_model.db``. Replaced by
  :func:`write_pp_tables`, which writes PP rows into ``racing_full.db``.

Changed in the port
-------------------
* **Morning-line odds is a feature, not an anchor.** ``ml_decimal`` is emitted
  as one column of ``entry_pp_features`` alongside ~50 others. The v1 model
  gave ``log_ml`` its single largest coefficient (~40% of the prediction);
  that is the structural flaw the v2 rebuild exists to correct. Nothing in
  this module privileges it, and Phase 5A's prediction test carries it in the
  same bucket as every other PP feature.
* Output is entry-grain and joins to ``entries.id``. Matching to the result
  corpus is done by ``match_pp_to_entries.py``, not here.
* ``race_date`` is taken from the filename/text and the "is it today" guard is
  gone — Phase 5A parses a back catalogue, not tonight's card.

What it extracts (unchanged from v1)
------------------------------------
morning-line odds, Brisnet speed figures (best / recent / turf / AW), pace
figures (E1/E2/late), Prime Power + rank, workouts and engineered workout
features, equipment and weight changes, career records, distance/surface
combo records, trainer angles, jockey angles, running style, form trajectory
(OLS slope over recent figures), last class and last distance, J/T combo rate,
days off, and the positive/negative angle text.

Usage
-----
    python scripts_dpv1/brisnet_pp_parser.py <file.pdf> [TRACK]   # one file, dry
    python scripts_dpv1/brisnet_pp_parser.py --json <file.pdf> CT
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Track codes as they appear in PP filenames -> tracks.code in racing_full.db.
# FP and EVD parse fine but have no result corpus in racing_full.db (Phase 4A
# loaded GP + CT + MNR only), so they can be extracted but not matched.
PP_TRACK_CODES = {
    "GP": "Gulfstream Park",
    "CT": "Charles Town",
    "MNR": "Mountaineer",
    "FP": "Fairmount Park",
    "EVD": "Evangeline Downs",
    "MVR": "Mahoning Valley",
    "DD": "Delta Downs",
}

# Filename stems use a different token than the DB track code for some tracks.
FILENAME_PREFIX_TO_TRACK = {
    "GPX": "GP", "GP": "GP",
    "CTX": "CT", "CT": "CT",
    "FPK": "FP", "FP": "FP",
    "EVD": "EVD",
    "MNR": "MNR",
    "MVR": "MVR", "DD": "DD",
}

def extract_text(filepath):
    path = Path(filepath)
    if path.suffix.lower() != '.pdf':
        return path.read_text(errors='replace')
    try:
        result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                               capture_output=True, text=True, errors='replace')
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            full = page.extract_text(layout=True) or ''
            left = page.crop((0, 0, page.width * 0.52, page.height)).extract_text() or ''
            pages.append(full + '\n' + left)
    return '\f'.join(pages)

# PP race lines start "DDMonYYTRK" (e.g. '18Apr26CT'); Brisnet spells July 'Jly'
_PP_LINE_DATE_RE = re.compile(r'^\s*(\d{1,2})([A-Za-z]{3})(\d{2})[A-Za-z]')
_PP_MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5,
              'jun': 6, 'jne': 6, 'jul': 7, 'jly': 7, 'aug': 8,
              'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
_PP_PACE_TOKEN_RE = re.compile(r'\d{2,3}/$')
_PP_VARIANT_RE = re.compile(r'^[+-]\d+$')
_TURF_GOING_RE = re.compile(r'\b(fm|yl|sf)\b')


def _pp_line_date(line):
    """Race date of a condensed PP race line, or None."""
    m = _PP_LINE_DATE_RE.match(line)
    if not m:
        return None
    mon = _PP_MONTHS.get(m.group(2).lower())
    if not mon:
        return None
    try:
        return date(2000 + int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


_PP_E1_TAIL_RE = re.compile(r'(\d{2,3})$')


def extract_speed_figures(block_lines):
    """Extract Brisnet speed figures from condensed PP race lines.

    Figure block reads "E1 E2/ LP [±var ±var] SPD" before the post/start
    positions, so SPD is the LAST 25-130 number in the run that follows
    the "NN/" pace token (e.g. '88 82/ 61 -1 -4 59 6 5 ...' -> 59).
    Returns [(figure, surface), ...] most recent first, deduped by race
    date (extracted text repeats some lines). surface is 'T', 'AW', 'D'.
    """
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or d in races:
            continue
        toks = line.split()
        slash_i = next((i for i, t in enumerate(toks)
                        if _PP_PACE_TOKEN_RE.fullmatch(t)), None)
        if slash_i is None:
            continue
        fig = None
        for t in toks[slash_i + 1:]:
            if _PP_VARIANT_RE.fullmatch(t):
                continue
            # t.isdigit() returns True for Unicode digit-like glyphs (e.g. ²)
            # that int() then chokes on; guard with the str-only ascii check.
            if not (t.isdigit() and t.isascii()):
                break
            v = int(t)
            if 25 <= v <= 130:
                fig = v
            else:
                break
        if fig is None:
            continue
        if '(T)' in line or _TURF_GOING_RE.search(line):
            surf = 'T'
        elif re.search(r'\bAW\b|Tapeta|Polytrack|All.?Weather', line):
            surf = 'AW'
        else:
            surf = 'D'
        races[d] = (fig, surf)
    return [races[d] for d in sorted(races, reverse=True)]


# Workout line entries: "[×]DDMon[YY] TRK <dist><unit> <surf> :<time>[frac] B[g]<rank>/<total>"
# Examples seen in GP/CT/EVD PPs:
#   27May GP 3f ft :37ª B1/8
#   13Dec'25 Tam 4f ft :51ª B46/52
#   15Feb Tam 3f ft :36« Bg6/21          (gate work)
#   ×04Mar Tam 3f ft :36ª B1/11           (× = recently-noted / significant)
#   05Oct'25 GP 4f ft :48« B9/12
# Time fractions are FIFTHS of a second (standard horse-racing convention).
_WORKOUT_TIME_FIFTHS = {
    '§': 0.0, '¨': 0.2, '©': 0.4, 'ª': 0.6, '«': 0.8,
}
_WORKOUT_RE = re.compile(
    r"(?:×\s*)?"                                            # optional × prefix
    r"(\d{1,2})([A-Z][a-z]{2})(?:'(\d{2}))?"                # date: 27May or 13Dec'25
    r"\s+"
    r"([A-Za-z]{2,5})"                                      # track code (Tam, GP, Sar, etc.)
    r"\s+"
    r"(\d{1,2})([½¼¾]?)([mf])"                              # distance: 3f, 5½f, 1m
    r"\s+"
    r"([a-z]{2,3})"                                         # surface: ft, sl, gd, my
    r"\s+"
    r":(\d+(?::\d+)?)([§¨©ª«¬\xad®¯°]?)"                    # time: :37ª or :1:01¨
    r"\s+"
    r"B\s*(g?)\s*(\d+)/(\d+)"                               # ranking: B1/8, B 1/8, Bg6/21
)


def _parse_workout_distance(num: str, frac: str, unit: str) -> float | None:
    try:
        n = int(num)
    except ValueError:
        return None
    f = {'½': 0.5, '¼': 0.25, '¾': 0.75}.get(frac, 0.0)
    if unit == 'f':
        return n + f
    if unit == 'm':
        return (n + f) * 8.0
    return None


def _parse_workout_time(digits: str, sup: str) -> float | None:
    try:
        if ':' in digits:
            mm, ss = digits.split(':', 1)
            sec = int(mm) * 60 + int(ss)
        else:
            sec = int(digits)
    except ValueError:
        return None
    sec += _WORKOUT_TIME_FIFTHS.get(sup, 0.0)
    return float(sec)


def _parse_workout_date(day: str, mon: str, yy: str,
                        race_date: date | None) -> date | None:
    month = _PP_MONTHS.get(mon.lower())
    if month is None:
        return None
    try:
        d_int = int(day)
    except ValueError:
        return None
    if yy:
        try:
            return date(2000 + int(yy), month, d_int)
        except ValueError:
            return None
    # No year suffix: use race_year, fall back to year-1 if that puts the
    # workout after the race (workouts always precede the race).
    if race_date is None:
        return None
    for year in (race_date.year, race_date.year - 1):
        try:
            d = date(year, month, d_int)
        except ValueError:
            continue
        if d <= race_date:
            return d
    return None


def extract_workouts(block_lines, race_date: date | None) -> list[dict]:
    """Parse the workout-history lines at the bottom of a horse's PP block.

    Returns a list of dicts with keys: date, days_ago, track, furlongs,
    surface, seconds, sec_per_f, is_bullet, is_gate, rank, total. Older
    entries (>1 year) and unparseable rows are dropped.
    """
    if race_date is None:
        return []
    works = []
    seen_keys = set()
    for line in block_lines:
        for m in _WORKOUT_RE.finditer(line):
            (day, mon, yy, trk, dnum, dfrac, dunit, surf,
             tdigits, tfrac, gflag, rank, total) = m.groups()
            wdate = _parse_workout_date(day, mon, yy, race_date)
            if wdate is None:
                continue
            days_ago = (race_date - wdate).days
            if days_ago < 0 or days_ago > 540:
                continue
            # De-dupe — Brisnet's two-column layout sometimes prints the
            # same workout in left and right copies.
            key = (wdate, trk, dnum + dfrac + dunit, tdigits + tfrac)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            furlongs = _parse_workout_distance(dnum, dfrac, dunit)
            seconds = _parse_workout_time(tdigits, tfrac)
            sec_per_f = (seconds / furlongs
                         if seconds is not None and furlongs and furlongs > 0
                         else None)
            try:
                rank_i, total_i = int(rank), int(total)
            except ValueError:
                continue
            works.append({
                'date': wdate, 'days_ago': days_ago,
                'track': trk, 'furlongs': furlongs, 'surface': surf,
                'seconds': seconds, 'sec_per_f': sec_per_f,
                'is_bullet': rank_i == 1,
                'is_gate': bool(gflag),
                'rank': rank_i, 'total': total_i,
            })
    works.sort(key=lambda w: w['days_ago'])
    return works


def workout_features(works: list[dict]) -> dict:
    """Aggregate a horse's workout history into model features.

    Returns dict with the 5 features (None for missing):
      bullet_count_60d         — count of B1/N in last 60 days
      days_since_last_workout  — days_ago of the most recent work
      workout_avg_pace         — avg sec_per_f of last 3 timed workouts
      workout_count_60d        — total works in last 60 days
      has_recent_bullet        — 1 if any B1/N in last 14 days, else 0
    """
    if not works:
        return {'bullet_count_60d': None, 'days_since_last_workout': None,
                'workout_avg_pace': None, 'workout_count_60d': None,
                'has_recent_bullet': None}
    recent_60 = [w for w in works if w['days_ago'] <= 60]
    bullets_60 = [w for w in recent_60 if w['is_bullet']]
    bullets_14 = [w for w in works
                  if w['days_ago'] <= 14 and w['is_bullet']]
    timed_recent3 = [w['sec_per_f'] for w in works[:3]
                     if w['sec_per_f'] is not None]
    avg_pace = (sum(timed_recent3) / len(timed_recent3)
                if timed_recent3 else None)
    return {
        'bullet_count_60d': len(bullets_60),
        'days_since_last_workout': works[0]['days_ago'],
        'workout_avg_pace': avg_pace,
        'workout_count_60d': len(recent_60),
        'has_recent_bullet': int(bool(bullets_14)),
    }


# Equipment-change indicators in Brisnet PPs come through three channels:
#   1. Angle/comment text near top of horse block, e.g.:
#        "ñ May improve with Blinkers added today"
#   2. Trainer-stat angle rows that only appear when the horse is in that
#      category today, e.g.:
#        "+1stTimeBlinkers    30 20%   40% -0.65"
#        "Blinkers Off  N N-N-N N% ..."
#        "1st time lasix  23 9% 48% -0.64"
#   3. Today's weight: token after "Brdr: ..." like "L 120" (Lasix + lbs).
#      Last race weight: 3 superscript digits glued to jockey name in the
#      most recent PP race line (e.g. "OcasioJ¨©§" = OcasioJ + 120).
_BLINKERS_ADD_RE = re.compile(r'[Bb]linkers\s+added\s+today', re.IGNORECASE)
_BLINKERS_OFF_RE = re.compile(r'\b[Bb]linkers\s*[Oo]ff\b|\bBlinkersOff\b')
_FIRST_BLINKERS_RE = re.compile(r'1st\s*Time\s*Blinkers', re.IGNORECASE)
_FIRST_LASIX_RE = re.compile(r'\b1st\s*time\s*lasix\b', re.IGNORECASE)
# Today's equip+weight token can land on any line in the horse header
# block (Brdr/Dam/silks line, varies by track). The combination of a 1-3
# letter equipment code (Lasix L / blinkers b / bandages B / furosemide F)
# followed by a weight in the [105, 132] race-weight range is rare enough
# elsewhere in the text to be reliable. We additionally require trailing
# whitespace + a digit OR $ to avoid matching things like "L 100k" inside
# claiming notes.
_TODAY_EQ_RE = re.compile(r'(?<![A-Za-z0-9])([LBbFf]{1,3})\s+(1[0-3]\d)(?=\s+[\$\d])')
_PP_JK_WEIGHT_RE = re.compile(
    r"[A-Z][A-Za-z'.]{2,}([§¨©ª«¬\xad®¯°]{3})\s+[A-Za-z]{1,5}\s+\d+\.\d+"
)


def _decode_sup_weight(sup: str) -> int | None:
    try:
        return int(''.join(str(_SUP_DIGITS[c]) for c in sup))
    except KeyError:
        return None


def extract_equipment_features(block_lines, block_text: str | None = None) -> dict:
    """Return blinkers_added_today, blinkers_removed_today, first_time_lasix,
    weight_change, equipment_change. Sources: angle text + trainer stat rows
    in the block, today's weight from the Brdr area, last race's weight from
    the most recent PP line's jockey superscript.

    block_text is the joined block — caller can pass a pre-joined string to
    avoid recomputing it. Falls back to joining block_lines.
    """
    if block_text is None:
        block_text = "\n".join(block_lines)
    feats = {
        'blinkers_added_today': 0,
        'blinkers_removed_today': 0,
        'first_time_lasix': 0,
        'weight_change': None,
        'equipment_change': 0,
    }
    if _BLINKERS_ADD_RE.search(block_text) or _FIRST_BLINKERS_RE.search(block_text):
        feats['blinkers_added_today'] = 1
    if _BLINKERS_OFF_RE.search(block_text):
        feats['blinkers_removed_today'] = 1
    if _FIRST_LASIX_RE.search(block_text):
        feats['first_time_lasix'] = 1

    # Today's weight from "Brdr: ... L 120"
    today_weight = None
    m = _TODAY_EQ_RE.search(block_text)
    if m:
        try:
            w = int(m.group(2))
            if 100 <= w <= 135:
                today_weight = w
        except ValueError:
            pass

    # Last race weight: scan PP race lines, take first match (most recent)
    last_weight = None
    for line in block_lines:
        if _pp_line_date(line) is None:
            continue
        jm = _PP_JK_WEIGHT_RE.search(line)
        if jm:
            last_weight = _decode_sup_weight(jm.group(1))
            if last_weight is not None:
                break

    if today_weight is not None and last_weight is not None:
        feats['weight_change'] = today_weight - last_weight

    # equipment_change is the OR of any binary change indicator + a meaningful
    # weight swing (≥2 lb is usually trainer intent, not a jockey re-pairing).
    if (feats['blinkers_added_today'] or feats['blinkers_removed_today']
            or feats['first_time_lasix']
            or (feats['weight_change'] is not None
                and abs(feats['weight_change']) >= 2)):
        feats['equipment_change'] = 1
    return feats


# Career-record block on the right side of the horse header:
#   "Dis (99) 9 0- 0- 0 $500 60"      → distance: par 99, 9 starts, 0-0-0
#   "Fst (101) 18  4- 4- 4 $75,367 83" → fast dirt
#   "Off (97) 5  4- 2- 1 $60,408 83"  → off track (mud/sloppy/etc.)
#   "Trf (101) 1"                     → turf (some rows omit W-P-S)
#   "AW  10 0 - 2 - 1"                → all-weather (no par in parens)
_CAREER_RECORD_RE = re.compile(
    r'\b(Fst|Off|Dis|Trf)\s*\(\s*\d+\??\s*\)\s+(\d+)'
    r'(?:\s+(\d+)\s*-\s*(\d+)\s*-\s*(\d+))?'
)
_AW_RECORD_RE = re.compile(
    r'\bAW\s+(\d+)(?:\s+(\d+)\s*-\s*(\d+)\s*-\s*(\d+))?'
)


def extract_career_records(block_lines) -> dict:
    """Parse the Dis/Fst/Off/Trf/AW career records from a horse block.
    Returns dict keyed by label → (starts, wins) tuple. Wins defaults to 0
    when the W-P-S triple is missing (Brisnet sometimes truncates AW/Trf
    rows when the horse only has a few starts).
    """
    text = '\n'.join(block_lines)
    out: dict[str, tuple[int, int]] = {}
    for m in _CAREER_RECORD_RE.finditer(text):
        label = m.group(1)
        if label in out:
            continue
        try:
            starts = int(m.group(2))
        except (TypeError, ValueError):
            continue
        try:
            wins = int(m.group(3)) if m.group(3) is not None else 0
        except ValueError:
            wins = 0
        out[label] = (starts, wins)
    if 'AW' not in out:
        am = _AW_RECORD_RE.search(text)
        if am:
            try:
                starts = int(am.group(1))
                wins = int(am.group(2)) if am.group(2) is not None else 0
                out['AW'] = (starts, wins)
            except ValueError:
                pass
    return out


def _surface_label(today_surface: str | None) -> str:
    """Map race surface string to the matching career-record label."""
    if not today_surface:
        return 'Fst'
    s = today_surface.strip().lower()
    if 'turf' in s:
        return 'Trf'
    if 'all weather' in s or 'aw' in s or 'tapeta' in s or 'synthetic' in s:
        return 'AW'
    return 'Fst'   # dirt default; assume fast at predict time


def _pp_line_surface(line: str) -> str:
    """Surface category for a PP race line: 'T' (turf), 'AW', or 'D' (dirt)."""
    if '(T)' in line or _TURF_GOING_RE.search(line):
        return 'T'
    if re.search(r'\bAW\b|Tapeta|Polytrack|All.?Weather', line):
        return 'AW'
    return 'D'


def _today_surface_category(today_surface: str | None) -> str:
    """Map today's surface (race header string) to PP-line category."""
    if not today_surface:
        return 'D'
    s = today_surface.strip().lower()
    if 'turf' in s:
        return 'T'
    if 'all weather' in s or s == 'aw' or 'tapeta' in s or 'synthetic' in s:
        return 'AW'
    return 'D'


def distance_surface_combo_record(block_lines,
                                  today_furlongs: float | None,
                                  today_surface: str | None,
                                  tolerance: float = 0.5) -> tuple[int, int]:
    """Count starts and wins at races matching today's distance (within
    tolerance furlongs) AND surface. Wins are detected from the FIN call
    in the PP line (position == 1). Returns (combo_starts, combo_wins).
    """
    if today_furlongs is None:
        return 0, 0
    target_cat = _today_surface_category(today_surface)
    starts = wins = 0
    seen = set()
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or d in seen:
            continue
        seen.add(d)
        f = _ppline_furlongs(line)
        if f is None or abs(f - today_furlongs) > tolerance:
            continue
        if _pp_line_surface(line) != target_cat:
            continue
        starts += 1
        fin_m = _PP_FIN_RE.search(line)
        if fin_m:
            try:
                if int(fin_m.group(1)) == 1:
                    wins += 1
            except ValueError:
                pass
    return starts, wins


def distance_surface_record_features(records: dict,
                                     today_surface: str | None) -> dict:
    """Extract per-horse distance/surface feature aggregates."""
    feats = {
        'dist_wins': None, 'dist_starts': None,
        'surface_wins': None, 'surface_starts': None,
        'surface_winpct': None,
    }
    if 'Dis' in records:
        s, w = records['Dis']
        feats['dist_starts'] = s
        feats['dist_wins'] = w
    surf_label = _surface_label(today_surface)
    if surf_label in records:
        s, w = records[surf_label]
        feats['surface_starts'] = s
        feats['surface_wins'] = w
        if s > 0:
            feats['surface_winpct'] = w / s
    return feats


# Connection-change features (Phase C). Today's jockey appears in two
# formats: the silks line ("VASQUEZ MIGUEL A" — uppercase, space-separated)
# and the PP race lines ("VasquezMA" — last name + first-initial(s)
# compressed). Normalize both to lowercase last-name + initials.
_PP_JOCKEY_RE = re.compile(
    r"([A-Z][A-Za-z'.]{2,})[§¨©ª«¬\xad®¯°]{3}"
)


def _normalize_jockey(name: str | None) -> str | None:
    """Canonical key so today's jockey and the PP-line abbreviation compare.

    DPv1 fix over the v1 parser: today's rider renders as
    ``"EBOW III WARREN"`` (surname first, then given names) while the PP race
    line abbreviates it ``"EbowWI"`` (surname, then given-name initials in the
    opposite order). The v1 normalizer preserved initial order, so those two
    produced ``ebowiw`` vs ``ebowwi`` and never matched — which made
    ``jockey_change``/``jockey_first_time`` fire on essentially every horse.
    Sorting the initials makes the key order-free.
    """
    if not name:
        return None
    name = name.strip()
    if ' ' in name:
        parts = [p for p in name.split() if p]
        if not parts:
            return None
        last = parts[0].lower()
        initials = ''.join(sorted(p[0].lower() for p in parts[1:] if p))
        return last + initials if last else None
    m = re.match(r"^([A-Z][a-z'.]+)([A-Z]+)$", name)
    if m:
        return (m.group(1).lower() + ''.join(sorted(m.group(2).lower())))
    return name.lower().replace(' ', '')


def extract_past_jockeys(block_lines) -> list[str]:
    """List of normalized past-race jockey names, most recent first,
    deduped by race date."""
    seen_dates = set()
    out = []
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or d in seen_dates:
            continue
        m = _PP_JOCKEY_RE.search(line)
        if not m:
            continue
        norm = _normalize_jockey(m.group(1))
        if norm:
            seen_dates.add(d)
            out.append(norm)
    return out


def connection_features(today_jockey: str | None,
                        past_jockeys: list[str],
                        jt_winpct: float | int | None,
                        hot_jt_threshold: float = 20.0) -> dict:
    """jockey_change: 1 if today's jockey differs from the most recent PP
    line's jockey (NaN when no past PPs). jockey_first_time: 1 if today's
    jockey never appears in past PP lines. hot_jt_combo: 1 when the
    JKYw/Trn L60 win rate (jt_winpct) clears threshold."""
    feats = {'jockey_change': None, 'jockey_first_time': None,
             'hot_jt_combo': None}
    today_norm = _normalize_jockey(today_jockey)
    if today_norm is None:
        # No today's jockey — leave change/first as missing
        pass
    elif not past_jockeys:
        # First-time starter (or no parseable PPs): every connection is
        # new. Setting first_time=1 surfaces FTS as a connection signal,
        # but leave jockey_change as None (no last-race comparison
        # available) to avoid double-counting with starts_missing.
        feats['jockey_first_time'] = 1
    else:
        feats['jockey_change'] = int(today_norm != past_jockeys[0])
        feats['jockey_first_time'] = int(today_norm not in past_jockeys)

    if jt_winpct is not None:
        try:
            feats['hot_jt_combo'] = int(float(jt_winpct) >= hot_jt_threshold)
        except (TypeError, ValueError):
            pass
    return feats


# Trainer-angle stat rows (Phase E1). Format:
#   "<name>  <starts>  <winpct>%  <itm%>  <roi>"
# Examples (from real Brisnet PPs):
#   "Maiden Clming  93 8%  25% -0.72"
#   "All Weather   125 8%  21% -0.73"
#   "Sprints       135 13% 35% -0.62"
#   "+1stTimeBlinkers 30 20% 40% -0.65"
# Jockey rows use a "JKYw/" prefix ("+JKYw/ P types 279 18% 48% -0.71")
# and are filtered out — they're Phase E2 territory.
_ANGLE_ROW_RE = re.compile(
    r'(?:^|\s)([+\-]?)([A-Za-z][A-Za-z0-9 /\-\']{1,28}?)'
    r'\s+(\d{1,5})\s+(\d{1,3})%\s+(\d{1,3})%\s+([+\-]?\d+\.\d+)'
)

# Trainer-angle classifier: map known angle names (lowercased) to canonical
# categories. Only angles in this map are kept — random matches like
# "2026 36 3% 25% -1.76" (year stats, not matchable to today's conditions)
# are dropped so the Sprint/Dirt/etc. signals stay clean.
TRAINER_ANGLE_TYPES = {
    # Surface
    'dirt':              'surface_dirt',
    'turf':              'surface_turf',
    'all weather':       'surface_aw',
    'allweather':        'surface_aw',
    'aw':                'surface_aw',
    'synth':             'surface_aw',
    # Distance band
    'sprint':            'dist_sprint',
    'sprints':           'dist_sprint',
    'route':             'dist_route',
    'routes':            'dist_route',
    # Class type
    'maiden':            'class_mdn',
    'mdn':               'class_mdn',
    'maiden clming':     'class_mdn',
    'maiden claming':    'class_mdn',
    'claming':           'class_clm',
    'clming':            'class_clm',
    'claim':             'class_clm',
    'claiming':          'class_clm',
    'allowance':         'class_alw',
    'alw':               'class_alw',
    'stakes':            'class_stk',
    'oc':                'class_alw',  # OC ~= Optional Claiming, behaves like Alw
    # Track condition (when known)
    'off':               'condition_off',
    'wet':               'condition_off',
    'mud':               'condition_off',
    'muddy':             'condition_off',
    # Equipment-change angles (match if today has same change)
    '1sttimeblinkers':   'eq_first_blinkers',
    '1st time blinkers': 'eq_first_blinkers',
    'blinkersoff':       'eq_blinkers_off',
    'blinkers off':      'eq_blinkers_off',
    '1st time lasix':    'eq_first_lasix',
    '1sttimelasix':      'eq_first_lasix',
}


def extract_trainer_angles(block_lines) -> list[dict]:
    """Parse trainer-side angle stat rows from a horse's block.

    Returns list of {sign, name, type, starts, winpct, itm_pct, roi}. Filters
    out jockey rows (JKYw/ prefix) and angles whose name isn't in the
    TRAINER_ANGLE_TYPES map (year/decade stats etc. that don't condition
    on today's race).
    """
    text = '\n'.join(block_lines)
    out: list[dict] = []
    seen = set()
    for m in _ANGLE_ROW_RE.finditer(text):
        sign, name, starts, winpct, itm, roi = m.groups()
        name = name.strip()
        name_norm = re.sub(r'\s+', ' ', name).lower()
        # Skip jockey rows — Phase E2 will handle these
        if 'jkyw' in name_norm or name_norm.startswith('jky'):
            continue
        # Filter to known trainer angles (longest-match first)
        angle_type = TRAINER_ANGLE_TYPES.get(name_norm)
        if angle_type is None:
            for kw, t in sorted(TRAINER_ANGLE_TYPES.items(),
                                key=lambda kv: -len(kv[0])):
                if kw in name_norm:
                    angle_type = t
                    break
        if angle_type is None:
            continue
        try:
            s = int(starts)
            wp = int(winpct)
        except ValueError:
            continue
        if not (1 <= s <= 99999) or wp > 100:
            continue
        key = (angle_type, s, wp)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'sign': sign or '',
            'name': name,
            'type': angle_type,
            'starts': s,
            'winpct': wp,
            'itm_pct': int(itm),
            'roi': float(roi),
        })
    return out


def _today_class_type(conditions: str | None) -> str | None:
    """Map race conditions string ('MC 12500 Ì 5 Furlongs ...') to one of
    {mdn, clm, alw, stk}. Returns None when no class indicator is found."""
    if not conditions:
        return None
    s = conditions.upper()
    # Order matters — MC is maiden claiming = mdn, but MSW also = mdn.
    if 'MSW' in s or 'MDN' in s or s.startswith('MC') or 'MAIDEN' in s:
        return 'mdn'
    if s.startswith('STK') or 'STAKES' in s or s.startswith('STAKES'):
        return 'stk'
    if 'ALW' in s or s.startswith('AOC') or s.startswith('OC'):
        return 'alw'
    if 'CLM' in s or 'CLAIM' in s or s.startswith('STR'):
        return 'clm'
    return None


def _angle_matches_today(angle_type: str,
                         today_surface: str | None,
                         today_furlongs: float | None,
                         today_class: str | None,
                         blinkers_added_today: int,
                         blinkers_removed_today: int,
                         first_time_lasix: int) -> bool:
    """Return True if a parsed angle type applies to today's race conditions."""
    if angle_type == 'surface_dirt':
        return (today_surface or '').strip().lower().startswith('dirt')
    if angle_type == 'surface_turf':
        return (today_surface or '').strip().lower().startswith('turf')
    if angle_type == 'surface_aw':
        s = (today_surface or '').strip().lower()
        return 'all weather' in s or s == 'aw' or 'tapeta' in s
    if angle_type == 'dist_sprint':
        return today_furlongs is not None and today_furlongs < 8.0
    if angle_type == 'dist_route':
        return today_furlongs is not None and today_furlongs >= 8.0
    if angle_type == 'class_mdn':
        return today_class == 'mdn'
    if angle_type == 'class_clm':
        return today_class == 'clm'
    if angle_type == 'class_alw':
        return today_class == 'alw'
    if angle_type == 'class_stk':
        return today_class == 'stk'
    if angle_type == 'condition_off':
        # We don't know post-time condition pre-race; skip
        return False
    if angle_type == 'eq_first_blinkers':
        return blinkers_added_today == 1
    if angle_type == 'eq_blinkers_off':
        return blinkers_removed_today == 1
    if angle_type == 'eq_first_lasix':
        return first_time_lasix == 1
    return False


def trainer_angle_features(angles: list[dict],
                           today_surface: str | None,
                           today_furlongs: float | None,
                           today_class: str | None,
                           blinkers_added_today: int,
                           blinkers_removed_today: int,
                           first_time_lasix: int,
                           hot_threshold: int = 20,
                           min_starts: int = 10) -> dict:
    """Aggregate trainer angles that apply to today's race conditions.

    trainer_today_angle_winpct: starts-weighted win% across matching angles
                                (None when no matching angle has starts)
    trainer_today_angle_starts: sum of starts across matching angles
                                (counts can double-count when multiple
                                 angles overlap — that's OK as a signal)
    has_strong_angle:           1 if any matching angle has winpct
                                >= hot_threshold AND starts >= min_starts
    count_positive_angles:      number of matching angles with '+' sign
    """
    matching = [a for a in angles if _angle_matches_today(
        a['type'], today_surface, today_furlongs, today_class,
        blinkers_added_today, blinkers_removed_today, first_time_lasix,
    )]
    if not matching:
        return {
            'trainer_today_angle_winpct': None,
            'trainer_today_angle_starts': None,
            'has_strong_angle': None,
            'count_positive_angles': None,
        }
    total_starts = sum(a['starts'] for a in matching)
    if total_starts > 0:
        weighted = sum(a['starts'] * a['winpct'] for a in matching) / total_starts
    else:
        weighted = None
    has_strong = any(
        a['winpct'] >= hot_threshold and a['starts'] >= min_starts
        for a in matching
    )
    count_pos = sum(1 for a in matching if a['sign'] == '+')
    return {
        'trainer_today_angle_winpct': weighted,
        'trainer_today_angle_starts': total_starts,
        'has_strong_angle': int(has_strong),
        'count_positive_angles': count_pos,
    }


# Jockey-angle stat rows (Phase E2). Same row format as trainer angles
# but prefixed with "JKYw/" (jockey with ...). After stripping the
# prefix the category is one of:
#   sprints/routes        distance band — match today's distance
#   e/ep/p/s/na types     running-style — match today's horse style
#   dirt/turf             surface — match today's race surface
#   trn l60               jockey-with-current-trainer last 60 days —
#                         redundant with existing sig_hotjt / jt_winpct,
#                         skip
JOCKEY_ANGLE_TYPES = {
    # Distance band
    'sprints':    'dist_sprint',
    'sprint':     'dist_sprint',
    'routes':     'dist_route',
    'route':      'dist_route',
    # Running style (horse style indicator from silks header)
    'e types':    'style_e',
    'ep types':   'style_ep',
    'e/p types':  'style_ep',
    'p types':    'style_p',
    's types':    'style_s',
    'na types':   'style_na',
    # Surface
    'dirt':       'surface_dirt',
    'turf':       'surface_turf',
    'all weather':'surface_aw',
    'aw':         'surface_aw',
    # Class type — rare on the jockey side but include for completeness
    'maiden':     'class_mdn',
    'claming':    'class_clm',
    'clming':     'class_clm',
    'claiming':   'class_clm',
    'allowance':  'class_alw',
    'stakes':     'class_stk',
}


def extract_jockey_angles(block_lines) -> list[dict]:
    """Parse JKYw/-prefixed jockey-angle stat rows. Skips "trn l60" because
    it's redundant with existing sig_hotjt / jt_winpct."""
    text = '\n'.join(block_lines)
    out: list[dict] = []
    seen = set()
    for m in _ANGLE_ROW_RE.finditer(text):
        sign, name, starts, winpct, itm, roi = m.groups()
        name = name.strip()
        name_norm = re.sub(r'\s+', ' ', name).lower()
        if 'jkyw' not in name_norm:
            continue
        # Strip the JKYw/ prefix to expose the bare category
        cat = re.sub(r'^.*?jkyw\s*/\s*', '', name_norm).strip()
        if not cat or cat.startswith('trn '):
            continue
        angle_type = JOCKEY_ANGLE_TYPES.get(cat)
        if angle_type is None:
            for kw, t in sorted(JOCKEY_ANGLE_TYPES.items(),
                                key=lambda kv: -len(kv[0])):
                if kw in cat:
                    angle_type = t
                    break
        if angle_type is None:
            continue
        try:
            s = int(starts)
            wp = int(winpct)
        except ValueError:
            continue
        if not (1 <= s <= 99999) or wp > 100:
            continue
        key = (angle_type, s, wp)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'sign': sign or '',
            'name': name,
            'type': angle_type,
            'starts': s,
            'winpct': wp,
            'itm_pct': int(itm),
            'roi': float(roi),
        })
    return out


# Horse running-style indicator from the silks-header line: "(E 7)",
# "(E/P 3)", "(P 12)", "(S 5)", "(NA 0)". Normalize "E/P" → "ep".
_HORSE_STYLE_RE = re.compile(r'\(([A-Z]{1,2}(?:/[A-Z]{1,2})?)\s+\d+\)')


def _extract_horse_style(block_lines) -> str | None:
    for line in block_lines[:8]:  # style indicator lives at top of block
        m = _HORSE_STYLE_RE.search(line)
        if m:
            style = m.group(1).replace('/', '').lower()
            if style in ('e', 'ep', 'p', 's', 'na'):
                return style
    return None


def _jockey_angle_matches_today(angle_type: str,
                                today_surface: str | None,
                                today_furlongs: float | None,
                                today_class: str | None,
                                today_horse_style: str | None) -> bool:
    """True iff the parsed jockey-angle category applies to today's race
    AND this horse. Surface/distance/class match the race; style matches
    the horse."""
    if angle_type.startswith('style_'):
        target = angle_type.split('_', 1)[1]
        return today_horse_style is not None and today_horse_style == target
    # Surface/distance/class — reuse the same logic as trainer angles
    return _angle_matches_today(
        angle_type, today_surface, today_furlongs, today_class,
        blinkers_added_today=0, blinkers_removed_today=0,
        first_time_lasix=0,
    )


def jockey_angle_features(angles: list[dict],
                          today_surface: str | None,
                          today_furlongs: float | None,
                          today_class: str | None,
                          today_horse_style: str | None,
                          hot_threshold: int = 20,
                          min_starts: int = 10) -> dict:
    """Same shape as trainer_angle_features but for jockey angles."""
    matching = [a for a in angles if _jockey_angle_matches_today(
        a['type'], today_surface, today_furlongs, today_class,
        today_horse_style,
    )]
    if not matching:
        return {
            'jky_angle_winpct': None,
            'jky_angle_starts': None,
            'has_strong_jky_angle': None,
            'count_positive_jky_angles': None,
        }
    total_starts = sum(a['starts'] for a in matching)
    if total_starts > 0:
        weighted = sum(a['starts'] * a['winpct'] for a in matching) / total_starts
    else:
        weighted = None
    has_strong = any(
        a['winpct'] >= hot_threshold and a['starts'] >= min_starts
        for a in matching
    )
    count_pos = sum(1 for a in matching if a['sign'] == '+')
    return {
        'jky_angle_winpct': weighted,
        'jky_angle_starts': total_starts,
        'has_strong_jky_angle': int(has_strong),
        'count_positive_jky_angles': count_pos,
    }


def extract_pace_figures(block_lines):
    """Extract Brisnet pace figures (E1, E2, LP) from condensed PP race lines.

    Same figure block as extract_speed_figures: "E1 E2/ LP ±var ±var SPD".
    The CR column renders as a superscript prefix glued to the E1 token by
    pdfplumber (e.g. '¨§­74' = CR 106, E1 74), so E1 is the regular-digit
    tail of the token immediately before the "NN/" pace token. E2 is the
    NN of "NN/". LP is the FIRST 25-130 int that follows the pace token
    (before the ±variants), which is what the SPD extractor then walks past.

    Returns [(e1, e2, lp), ...] most recent first, deduped by race date.
    Each component is None when missing or out of the 25-130 range.
    """
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or d in races:
            continue
        toks = line.split()
        slash_i = next((i for i, t in enumerate(toks)
                        if _PP_PACE_TOKEN_RE.fullmatch(t)), None)
        if slash_i is None:
            continue

        # E2: digits of the NN/ token
        e2_str = toks[slash_i].rstrip('/')
        try:
            v = int(e2_str)
            e2 = v if 25 <= v <= 130 else None
        except ValueError:
            e2 = None

        # E1: regular-digit tail of the token before NN/, after stripping
        # the superscript CR prefix the font produces
        e1 = None
        if slash_i > 0:
            m = _PP_E1_TAIL_RE.search(toks[slash_i - 1])
            if m:
                v = int(m.group(1))
                if 25 <= v <= 130:
                    e1 = v

        # LP: first 25-130 int after the pace token, before any variants
        # or non-digit. Matches the layout the SPD extractor walks past.
        lp = None
        for t in toks[slash_i + 1:]:
            if _PP_VARIANT_RE.fullmatch(t):
                continue
            if not (t.isdigit() and t.isascii()):
                break
            v = int(t)
            if 25 <= v <= 130:
                lp = v
                break
            break

        races[d] = (e1, e2, lp)
    return [races[d] for d in sorted(races, reverse=True)]


# Brisnet PP font: superscript digits map to §¨©ª«¬\xad®¯° (verified against
# jockey weights, e.g. OcasioJ¨©§ = 120) and margin fractions to
# \x81=½ ‚=¼ ƒ=¾ (verified: winner-margin chain sums match the FIN call).
_SUP_DIGITS = {'§': 0, '¨': 1, '©': 2, 'ª': 3, '«': 4,
               '¬': 5, '\xad': 6, '®': 7, '¯': 8, '°': 9}
_SUP_FRACTIONS = {'\x81': 0.5, '‚': 0.25, 'ƒ': 0.75,   # ½ ¼ ¾
                  '\xb2': 0.05, '„': 0.1, '\xb3': 0.3}      # nose head neck
_SUP_CHARS = re.escape(''.join(list(_SUP_DIGITS) + list(_SUP_FRACTIONS)))
# The FIN call (position + superscript beaten lengths) is the token right
# before the jockey, who renders as Name + 3 superscript weight digits
_PP_FIN_RE = re.compile(
    r'(\d{1,2})([' + _SUP_CHARS + r']*)\s*'
    r"(?=[A-Z][A-Za-z'.]{2,}[" + re.escape(''.join(_SUP_DIGITS)) + r']{3})'
)


def _sup_to_lengths(sup):
    digits = ''.join(str(_SUP_DIGITS[c]) for c in sup if c in _SUP_DIGITS)
    frac = sum(_SUP_FRACTIONS[c] for c in sup if c in _SUP_FRACTIONS)
    return (int(digits) if digits else 0) + frac


def extract_beaten_lengths(block_lines, page_lines=None):
    """Beaten lengths in the horse's most recent race (0.0 = won, positive
    = lengths behind the winner), or None when unparseable / first-time
    starter. Horse blocks come from the page's left-crop text, where PP
    lines are truncated before the FIN call; pass page_lines so the
    full-layout copy (same line, longer) can be located by prefix."""
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or races.get(d) is not None:
            continue
        m = _PP_FIN_RE.search(line)
        if m is None and page_lines:
            key = line.strip()
            if len(key) >= 40:
                for fl in page_lines:
                    fls = fl.strip()
                    if len(fls) > len(key) and fls.startswith(key):
                        m = _PP_FIN_RE.search(fls)
                        if m:
                            break
        if m is None:
            races.setdefault(d, None)
            continue
        pos = int(m.group(1))
        races[d] = 0.0 if pos == 1 else _sup_to_lengths(m.group(2))
    return races[max(races)] if races else None


# Class-money token: claiming price for claiming races (MC12500, Clm 5000n4L),
# purse for maiden/allowance (Mdn 70k, Alw 34000). Same token format appears in
# PP race lines and in today's race header right before "Purse $...", so deltas
# compare like with like.
_CLASS_MONEY_RE = re.compile(
    r'\b(SOC|MOC|MC|Mdn|Clm|OC|Alw|Str|Hcp)\s?(\d[\d,]*)\s?(k?)')
_STAKES_PURSE_RE = re.compile(r'(\d{2,4})k\b')


def _class_money(s):
    m = _CLASS_MONEY_RE.search(s)
    if m:
        v = int(m.group(2).replace(',', ''))
        return v * 1000 if m.group(3) else v
    m = _STAKES_PURSE_RE.search(s)   # stakes: "RaceNameS 75k"
    return int(m.group(1)) * 1000 if m else None


def extract_horse_starts(block_lines):
    """Count unique past races in the horse's PP block. Brisnet displays
    up to ~10 PP race lines, so the count is exact for lightly-raced
    horses (the regime we care about for the FTS-density signal) and a
    lower bound of 10 for veterans. Zero = first-time starter."""
    return len({d for line in block_lines
                if (d := _pp_line_date(line)) is not None})


def _ols_slope(ys):
    """Simple OLS slope of ys against x = [0, 1, ..., n-1].
    Convention: x=0 is the OLDEST race, x=n-1 the MOST RECENT, so a
    positive slope means the metric is rising over time. Returns None
    when fewer than 2 points are present."""
    n = len(ys)
    if n < 2:
        return None
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(ys))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den else None


def extract_form_trajectory(block_lines, race_date, page_lines=None):
    """Phase E3: continuous trajectory features across the horse's last 5
    PP race lines. Captures improvement/decline patterns that the binary
    `improving` flag (last vs second-last only) cannot.

    Returns a dict with five keys, each None when insufficient data:
      * speed_fig_slope: OLS slope of speed figures over time (oldest→newest)
            so positive = improving form.
      * beaten_lengths_slope: OLS slope of beaten lengths over time. The
            sign convention is the RAW length: 0 = won, positive = behind,
            so a NEGATIVE slope means the horse is finishing closer to the
            winner over time (improving).
      * class_drop_count: number of class drops in the last 5 races
            (consecutive races where today's class < previous race's class).
            Reads from oldest to newest in the trailing window.
      * figure_high_recent: max(last 3 speed figs) / max(all stored figs).
            Ratio in (0, 1]; 1.0 means recent form is at lifetime peak.
      * races_in_60d: count of PP race lines dated within 60 days of
            today's race_date. Fitness/freshness indicator.
    """
    # Speed figures: most-recent first; reverse to oldest-first for the
    # slope so positive = improving.
    spd_pairs = extract_speed_figures(block_lines)
    spd_recent_to_old = [f for f, _ in spd_pairs[:5]]
    spd_old_to_recent = list(reversed(spd_recent_to_old))
    speed_fig_slope = _ols_slope(spd_old_to_recent)

    last3 = spd_recent_to_old[:3]
    figs_all = [f for f, _ in spd_pairs]
    if last3 and figs_all:
        lifetime_max = max(figs_all)
        figure_high_recent = max(last3) / lifetime_max if lifetime_max else None
    else:
        figure_high_recent = None

    # Beaten lengths per PP date — replicate extract_beaten_lengths but
    # keep the full per-date map rather than collapsing to most-recent.
    bl_by_date = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or bl_by_date.get(d) is not None:
            continue
        m = _PP_FIN_RE.search(line)
        if m is None and page_lines:
            key = line.strip()
            if len(key) >= 40:
                for fl in page_lines:
                    fls = fl.strip()
                    if len(fls) > len(key) and fls.startswith(key):
                        m = _PP_FIN_RE.search(fls)
                        if m:
                            break
        if m is None:
            bl_by_date.setdefault(d, None)
            continue
        pos = int(m.group(1))
        bl_by_date[d] = 0.0 if pos == 1 else _sup_to_lengths(m.group(2))
    bl_recent_to_old = [bl_by_date[d] for d in sorted(bl_by_date, reverse=True)
                        if bl_by_date[d] is not None][:5]
    bl_old_to_recent = list(reversed(bl_recent_to_old))
    beaten_lengths_slope = _ols_slope(bl_old_to_recent)

    # Class drops in the last 5 races (oldest→newest). Drop = current
    # class < previous class; count transitions, not absolute level.
    class_by_date = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or class_by_date.get(d) is not None:
            continue
        class_by_date[d] = _class_money(line[:60])
    class_recent_to_old = [class_by_date[d] for d in sorted(class_by_date, reverse=True)
                           if class_by_date[d] is not None][:5]
    class_old_to_recent = list(reversed(class_recent_to_old))
    if len(class_old_to_recent) >= 2:
        class_drop_count = sum(1 for i in range(1, len(class_old_to_recent))
                               if class_old_to_recent[i] < class_old_to_recent[i - 1])
    else:
        class_drop_count = None

    # Races in last 60 days — needs today's race_date for the window.
    if race_date is None:
        races_in_60d = None
    else:
        pp_dates = {d for line in block_lines
                    if (d := _pp_line_date(line)) is not None}
        races_in_60d = sum(1 for d in pp_dates if 0 <= (race_date - d).days <= 60)

    return {
        'speed_fig_slope':      speed_fig_slope,
        'beaten_lengths_slope': beaten_lengths_slope,
        'class_drop_count':     class_drop_count,
        'figure_high_recent':   figure_high_recent,
        'races_in_60d':         races_in_60d,
    }


def extract_last_class(block_lines):
    """Class money of the horse's most recent race, or None. Only the first
    60 chars are searched so Top Finishers / comment text can't match."""
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or races.get(d) is not None:
            continue
        races[d] = _class_money(line[:60])
    return races[max(races)] if races else None


# PP-line distance tokens: 6f, 5½ (going fused: "5½ft"), 1m, and route
# glyphs verified by final times on FP cards (1m ~1:41 < 1Ñ ~1:45 < 1ˆ ~1:47):
# ˆ = 1/16 mile, Ñ = 70 yards. Optional junk char before the number is a
# surface/inner-track marker (Ì à š æ).
_DIST_FRACTIONS = {'½': 0.5, '¼': 0.25, '¾': 0.75}
_MILE_GLYPHS = {'ˆ': 0.5, 'Ñ': 0.32}   # in furlongs past the whole miles
_PP_DIST_RE = re.compile(
    r'^\s*\d{1,2}[A-Za-z]{3}\d{2}\S*\s+[^\s\d]{0,2}(\d{1,2})([½¼¾ˆÑ]?)([mf]?)')


def _ppline_furlongs(line):
    m = _PP_DIST_RE.match(line)
    if not m:
        return None
    n, glyph, unit = int(m.group(1)), m.group(2), m.group(3)
    if glyph in _DIST_FRACTIONS:
        return n + _DIST_FRACTIONS[glyph]
    if glyph in _MILE_GLYPHS:
        return n * 8 + _MILE_GLYPHS[glyph]
    if unit == 'm':
        return n * 8.0
    if unit == 'f':
        return float(n)
    return None


def _header_furlongs(s):
    """Today's distance in furlongs from a plain-text race header line
    ('6 Furlongs', '1Mile.', '1 1/16 Miles', '1 Mile 70 Yards')."""
    m = re.search(r'(\d{1,2})\s*(½|\d\s*/\s*\d+)?\s*Furlongs?', s)
    if m:
        f = float(m.group(1))
        if m.group(2) == '½':
            f += 0.5
        elif m.group(2):
            num, den = re.split(r'\s*/\s*', m.group(2))
            f += float(num) / float(den)
        return f
    m = re.search(r'(\d)\s*(\d+\s*/\s*\d+)?\s*Miles?(?:\s*(?:and\s*)?(\d+)\s*Yards?)?', s)
    if m:
        miles = float(m.group(1))
        if m.group(2):
            num, den = re.split(r'\s*/\s*', m.group(2))
            miles += float(num) / float(den)
        f = miles * 8
        if m.group(3):
            f += float(m.group(3)) / 220.0
        return f
    return None


def extract_last_distance(block_lines):
    """Distance (furlongs) of the horse's most recent race, or None."""
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or races.get(d) is not None:
            continue
        races[d] = _ppline_furlongs(line)
    return races[max(races)] if races else None


def last_race_date_from_block(block):
    """Most recent past-race date in a horse's PP block, or None
    (first-time starters have no PP lines)."""
    dates = [d for d in (_pp_line_date(line) for line in block) if d]
    return max(dates, default=None)

_OWN_ANCHOR_RE = re.compile(r'^\s*(?:(\d{1,2}(?:/\d{1,2})?)\s+)?Own:')


def parse_brisnet(text, track_code='GP', race_date=None):
    pages = text.split('\f')
    races = defaultdict(lambda: {'conditions': '', 'purse': '', 'surface': '', 'horses': []})
    current_race = 1

    for i, page in enumerate(pages):
        if len(page.strip()) < 50:
            continue

        lines = page.split('\n')
        header = lines[0]

        # ── Race number from header (check first 10 lines; pdfplumber may offset) ─
        for hline in lines[:10]:
            race_m = re.search(r'\bRace\s+(\d+)\b', hline)
            if race_m:
                current_race = int(race_m.group(1))
                break

        # ── Race conditions from header ───────────────────────────────────────
        # Brisnet header layout (varies by track): a class code (Mdn / MC /
        # Clm / Alw / STK / etc.) starts the conditions block, and the day
        # of week ("Sunday, June 14, 2026 Race 1") closes it. The previous
        # regex was too restrictive — required digit-suffix-digit pattern —
        # and failed on "Clm 8000n2L Ì 5½ Furlongs", capturing nothing for
        # 99% of PP races. Two-pass anchor:
        #   1. class-code anchor (MSW/Mdn/Clm/Alw/STK/etc.) → day-of-week
        #   2. track-name anchor fallback for stakes races like
        #      "SnJnCpo-G3 *1 Mile" where the race name precedes class info
        if current_race and not races[current_race]['conditions']:
            day_pat = r'(?=\s+(?:Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)day,)'
            cond_m = re.search(
                r'(?:MSW|MCL|MOC|MC|MdnCl|Mdn|MDN|MAIDEN|Clm|CLM|AOC|OC|Alw|ALW'
                r'|Str|STR|SOC|Hcp|HCP|STK|Stk)\b.+?' + day_pat,
                header
            )
            if not cond_m:
                cond_m = re.search(
                    r'(?:Gulfstream Park|Charles Town|Fairmount Park'
                    r'|Evangeline Downs|Santa Anita Park|Saratoga'
                    r'|Mahoning Valley|Delta Downs|Fair Grounds|Laurel Park)\s+'
                    r'[`TM]*\s*(.+?)' + day_pat,
                    header
                )
                if cond_m:
                    cond_m = re.match(r'\s*(.+)', cond_m.group(1))
            if cond_m:
                races[current_race]['conditions'] = cond_m.group(0).strip()[:120]
            # Surface
            if '(T)' in header or 'Turf' in header:
                races[current_race]['surface'] = 'Turf'
            elif 'AW' in header or 'Tapeta' in header or 'All Weather' in header:
                races[current_race]['surface'] = 'AW'
            else:
                races[current_race]['surface'] = 'Dirt'

        # ── Today's distance from the plain-text header lines ────────────────
        if current_race and races[current_race].get('dist_furlongs') is None:
            for hline in lines[:10]:
                f = _header_furlongs(hline)
                if f:
                    races[current_race]['dist_furlongs'] = f
                    break

        # ── Purse / class money: the race header may share a page with horse
        # blocks (condensed y-format), so check every page ────────────────────
        purse_m = re.search(r'Purse\s+\$([\d,]+)', page)
        if purse_m and current_race and not races[current_race]['purse']:
            races[current_race]['purse'] = f"${purse_m.group(1)}"
            # class token renders right before "Purse" with no space between
            tok = re.search(_CLASS_MONEY_RE.pattern + r'\S*Purse', page)
            if tok:
                v = int(tok.group(2).replace(',', ''))
                races[current_race]['class_money'] = v * 1000 if tok.group(3) else v
            else:  # stakes etc: the purse is the class
                races[current_race]['class_money'] = int(purse_m.group(1).replace(',', ''))

        # ── Is this a horse page? (has 'Own:') ────────────────────────────────
        if 'Own:' not in page:
            continue

        # ── Prime Power map: keyed by PP# from full-page horse-name lines ─────
        # Full-page format: "{PP}  {Name} ... Prime Power: {val} ({rank})"
        pp_power_map = {}
        for line in lines:
            pm = re.match(r'^\s*(\d{1,2})\s+[A-Z][A-Za-z].*?Prime Power:\s*([\d.]+)\s*\((\d+)', line)
            if pm:
                pp_power_map[int(pm.group(1))] = (pm.group(2), pm.group(3))
        # CT-style fallback: Prime Power in page header without PP# prefix
        if not pp_power_map:
            ppm = re.search(r'Prime\s+P(?:ower)?[:\s]*([\d.]+)\s*\((\d+)', lines[0])
            if ppm:
                pp_power_map[-1] = (ppm.group(1), ppm.group(2))

        # ── Find every Own: line on this page ─────────────────────────────────
        # DPv1 recall fix: pdftotext often collapses the silks column onto the
        # owner line, so the anchor reads "10/1  Own: ..." rather than starting
        # at "Own:". The v1 anchor (`^Own:` or `^<digits> Own:`) silently
        # dropped every such horse — 11 of 85 blocks on gpx0509y.pdf alone, and
        # a lost block is a lost row, not a visible parse failure. One leading
        # numeric token (a program number OR a fractional ML price) is allowed.
        own_indices = [j for j, line in enumerate(lines)
                       if _OWN_ANCHOR_RE.match(line)]

        for oi, own_idx in enumerate(own_indices):
            # ── Per-horse state ───────────────────────────────────────────────
            horse = '?'; pp_num = 0; ml = '?'; trainer = '?'; trainer_stats = ''
            jockey = '?'; sire = '?'; prime_power = '?'; pp_rank = '?'
            days_off = 0; pos_angles = []; neg_angles = []; claim_price = None
            jt_winpct = None

            # ── ML odds / PP# from the anchor line's leading token ────────────
            own_line = lines[own_idx]
            om = _OWN_ANCHOR_RE.match(own_line)
            lead = om.group(1)
            if lead and '/' in lead:
                ml = lead                       # collapsed silks column
            elif lead:
                pp_num = int(lead)

            # ── Horse name: search backward from Own: ─────────────────────────
            for k in range(own_idx - 1, max(0, own_idx - 6), -1):
                prev = lines[k]
                # Country-of-origin suffix like "(Ire)" or "(GB)" may appear between
                # the horse name and the class condition "(CLM 5000)".  The optional
                # non-capturing group consumes it so group 1 holds only the bare name.
                hm = re.search(r'([A-Z][A-Za-z\'"\-\. ]+?)(?:\s*\([A-Z][A-Za-z]{0,3}\))?\s+\([A-Z/EP]+\s+\d+\)', prev)
                if hm:
                    horse = hm.group(1).strip()
                    claim_m = re.search(r'\$(\d{1,3},?\d{3})', prev)
                    if claim_m:
                        claim_price = claim_m.group(1)
                    # The horse-name line is itself prefixed with the program
                    # number ("4   I Wanna Be Me (E/P 1) ..."), which is the
                    # most reliable source. v1 only read it via a backward scan
                    # requiring [A-Z][a-z], so single-letter first words
                    # ("H Abarrio", "I Wanna Be Me") produced pp_num=0 and the
                    # horse was dropped.
                    pm = re.match(r'^\s*(\d{1,2})\s+[A-Z]', prev)
                    if pm:
                        pp_num = int(pm.group(1))
                    break

            if pp_num == 0:
                for k in range(own_idx - 1, max(0, own_idx - 8), -1):
                    nm = re.match(r'^\s*(\d{1,2})\s+[A-Z]', lines[k])
                    if nm:
                        pp_num = int(nm.group(1))
                        break

            # ── Prime Power from pre-built map ────────────────────────────────
            if pp_num in pp_power_map:
                prime_power, pp_rank = pp_power_map[pp_num]
            elif -1 in pp_power_map:
                prime_power, pp_rank = pp_power_map[-1]

            # ── Block: own_idx-4 to next Own: (exclusive) ────────────────────
            block_start = max(0, own_idx - 4)
            block_end = own_indices[oi + 1] if oi + 1 < len(own_indices) else len(lines)
            block = lines[block_start:block_end]

            # ── Scan block for remaining fields ───────────────────────────────
            for bi, line in enumerate(block):

                # Prime Power fallback (block may include it for some formats)
                if prime_power == '?':
                    ppm = re.search(r'Prime Power:\s*([\d.]+)\s*\((\d+)', line)
                    if ppm:
                        prime_power = ppm.group(1)
                        pp_rank = ppm.group(2)

                # ML odds: silks line starts with fraction/integer then color word.
                # Horse header lines ("1 Army Medic (E 7) ...") also start with an
                # integer + capitalized word — the running-style parens "(E 7)"
                # distinguish them, so exclude any line containing that pattern.
                # 'Trnr:' is NOT excluded: PDF column collapse often merges the
                # silks cell with the trainer cell, putting both on one line —
                # the ^ anchor still pins ML odds at the line start.
                if ml == '?':
                    stripped = line.strip()
                    ml_m = re.match(r'^(\d+/\d+|\d+)\s+[A-Z][a-z]', stripped)
                    if (ml_m and 'Own:' not in line
                            and 'Sire' not in line
                            and not re.search(r'\([A-Z/EP]+\s+\d+\)', stripped)):
                        val = ml_m.group(1)
                        if '/' in val or (val.isdigit() and 1 <= int(val) <= 99):
                            ml = val

                # Trainer: "(N/N N%)", "(N N-N-N N%)", or name-only fallback
                if trainer == '?':
                    tm = re.search(r'Trnr:\s*([^\n(]+?)\s*\((\d+)\s*/\s*(\d+)\s+(\d+)%\)', line)
                    if tm:
                        trainer = tm.group(1).strip()
                        trainer_stats = f"{tm.group(2)} sts {tm.group(4)}%"
                    else:
                        tm2 = re.search(r'Trnr:\s*([^\n(]+?)\s*\((\d+)\s+(\d+)-(\d+)-(\d+)\s+(\d+)%\)', line)
                        if tm2:
                            trainer = tm2.group(1).strip()
                            trainer_stats = f"{tm2.group(2)} sts {tm2.group(3)}-{tm2.group(4)}-{tm2.group(5)} {tm2.group(6)}%"
                        else:
                            # Fallback: grab name before stats even if stat format is unrecognized.
                            # Ensures signal matching fires even when the stats parens use a novel layout.
                            tm3 = re.search(r'Trnr:\s*([A-Za-z][^\n(]+?)\s*\(', line)
                            if tm3:
                                trainer = tm3.group(1).strip()

                # Jockey: "LASTNAME FIRSTNAME (N N-N-N N%)" or "(N/ N N%)"
                if jockey == '?':
                    jm = re.search(r'^([A-Z]{2,}(?:\s+[A-Z]+){0,3})\s+\(\d+[\s/]', line)
                    if jm:
                        jockey = jm.group(1).title()

                # J/T combo win rate. Condensed PPs carry it as
                # "JKYw/ Trn L60 <starts> <win%> <itm%> <roi>"; full PPs may
                # use a "J/T" or "Jky/Trn" stats line instead.
                if jt_winpct is None:
                    jt_m = re.search(r'JKYw/\s*Trn\s+L60\s+\d+\s+(\d+)%', line, re.IGNORECASE)
                    if jt_m:
                        jt_winpct = int(jt_m.group(1))
                    elif re.search(r'\bJ/?T\b|Jky/Trn', line, re.IGNORECASE):
                        pct_m = re.search(r'(\d+)%', line)
                        if pct_m:
                            jt_winpct = int(pct_m.group(1))

                # Sire
                if sire == '?':
                    sm = re.search(r'Sire\s*:\s*=?([A-Z][A-Za-z\'"\-\. \(\)]+?)\s*\(', line)
                    if sm:
                        sire_raw = sm.group(1).strip()
                        sire = re.sub(r'\s*\([^)]*\)\s*$', '', sire_raw).strip()
                    elif re.search(r'Sire\s*:\s*$', line.strip()):
                        abs_next = block_start + bi + 1
                        if abs_next < len(lines):
                            nxt = lines[abs_next].strip().lstrip('=')
                            sn = re.match(r'([A-Z][A-Za-z\'"\-\. ]+?)\s*[\($]', nxt)
                            if sn:
                                sire = sn.group(1).strip()

                # Days off
                if days_off == 0:
                    dm = re.search(r'(\d+)\s+days\s+away', line)
                    if dm:
                        days_off = int(dm.group(1))

                # Angles
                if 'ñ' in line:
                    for ang in re.findall(r'ñ\s*([^ñ×\n]+)', line):
                        a = ang.strip()
                        if len(a) > 4:
                            pos_angles.append(a[:65])
                if '×' in line:
                    for ang in re.findall(r'×\s*([^ñ×\n]+)', line):
                        a = ang.strip()
                        if len(a) > 4:
                            neg_angles.append(a[:65])

            # ── Days off from the most recent PP race-line date ──────────────
            # ('N days away' text above is absent from condensed PPs, so this
            # computed value is the real source)
            last_race = last_race_date_from_block(block)
            if race_date and last_race and last_race < race_date:
                days_off = (race_date - last_race).days

            beaten_len = extract_beaten_lengths(block, lines)
            last_class = extract_last_class(block)
            last_dist  = extract_last_distance(block)
            horse_starts = extract_horse_starts(block)
            traj_feats = extract_form_trajectory(block, race_date, lines)

            # ── Speed figures from PP lines in block ──────────────────────────
            spd_figs   = extract_speed_figures(block)  # [(figure, surface), ...]
            recent_spd = [f for f, _ in spd_figs[:5]]
            best_spd   = max((f for f, _ in spd_figs), default=None)
            best_spd_turf = max((f for f, s in spd_figs if s == 'T'),  default=None)
            best_spd_aw   = max((f for f, s in spd_figs if s == 'AW'), default=None)
            improving = (len(recent_spd) >= 3 and
                         recent_spd[0] > recent_spd[1] > recent_spd[2])

            # ── Pace figures (E1, E2, LP) — same PP block, max across races ──
            pace_figs = extract_pace_figures(block)
            best_e1   = max((e for e, _, _ in pace_figs if e is not None), default=None)
            best_e2   = max((e for _, e, _ in pace_figs if e is not None), default=None)
            best_late = max((l for _, _, l in pace_figs if l is not None), default=None)

            # ── Workout features — bottom-of-block workout history ──────────
            works = extract_workouts(block, race_date)
            wfeats = workout_features(works)

            # ── Equipment-change features (Phase B) ─────────────────────────
            eq_feats = extract_equipment_features(block)

            # ── Distance/surface records (Phase D) ──────────────────────────
            today_surface_str = races[current_race].get('surface')
            today_furlongs = _header_furlongs(
                races[current_race].get('conditions', '')
            )
            career_recs = extract_career_records(block)
            ds_feats = distance_surface_record_features(career_recs, today_surface_str)
            combo_s, combo_w = distance_surface_combo_record(
                block, today_furlongs, today_surface_str
            )

            # ── Connection-change features (Phase C) ────────────────────────
            past_jks = extract_past_jockeys(block)
            conn_feats = connection_features(
                today_jockey=jockey if jockey != '?' else None,
                past_jockeys=past_jks,
                jt_winpct=jt_winpct,
            )

            # ── Trainer-angle features (Phase E1) ───────────────────────────
            trn_angles = extract_trainer_angles(block)
            today_class = _today_class_type(races[current_race].get('conditions',''))
            tang_feats = trainer_angle_features(
                trn_angles,
                today_surface_str,
                today_furlongs,
                today_class,
                eq_feats['blinkers_added_today'] or 0,
                eq_feats['blinkers_removed_today'] or 0,
                eq_feats['first_time_lasix'] or 0,
            )

            # ── Jockey-angle features (Phase E2) ────────────────────────────
            today_horse_style = _extract_horse_style(block)
            jky_angles = extract_jockey_angles(block)
            jang_feats = jockey_angle_features(
                jky_angles, today_surface_str, today_furlongs,
                today_class, today_horse_style,
            )

            # ── Hot J/T and 0% J/T from angles ────────────────────────────────
            _HOT_JT_RE = re.compile(r'hot.*?(?:trainer|jockey|j/?t|combo)', re.IGNORECASE)
            hot_jt = any(_HOT_JT_RE.search(a) for a in pos_angles)
            # Angle fallback for 0% when no dedicated J/T stats line was found
            if jt_winpct is None:
                for _a in neg_angles:
                    if re.search(r'j/?t\b|trainer.*jockey|jockey.*trainer', _a, re.IGNORECASE) \
                            and '0%' in _a:
                        jt_winpct = 0
                        break
            jt_zero = (jt_winpct == 0)

            if horse == '?' or pp_num == 0:
                continue

            horse_data = {
                'pp': pp_num, 'name': horse, 'ml': ml,
                'trainer': trainer, 'trainer_stats': trainer_stats,
                'jockey': jockey, 'sire': sire,
                'prime_power': prime_power, 'pp_rank': pp_rank,
                'days_off': days_off, 'claim': claim_price,
                'pos_angles': pos_angles[:4], 'neg_angles': neg_angles[:3],
                'recent_spd': recent_spd, 'best_spd': best_spd,
                'best_spd_turf': best_spd_turf, 'best_spd_aw': best_spd_aw,
                'best_e1': best_e1, 'best_e2': best_e2, 'best_late': best_late,
                'bullet_count_60d': wfeats['bullet_count_60d'],
                'days_since_last_workout': wfeats['days_since_last_workout'],
                'workout_avg_pace': wfeats['workout_avg_pace'],
                'workout_count_60d': wfeats['workout_count_60d'],
                'has_recent_bullet': wfeats['has_recent_bullet'],
                'blinkers_added_today': eq_feats['blinkers_added_today'],
                'blinkers_removed_today': eq_feats['blinkers_removed_today'],
                'first_time_lasix': eq_feats['first_time_lasix'],
                'weight_change': eq_feats['weight_change'],
                'equipment_change': eq_feats['equipment_change'],
                'dist_wins': ds_feats['dist_wins'],
                'dist_starts': ds_feats['dist_starts'],
                'surface_wins': ds_feats['surface_wins'],
                'surface_starts': ds_feats['surface_starts'],
                'surface_winpct': ds_feats['surface_winpct'],
                'combo_starts': combo_s,
                'combo_wins': combo_w,
                'jockey_change': conn_feats['jockey_change'],
                'jockey_first_time': conn_feats['jockey_first_time'],
                'hot_jt_combo': conn_feats['hot_jt_combo'],
                'trainer_today_angle_winpct': tang_feats['trainer_today_angle_winpct'],
                'trainer_today_angle_starts': tang_feats['trainer_today_angle_starts'],
                'has_strong_angle': tang_feats['has_strong_angle'],
                'count_positive_angles': tang_feats['count_positive_angles'],
                'jky_angle_winpct': jang_feats['jky_angle_winpct'],
                'jky_angle_starts': jang_feats['jky_angle_starts'],
                'has_strong_jky_angle': jang_feats['has_strong_jky_angle'],
                'count_positive_jky_angles': jang_feats['count_positive_jky_angles'],
                'improving': improving, 'jt_zero': jt_zero,
                'running_style': today_horse_style,
                'jt_winpct': jt_winpct, 'beaten_len': beaten_len,
                'last_class': last_class, 'last_dist': last_dist,
                'horse_starts': horse_starts,
                'speed_fig_slope':      traj_feats['speed_fig_slope'],
                'beaten_lengths_slope': traj_feats['beaten_lengths_slope'],
                'class_drop_count':     traj_feats['class_drop_count'],
                'figure_high_recent':   traj_feats['figure_high_recent'],
                'races_in_60d':         traj_feats['races_in_60d'],
            }

            if not any(h['name'] == horse for h in races[current_race]['horses']):
                races[current_race]['horses'].append(horse_data)

    # class/distance deltas need today's values (parsed from the race header)
    # and the horse's last-race values, so compute them after both passes
    for race in races.values():
        today_class = race.get('class_money')
        today_dist = race.get('dist_furlongs')
        for h in race['horses']:
            lc = h.get('last_class')
            h['class_delta'] = (today_class - lc) \
                if today_class is not None and lc is not None else None
            ld = h.get('last_dist')
            h['distance_delta'] = round(today_dist - ld, 2) \
                if today_dist is not None and ld is not None else None

    return dict(races)

def extract_file_date(filepath, track_code, text=''):
    """Return the race date from the filename pattern or file text; None if not found."""
    stem = Path(filepath).stem.upper()
    tc = track_code.upper()

    # TRACKMMDDDYYUSA  e.g. CT050926USA, GP050826USA
    m = re.match(rf'^{re.escape(tc)}(\d{{2}})(\d{{2}})(\d{{2}})USA$', stem)
    if m:
        try:
            return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # TRACKx?MMDD...  e.g. CTX0507Y, GPX0508X, EVD0509Y, FPK0519Y
    m = re.match(rf'^{re.escape(tc)}[A-Z]?(\d{{2}})(\d{{2}})', stem)
    if m:
        try:
            return date(date.today().year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # Fall back: scan first 3 000 chars of extracted text
    if text:
        sample = text[:3000]
        dm = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', sample)
        if dm:
            month, day, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if year < 100:
                year += 2000
            try:
                return date(year, month, day)
            except ValueError:
                pass
        MONTHS = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        dm = re.search(
            r'\b(January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            sample, re.IGNORECASE,
        )
        if dm:
            try:
                return date(int(dm.group(3)), MONTHS[dm.group(1).lower()], int(dm.group(2)))
            except ValueError:
                pass

    return None


def ml_to_float(ml_str):
    """Convert morning-line odds string to decimal odds (fractional + 1).

    US ML odds are expressed as 'to-1' fractions: '8/5' means 8-to-5, which
    pays 8/5 + 1 = 2.6 per unit stake. Plain integers ('5') mean 5-to-1 = 6.0.

    Examples: '15/1' → 16.0, '8/5' → 2.6, '7/2' → 4.5, '1/1' → 2.0, '5' → 6.0
    """
    if not ml_str or ml_str == '?':
        return None
    if '/' in ml_str:
        try:
            num, den = ml_str.split('/')
            return round(int(num) / int(den) + 1, 2)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(ml_str) + 1
    except ValueError:
        return None

# ---------------------------------------------------------------------------
# DPv1 entry-grain output
# ---------------------------------------------------------------------------

# The PP feature columns written to ``entry_pp_features``. Order is the table's
# column order. ``bucket`` 9 = "PP Data" in dpv1_feature_config.json.
PP_FEATURE_COLUMNS: tuple[str, ...] = (
    # --- market (a feature, NOT an anchor) ---
    "pp_ml_decimal",
    # --- Brisnet composite ratings ---
    "pp_prime_power", "pp_prime_power_rank",
    # --- speed figures ---
    "pp_best_speed", "pp_best_speed_turf", "pp_best_speed_aw",
    "pp_last_speed", "pp_avg_speed_last3", "pp_speed_improving",
    # --- pace figures ---
    "pp_best_e1", "pp_best_e2", "pp_best_late",
    # --- form trajectory ---
    "pp_speed_fig_slope", "pp_beaten_lengths_slope", "pp_class_drop_count",
    "pp_figure_high_recent", "pp_races_in_60d",
    # --- workouts ---
    "pp_workout_count_60d", "pp_bullet_count_60d", "pp_has_recent_bullet",
    "pp_days_since_last_workout", "pp_workout_avg_pace",
    # --- equipment / weight ---
    "pp_blinkers_added_today", "pp_blinkers_removed_today",
    "pp_first_time_lasix", "pp_weight_change", "pp_equipment_change",
    # --- career / distance / surface records ---
    "pp_career_starts", "pp_dist_starts", "pp_dist_wins",
    "pp_surface_starts", "pp_surface_wins", "pp_surface_winpct",
    "pp_combo_starts", "pp_combo_wins",
    # --- connections ---
    "pp_jockey_change", "pp_jockey_first_time", "pp_jt_winpct",
    "pp_hot_jt_combo", "pp_jt_zero",
    # --- Brisnet proprietary angles ---
    "pp_trainer_angle_winpct", "pp_trainer_angle_starts",
    "pp_has_strong_trainer_angle", "pp_positive_trainer_angles",
    "pp_jky_angle_winpct", "pp_jky_angle_starts",
    "pp_has_strong_jky_angle", "pp_positive_jky_angles",
    # --- context ---
    "pp_days_off", "pp_beaten_len_last", "pp_last_class", "pp_last_dist",
    "pp_class_delta", "pp_distance_delta", "pp_running_style",
    "pp_pos_angle_count", "pp_neg_angle_count",
)


def _num(v):
    """Coerce to a JSON/SQLite-friendly number, or None."""
    if v is None or v is True or v is False:
        return int(v) if isinstance(v, bool) else None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _bool(v):
    return None if v is None else int(bool(v))


def horse_to_pp_features(h: dict) -> dict:
    """Map one parsed horse dict onto the ``entry_pp_features`` columns."""
    recent = [s for s in (h.get("recent_spd") or []) if s is not None]
    avg3 = sum(recent[:3]) / len(recent[:3]) if recent[:3] else None
    return {
        "pp_ml_decimal": ml_to_float(h.get("ml")),
        "pp_prime_power": _num(h.get("prime_power")),
        "pp_prime_power_rank": _num(h.get("pp_rank")),
        "pp_best_speed": _num(h.get("best_spd")),
        "pp_best_speed_turf": _num(h.get("best_spd_turf")),
        "pp_best_speed_aw": _num(h.get("best_spd_aw")),
        "pp_last_speed": _num(recent[0]) if recent else None,
        "pp_avg_speed_last3": _num(avg3),
        "pp_speed_improving": _bool(h.get("improving")),
        "pp_best_e1": _num(h.get("best_e1")),
        "pp_best_e2": _num(h.get("best_e2")),
        "pp_best_late": _num(h.get("best_late")),
        "pp_speed_fig_slope": _num(h.get("speed_fig_slope")),
        "pp_beaten_lengths_slope": _num(h.get("beaten_lengths_slope")),
        "pp_class_drop_count": _num(h.get("class_drop_count")),
        "pp_figure_high_recent": _bool(h.get("figure_high_recent")),
        "pp_races_in_60d": _num(h.get("races_in_60d")),
        "pp_workout_count_60d": _num(h.get("workout_count_60d")),
        "pp_bullet_count_60d": _num(h.get("bullet_count_60d")),
        "pp_has_recent_bullet": _bool(h.get("has_recent_bullet")),
        "pp_days_since_last_workout": _num(h.get("days_since_last_workout")),
        "pp_workout_avg_pace": _num(h.get("workout_avg_pace")),
        "pp_blinkers_added_today": _bool(h.get("blinkers_added_today")),
        "pp_blinkers_removed_today": _bool(h.get("blinkers_removed_today")),
        "pp_first_time_lasix": _bool(h.get("first_time_lasix")),
        "pp_weight_change": _num(h.get("weight_change")),
        "pp_equipment_change": _bool(h.get("equipment_change")),
        "pp_career_starts": _num(h.get("horse_starts")),
        "pp_dist_starts": _num(h.get("dist_starts")),
        "pp_dist_wins": _num(h.get("dist_wins")),
        "pp_surface_starts": _num(h.get("surface_starts")),
        "pp_surface_wins": _num(h.get("surface_wins")),
        "pp_surface_winpct": _num(h.get("surface_winpct")),
        "pp_combo_starts": _num(h.get("combo_starts")),
        "pp_combo_wins": _num(h.get("combo_wins")),
        "pp_jockey_change": _bool(h.get("jockey_change")),
        "pp_jockey_first_time": _bool(h.get("jockey_first_time")),
        "pp_jt_winpct": _num(h.get("jt_winpct")),
        "pp_hot_jt_combo": _bool(h.get("hot_jt_combo")),
        "pp_jt_zero": _bool(h.get("jt_zero")),
        "pp_trainer_angle_winpct": _num(h.get("trainer_today_angle_winpct")),
        "pp_trainer_angle_starts": _num(h.get("trainer_today_angle_starts")),
        "pp_has_strong_trainer_angle": _bool(h.get("has_strong_angle")),
        "pp_positive_trainer_angles": _num(h.get("count_positive_angles")),
        "pp_jky_angle_winpct": _num(h.get("jky_angle_winpct")),
        "pp_jky_angle_starts": _num(h.get("jky_angle_starts")),
        "pp_has_strong_jky_angle": _bool(h.get("has_strong_jky_angle")),
        "pp_positive_jky_angles": _num(h.get("count_positive_jky_angles")),
        "pp_days_off": _num(h.get("days_off")),
        "pp_beaten_len_last": _num(h.get("beaten_len")),
        "pp_last_class": _num(h.get("last_class")),
        "pp_last_dist": _num(h.get("last_dist")),
        "pp_class_delta": _num(h.get("class_delta")),
        "pp_distance_delta": _num(h.get("distance_delta")),
        "pp_running_style": h.get("running_style"),
        "pp_pos_angle_count": len(h.get("pos_angles") or []),
        "pp_neg_angle_count": len(h.get("neg_angles") or []),
    }


def track_from_filename(path) -> str | None:
    """Track code from a PP filename stem, or None when unrecognised."""
    stem = Path(path).stem.upper()
    for pref in sorted(FILENAME_PREFIX_TO_TRACK, key=len, reverse=True):
        if stem.startswith(pref):
            return FILENAME_PREFIX_TO_TRACK[pref]
    return None


def parse_pp_file(filepath, track_code: str | None = None) -> dict:
    """Parse one PP file into a JSON-able dict.

    Returns ``{"file", "track", "race_date", "races": [...], "error"}``.
    Never raises on a bad file — the caller reports the failure rate.
    """
    path = Path(filepath)
    track = (track_code or track_from_filename(path) or "").upper() or None
    out = {"file": path.name, "path": str(path), "track": track,
           "race_date": None, "races": [], "n_horses": 0, "error": None}
    if track is None:
        out["error"] = "unrecognised track prefix"
        return out
    try:
        text = extract_text(path)
    except Exception as exc:                       # noqa: BLE001 - report, don't crash
        out["error"] = f"text extraction failed: {exc}"
        return out
    if not text or len(text.strip()) < 500:
        out["error"] = "no extractable text (scanned or anti-bot placeholder?)"
        return out

    race_date = extract_file_date(path, track, text)
    out["race_date"] = race_date.isoformat() if race_date else None
    if race_date is None:
        out["error"] = "could not determine race date"
        return out

    try:
        races = parse_brisnet(text, track, race_date)
    except Exception as exc:                       # noqa: BLE001
        out["error"] = f"parse failed: {exc}"
        return out

    for rn, race in sorted(races.items()):
        horses = []
        for h in race["horses"]:
            rec = {"program_num": h["pp"], "horse_name": h["name"],
                   "trainer": h.get("trainer"), "jockey": h.get("jockey"),
                   "sire": h.get("sire"), "ml": h.get("ml")}
            rec.update(horse_to_pp_features(h))
            horses.append(rec)
        out["races"].append({
            "race_num": rn,
            "surface": race.get("surface"),
            "conditions": race.get("conditions"),
            "purse": race.get("purse"),
            "class_money": race.get("class_money"),
            "dist_furlongs": race.get("dist_furlongs"),
            "horses": horses,
        })
    out["n_horses"] = sum(len(r["horses"]) for r in out["races"])
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print("Usage: python brisnet_pp_parser.py [--json] <file.pdf> [TRACK]")
        raise SystemExit(1)
    result = parse_pp_file(args[0], args[1] if len(args) > 1 else None)
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"{result['file']}  track={result['track']}  "
              f"date={result['race_date']}")
        if result["error"]:
            print(f"  ERROR: {result['error']}")
        print(f"  {len(result['races'])} races, {result['n_horses']} horses")
        for r in result["races"]:
            names = ", ".join(f"{h['program_num']}:{h['horse_name']}"
                              for h in r["horses"])
            print(f"    R{r['race_num']:>2} ({len(r['horses'])}): {names}")
