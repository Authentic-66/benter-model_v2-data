"""Extract Cross-Track Iron Rules signals from Doug's v10 workbook.

The sheet layout (see ``_iron_rules_raw.txt`` for a raw dump) is two
sections — universal FADE signals and universal POSITIVE signals — each
introduced by a section header row, followed by a column-header row, then
data rows. Each data row is one signal.

We emit a structured JSON document that Doug reviews before Phase 3F
priors get applied. **Nothing in the model changes until Doug curates
the JSON.** This is a deliberate checkpoint.

Signal schema (one entry per row in the sheet):

    id                — deterministic string, e.g. "iron_rule_005"
    signal_name       — raw first-column text
    signal_type       — 'jockey' | 'trainer' | 'sire' | 'universal'
    direction         — 'fade' | 'bet'
    tracks_confirmed  — list of track codes parsed from column 3
    roi_range         — raw column-4 text
    notes             — raw column-5 text (can be long — update logs live here)
    confidence        — 'iron' | 'high' | 'medium' (canonical, from emoji symbols)
    confidence_raw    — original cell content for auditing
    action_raw        — raw column-7 text
    applies_to_gp     — True if 'GP' is in tracks_confirmed
    scope             — 'specific' if a single track named, 'multi' otherwise
    raw_row           — source row number in the sheet
    review_status     — always 'unreviewed' at extraction time; Doug edits

Usage
-----
    python v10_signal_extractor.py \\
        --workbook "Previous Versions of Benter Model/benter_model_v10_master.xlsx" \\
        --sheet "Cross-Track Iron Rules" \\
        --out scripts/v10_iron_rules_extracted.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path

import openpyxl


log = logging.getLogger("v10_extractor")


# Section markers in the sheet
SECTION_FADE = "UNIVERSAL FADE SIGNALS"
SECTION_POSITIVE = "UNIVERSAL POSITIVE SIGNALS"
# Sheet title (row 1) — skip; not a signal
SHEET_TITLE_PREFIX = "CROSS-TRACK IRON RULES"

# Column-header sentinel — indicates we're on the header row, not a signal
HEADER_SENTINELS = {"Signal", "SIGNAL"}

# Track-code pattern: 2-4 uppercase letters (with optional parenthetical)
TRACK_CODE_RE = re.compile(r"\b([A-Z]{2,4})\b")

# Universal scope tokens — treated as applying to every track in our corpus
UNIVERSAL_TRACK_TOKENS = {"ALL"}


@dataclass
class Signal:
    id: str
    signal_name: str
    signal_type: str
    direction: str
    tracks_confirmed: list[str]
    roi_range: str | None
    notes: str | None
    confidence: str
    confidence_raw: str
    action_raw: str
    applies_to_gp: bool
    gp_applicability_source: str    # 'tracks' | 'notes' | 'universal' | 'none'
    gp_direction_needs_review: bool  # True when notes flip the direction at GP
    scope: str
    raw_row: int
    review_status: str = "unreviewed"
    reviewer_notes: str = ""


def _normalise_confidence(raw: str | None) -> str:
    """Map raw confidence text like 'HIGH ❌' or 'IRON ✅' to a canonical tier."""
    if not raw:
        return "medium"
    upper = raw.upper()
    if "IRON" in upper:
        return "iron"
    if "HIGH" in upper:
        return "high"
    if "MED" in upper:
        return "medium"
    return "medium"


def _parse_tracks(raw: str | None) -> list[str]:
    """`'CD, CT, KEE, BEL, AQU, SA'` -> `['CD', 'CT', 'KEE', 'BEL', 'AQU', 'SA']`.

    Ignores parenthetical qualifiers like `'AQU (+$24 n=251)'` — we keep only
    the code. Uses a regex so `'SA (turf)'` cleanly yields `'SA'`.
    """
    if not raw:
        return []
    codes: list[str] = []
    for chunk in re.split(r"[,;/&]", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = TRACK_CODE_RE.search(chunk)
        if m:
            codes.append(m.group(1))
    # De-dup while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _direction_from_action(action: str | None) -> str:
    if not action:
        return "unknown"
    if "FADE" in action.upper():
        return "fade"
    if "BET" in action.upper():
        return "bet"
    return "unknown"


def _canonical_type(raw: str | None) -> str:
    """Map free-form type text to a canonical category."""
    if not raw:
        return "unknown"
    t = raw.strip().lower()
    if "jock" in t:
        return "jockey"
    if "train" in t:
        return "trainer"
    if "sire" in t:
        return "sire"
    if "univ" in t or "all" in t:
        return "universal"
    return t


def _looks_like_section_header(row_cells: list[str | None]) -> str | None:
    """Return 'fade'/'positive' if this row is a section header, else None."""
    first = (row_cells[0] or "").strip().upper()
    if SECTION_FADE in first:
        return "fade"
    if SECTION_POSITIVE in first:
        return "positive"
    return None


def _is_sheet_title(row_cells: list[str | None]) -> bool:
    first = (row_cells[0] or "").strip().upper()
    return first.startswith(SHEET_TITLE_PREFIX)


def _looks_like_column_header(row_cells: list[str | None]) -> bool:
    return (row_cells[0] or "").strip() in HEADER_SENTINELS


_GP_WORD = re.compile(r"\bGP\b")


def _applies_to_gp(
    tracks: list[str],
    action_raw: str | None,
    notes: str | None,
    primary_direction: str,
) -> tuple[bool, str, bool]:
    """Return ``(applies, source, direction_needs_review)``.

    Source is 'tracks' if GP is in the confirmed-tracks list,
    'universal' if the signal is universal-scope, 'notes' if GP is only
    mentioned in the free-text notes/action, else 'none'.

    ``direction_needs_review`` is True when source is 'notes' AND the
    surrounding text mentions FADE or BET in a direction opposite of the
    primary — Doug then decides how to record the GP-specific direction.
    """
    if "GP" in tracks:
        return True, "tracks", False
    if any(t in UNIVERSAL_TRACK_TOKENS for t in tracks):
        return True, "universal", False
    for text in (action_raw, notes):
        if not isinstance(text, str):
            continue
        upper = text.upper()
        if not _GP_WORD.search(upper):
            continue
        # GP is mentioned in text; look for a nearby direction word.
        # If notes says "FADE at GP" but primary direction is "bet",
        # the direction flips at GP.
        flip = False
        for m in _GP_WORD.finditer(upper):
            window = upper[max(m.start() - 30, 0): m.end() + 30]
            if primary_direction == "bet" and ("FADE" in window
                                                or "NEGATIVE" in window):
                flip = True
            elif primary_direction == "fade" and ("BET" in window
                                                   or "POSITIVE" in window):
                flip = True
        return True, "notes", flip
    return False, "none", False


def extract_signals(
    workbook_path: Path, sheet_name: str,
) -> list[Signal]:
    wb = openpyxl.load_workbook(str(workbook_path), data_only=True)
    ws = wb[sheet_name]
    signals: list[Signal] = []
    current_section: str | None = None
    seq = 0

    for row_num, row in enumerate(ws.iter_rows(values_only=True), 1):
        cells = list(row)
        first = (cells[0] or "").strip() if cells and isinstance(cells[0], str) else ""
        if not first:
            continue

        if _is_sheet_title(cells):
            continue
        section = _looks_like_section_header(cells)
        if section:
            current_section = section
            continue
        if _looks_like_column_header(cells):
            continue

        # We're on a data row.
        signal_name = first
        signal_type_raw = cells[1] if len(cells) > 1 else None
        tracks_raw = cells[2] if len(cells) > 2 else None
        roi_range = cells[3] if len(cells) > 3 else None
        notes = cells[4] if len(cells) > 4 else None
        conf_raw = cells[5] if len(cells) > 5 else ""
        action_raw = cells[6] if len(cells) > 6 else ""

        canonical_type = _canonical_type(str(signal_type_raw) if signal_type_raw else None)
        tracks = _parse_tracks(str(tracks_raw) if tracks_raw else None)
        conf = _normalise_confidence(str(conf_raw) if conf_raw else None)
        action_direction = _direction_from_action(str(action_raw) if action_raw else None)
        # Section can override / confirm direction
        direction = action_direction if action_direction != "unknown" else (
            current_section or "unknown"
        )
        # Section 'positive' == direction 'bet'
        if direction == "positive":
            direction = "bet"

        applies_to_gp, gp_source, gp_needs_review = _applies_to_gp(
            tracks,
            str(action_raw) if action_raw else None,
            str(notes) if notes else None,
            direction,
        )
        if any(t in UNIVERSAL_TRACK_TOKENS for t in tracks):
            scope = "universal"
        elif len(tracks) == 1:
            scope = "specific"
        elif len(tracks) > 1:
            scope = "multi"
        else:
            scope = "unknown"

        seq += 1
        signals.append(Signal(
            id=f"iron_rule_{seq:03d}",
            signal_name=signal_name,
            signal_type=canonical_type,
            direction=direction,
            tracks_confirmed=tracks,
            roi_range=str(roi_range) if roi_range is not None else None,
            notes=str(notes) if notes is not None else None,
            confidence=conf,
            confidence_raw=str(conf_raw or "").strip(),
            action_raw=str(action_raw or "").strip(),
            applies_to_gp=bool(applies_to_gp),
            gp_applicability_source=gp_source,
            gp_direction_needs_review=bool(gp_needs_review),
            scope=scope,
            raw_row=row_num,
        ))

    return signals


def summarise(signals: list[Signal]) -> dict:
    total = len(signals)
    by_type: dict[str, int] = {}
    by_direction: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    gp_count = 0
    for s in signals:
        by_type[s.signal_type] = by_type.get(s.signal_type, 0) + 1
        by_direction[s.direction] = by_direction.get(s.direction, 0) + 1
        by_confidence[s.confidence] = by_confidence.get(s.confidence, 0) + 1
        if s.applies_to_gp:
            gp_count += 1
    return {
        "total": total,
        "by_type": by_type,
        "by_direction": by_direction,
        "by_confidence": by_confidence,
        "gp_applicable": gp_count,
    }


def _cli() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--workbook",
        default="Previous Versions of Benter Model/benter_model_v10_master.xlsx",
    )
    p.add_argument("--sheet", default="Cross-Track Iron Rules")
    p.add_argument("--out", default="scripts/v10_iron_rules_extracted.json")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    workbook_path = Path(args.workbook)
    if not workbook_path.exists():
        log.error("workbook not found: %s", workbook_path)
        return 1

    log.info("Reading %s :: %s", workbook_path, args.sheet)
    signals = extract_signals(workbook_path, args.sheet)
    log.info("Extracted %d signals", len(signals))

    summary = summarise(signals)
    document = {
        "extraction_date": date.today().isoformat(),
        "source_workbook": workbook_path.name,
        "source_sheet": args.sheet,
        "extractor_version": "phase3f_v1",
        "review_instructions": (
            "Doug: please review the signals below. For each, either leave "
            "review_status='unreviewed' (skip in application), set it to "
            "'approved' (apply as prior), 'rejected' (do not apply), or "
            "'modified' (with edits in reviewer_notes). Priors are applied "
            "ONLY to signals with review_status='approved' or 'modified'."
        ),
        "summary": summary,
        "signals": [asdict(s) for s in signals],
    }

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    log.info("Wrote %s", out_path)
    log.info("Summary: %s", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
