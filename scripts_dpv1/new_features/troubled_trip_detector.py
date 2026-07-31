"""Trouble detection from Equibase trip comments.

Doug on ``last_race_troubled_trip`` (rank 2): *"Trip comments are helpful and
can point out abnormalties from a gate mishap to being boxed-in, etc."*
And on ``pace_progression_last_race``: *"Trip comments will matter here,
especially if the horse ran into unforseen or unpredictable issues"* — which
is why the two are built together and activated together.

Trip comments are present on 100% of the 207,976 entries, so this is one of
the highest-coverage new signals available in the corpus.

Format
------
Comments are comma-separated, whitespace-stripped abbreviations, e.g.::

    bidtightqtrs,bmpd1/8
    3wd,pushout,bump1/8p
    dweltstart,urged,tire
    4wd,bump&lostrider1/8
    stedyst,keen,dueltn

Because spaces are stripped, tokens run together ("lackrmupr"), so detection
is substring matching on the lowercased comment rather than word matching.

What counts as trouble
----------------------
Incidents that cost the horse ground through no choice of its own: gate
mishaps, contact, being stopped, and losing the rider. Deliberately NOT
counted as trouble:

* **Wide trips** ("3wd", "4w"). A wide trip is a tactical/positional outcome,
  not an incident, and it is already carried by the pace features.
* **Drifting / lugging / bearing.** These are the horse's own error and read
  more as a soundness or greenness signal than a troubled trip.

Both are still detected and exposed as their own categories so the choice
can be revisited without re-deriving anything.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Category -> regex of chart abbreviations. Patterns are matched against the
# lowercased, space-stripped comment.
TROUBLE_PATTERNS: dict[str, str] = {
    "gate": r"dwelt|dwlt|brokeslow|brkslw|slowstart|slwst|brokein|brokeout|"
            r"fractious|rear|unruly|refusedtoload|leftgate|bobbl|stumbl|stmbl",
    "contact": r"bump|bmp|brush|brshd|clip|struck|hit|collid|sideswip",
    "stopped": r"steady|stead|stdy|stedy|check|chck|ckd|tookup|tkup|takenup|"
               r"shutoff|shutdown|shuf|blocked|blkd|boxed|boxdin|inclose|"
               r"noroom|norm\b|lackroom|lackrm|lackrmupr|trapped|trap|"
               r"pinch|squeez|squzd|waitfor|wait\d",
    "altered": r"altered|altrd|swerv|swrv|veer|cutoff|forcedout|forcdout|"
               r"carriedout|carrdout|carriedwide|steadiedwide",
    "catastrophe": r"lostrider|unseat|fell|spill|pulledup|pldup|bolted|"
                   r"brokedown|vanned|eased|eas'd|easd",
}

# Detected and reported, but not folded into the trouble flag — see module
# docstring.
NON_TROUBLE_PATTERNS: dict[str, str] = {
    "wide": r"\d\s?-?\s?\d?w(d|ide)?\b|wideturn|widetrip|widest",
    "self_error": r"drift|drftd|drfto|lugg?ed|lugin|lugout|borein|boreout|"
                  r"greenly|green\b|erratic",
}

_TROUBLE_RE = {k: re.compile(v) for k, v in TROUBLE_PATTERNS.items()}
_NON_TROUBLE_RE = {k: re.compile(v) for k, v in NON_TROUBLE_PATTERNS.items()}

TROUBLE_CATEGORIES = tuple(TROUBLE_PATTERNS)
ALL_CATEGORIES = TROUBLE_CATEGORIES + tuple(NON_TROUBLE_PATTERNS)


def _clean(comment: object) -> str | None:
    if not isinstance(comment, str):
        return None
    c = comment.strip().lower()
    return c if c else None


def detect_categories(comment: object) -> set[str]:
    """Return the set of category names firing on one trip comment."""
    c = _clean(comment)
    if c is None:
        return set()
    hits = {name for name, rx in _TROUBLE_RE.items() if rx.search(c)}
    hits |= {name for name, rx in _NON_TROUBLE_RE.items() if rx.search(c)}
    return hits


def is_troubled(comment: object) -> bool | None:
    """True/False if the comment is readable, None if it is missing.

    NULL propagates: an entry with no trip comment gets no opinion, rather
    than a default of "no trouble".
    """
    c = _clean(comment)
    if c is None:
        return None
    return any(rx.search(c) for rx in _TROUBLE_RE.values())


def detect_frame(comments: pd.Series) -> pd.DataFrame:
    """Vectorized-ish detection over a Series of trip comments.

    Returns a DataFrame indexed like ``comments`` with one Int8 column per
    category plus ``troubled`` (Int8, NA where the comment is missing) and
    ``trouble_kinds`` (comma-joined category names, for spot-checking).
    """
    cleaned = comments.map(_clean)
    out = pd.DataFrame(index=comments.index)
    readable = cleaned.notna()
    filled = cleaned.fillna("")

    for name, rx in {**_TROUBLE_RE, **_NON_TROUBLE_RE}.items():
        hit = filled.str.contains(rx, regex=True)
        out[name] = hit.where(readable).astype("boolean").astype("Int8")

    trouble_any = np.zeros(len(comments), dtype=bool)
    for name in TROUBLE_CATEGORIES:
        trouble_any |= out[name].fillna(0).astype(bool).to_numpy()
    out["troubled"] = pd.Series(trouble_any, index=comments.index).where(
        readable).astype("boolean").astype("Int8")

    kinds = []
    for i in range(len(out)):
        row = out.iloc[i]
        kinds.append(",".join(c for c in ALL_CATEGORIES if row[c] == 1) or None)
    out["trouble_kinds"] = kinds
    return out


if __name__ == "__main__":
    samples = [
        "bidtightqtrs,bmpd1/8",
        "3wd,pushout,bump1/8p",
        "dueledinside,weakened",
        "tookupoffspill1/8p",
        "4wd,bump&lostrider1/8",
        "pace,duel,repel,clear",
        "stedyst,keen,dueltn",
        "dweltstart,urged,tire",
        "rail,bid,gain,flatnd",
        "4w,lackrmupr,tookup",
        "trackins,drftoutstr",
        None,
        "",
    ]
    for s in samples:
        print(f"{str(s):<28} troubled={str(is_troubled(s)):<5} "
              f"kinds={sorted(detect_categories(s))}")
