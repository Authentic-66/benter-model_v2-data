"""Shared primitives for the DPv1 (Doug Parks v1) multi-track feature pipeline.

This module owns the things that more than one DPv1 feature module needs:

* Paths + the ``scripts/`` import shim, so we can reuse the Phase 3C
  prior-lookup engine (``_prior_by_entity_expanding`` and friends) without
  copying it or modifying ``scripts/``.
* The **class ladder** — ``races.class_level`` is NULL for all 28,105 races
  in the corpus, so class has to be derived from race_type + claiming_price
  + purse. Doug ranked ``class_change_from_last`` a 1 ("A significant change
  in class, up or down, is a big factor imo"), so this ladder is load-bearing.
* Distance / pace / surface bucketing shared across buckets 3, 4, 6 and 8.

Nothing here writes to the database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- import shim -----------------------------------------------------------
# Reuse the Phase 3C helpers. scripts/ is read-only for DPv1 purposes.
DPV1_DIR = Path(__file__).resolve().parent
REPO_ROOT = DPV1_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bayesian_shrinkage import shrink_rate_vec          # noqa: E402,F401
from time_decay import decay_weight_vec                 # noqa: E402,F401
from feature_builder import (                           # noqa: E402
    _prior_by_entity_expanding,
    _prior_by_entity_windowed,
    _prior_last_value,
    _prior_days_to_event,
    _classify_pace_type,
)

DEFAULT_DB = SCRIPTS_DIR / "racing_full.db"
DEFAULT_CONFIG = DPV1_DIR / "dpv1_feature_config.json"
FEATURES_TABLE = "entry_features_dpv1"
SPEED_TABLE = "computed_speed_figures_dpv1"

# Track ids, per Phase 4A load.
TRACK_CODES = {1: "GP", 2: "CT", 3: "MNR"}


# ---------------------------------------------------------------------------
# Class ladder
# ---------------------------------------------------------------------------
#
# tier * 10 + offset, where offset in [0, 9] positions the race inside its
# tier. Claiming races are positioned by claiming price (track-independent —
# a $10k claimer is a $10k claimer at GP, CT or MNR). Non-claiming races are
# positioned by log purse, which IS track-sensitive: an MNR allowance really
# does draw weaker company than a GP allowance, so registering that as a
# class drop when a horse ships down is the intended behaviour, not a bug.

CLASS_TIERS: dict[str, float] = {
    "MAIDENCLAIMING": 1.0,
    "CLAIMING": 2.0,
    "WAIVERCLAIMING": 2.0,
    "STARTERALLOWANCE": 3.0,
    "STARTEROPTIONALCLAIMING": 3.0,
    "STARTERHANDICAP": 3.0,
    "MAIDENOPTIONALCLAIMING": 3.0,
    "MAIDENSPECIALWEIGHT": 4.0,
    "STARTERSTAKES": 4.5,
    "ALLOWANCE": 5.0,
    "ALLOWANCEOPTIONALCLAIMING": 5.0,
    "RATINGS OPTIONAL CLAIMING": 5.0,
    "HANDICAP": 6.0,
    "RATINGS HANDICAP": 6.0,
    "STAKES": 7.0,
}

# Longest-prefix-first so ALLOWANCEOPTIONALCLAIMING never matches ALLOWANCE,
# and STARTERSTAKES never matches STARTER*/STAKES.
_TIER_PREFIXES: list[tuple[str, float]] = sorted(
    CLASS_TIERS.items(), key=lambda kv: -len(kv[0])
)

# Claiming-price breakpoints -> offset 0..9.
CLAIM_BREAKS = [2500, 4000, 5000, 7500, 10000, 16000, 25000, 40000, 62500]

# log10(purse) linear map -> offset 0..9. $5k purse = 0, $200k purse = 9.
PURSE_LOG_LO = 3.7
PURSE_LOG_HI = 5.3

# Race types whose class is set by the claiming tag rather than the purse.
_CLAIMING_TYPES = ("CLAIM",)


def normalize_race_type(race_type: str | None) -> str | None:
    """Collapse the raw chart race_type to a canonical tier key.

    Chart values run from plain ``'CLAIMING'`` to
    ``'STARTERSTAKES Claiming Crown Iron Horse S.'``; we only care about the
    leading category token.
    """
    if not isinstance(race_type, str) or not race_type.strip():
        return None
    rt = race_type.strip().upper()
    for prefix, _tier in _TIER_PREFIXES:
        if rt.startswith(prefix):
            return prefix
    return None


def class_tier(race_type: str | None) -> float | None:
    key = normalize_race_type(race_type)
    return CLASS_TIERS.get(key) if key else None


def _claim_offset(price: float | None) -> float | None:
    if price is None or not np.isfinite(price) or price <= 0:
        return None
    return float(sum(1 for b in CLAIM_BREAKS if price >= b))


def _purse_offset(purse: float | None) -> float | None:
    if purse is None or not np.isfinite(purse) or purse <= 0:
        return None
    lp = np.log10(purse)
    frac = (lp - PURSE_LOG_LO) / (PURSE_LOG_HI - PURSE_LOG_LO)
    return float(np.clip(round(9.0 * frac), 0, 9))


def class_score_vec(
    race_type: pd.Series, claiming_price: pd.Series, purse: pd.Series
) -> pd.Series:
    """Vectorized class ladder score. NaN where race_type is unusable.

    A claiming-type race is scored off its claiming tag when one is present,
    falling back to purse when the tag is missing. Everything else is scored
    off purse.
    """
    tiers = race_type.map(class_tier).astype("float64")
    keys = race_type.map(normalize_race_type)
    is_claim = keys.fillna("").str.contains(_CLAIMING_TYPES[0])

    claim_off = claiming_price.astype("float64").map(_claim_offset)
    purse_off = purse.astype("float64").map(_purse_offset)

    offset = np.where(
        is_claim & claim_off.notna(),
        claim_off.astype("float64"),
        purse_off.astype("float64"),
    )
    score = tiers * 10.0 + pd.Series(offset, index=race_type.index)
    # A tier with no usable offset still carries real information (the tier
    # itself), so fall back to the bare tier rather than dropping the row.
    score = score.where(score.notna(), tiers * 10.0)
    return score


# ---------------------------------------------------------------------------
# Distance / surface / pace bucketing
# ---------------------------------------------------------------------------

SPRINT_ROUTE_CUTOFF_YARDS = 1540  # 7f — matches Phase 3C


def dist_bucket_vec(distance_yards: pd.Series) -> pd.Series:
    """sprint / route, NaN-preserving."""
    d = distance_yards.astype("float64")
    return pd.Series(
        np.where(d.isna(), None,
                 np.where(d < SPRINT_ROUTE_CUTOFF_YARDS, "sprint", "route")),
        index=distance_yards.index,
        dtype="object",
    )


def distance_change_bucket_vec(
    now_yards: pd.Series, prev_yards: pd.Series
) -> pd.Series:
    """Doug's rank-2 four-way bucket: ``<prev>_to_<now>``.

    Doug's note: "Distance changes can be significant. If a horse has ran
    route races then moves to a sprint, they will 'hopefully' be more fit for
    the shorter distance. But, if they have not had any workouts it is
    questionable. Horses who have run sprints unsuccesfully and move to a
    route sometimes do better, but breeding and workouts are a factor."

    NULL for first-time starters (no prior distance to change from).
    """
    now_b = dist_bucket_vec(now_yards)
    prev_b = dist_bucket_vec(prev_yards)
    both = now_b.notna() & prev_b.notna()
    return pd.Series(
        np.where(both, prev_b.astype(str) + "_to_" + now_b.astype(str), None),
        index=now_yards.index,
        dtype="object",
    )


PACE_STYLES = ("front", "stalk", "mid", "close")


def parse_pace_positions(pace_json: str | None) -> list[int]:
    """Ordered running positions from a chart's pace-call JSON.

    Chart tokens are ``<position><margin>`` — see ``_classify_pace_type`` in
    scripts/feature_builder.py for the disambiguation rule, which we mirror
    here so that pace_progression and pace_type agree.
    """
    if not isinstance(pace_json, str) or not pace_json:
        return []
    try:
        d = json.loads(pace_json)
    except json.JSONDecodeError:
        return []
    out: list[int] = []
    for label, tok in d.items():
        if label in ("Start", "_extra_1") or not isinstance(tok, str) or not tok:
            continue
        if (len(tok) >= 3 and tok[:2] in {"10", "11", "12", "13", "14"}
                and (tok[2].isalpha() or "/" in tok[2:])):
            out.append(int(tok[:2]))
        elif tok[0].isdigit():
            out.append(int(tok[0]))
    return out


def early_pace_position(pace_json: str | None) -> int | None:
    """Position at the first non-Start call. NULL when uncallable."""
    pos = parse_pace_positions(pace_json)
    return pos[0] if pos else None


def pace_progression(pace_json: str | None) -> float | None:
    """Positions gained from the first call to the finish.

    Positive = the horse improved its position through the race; negative =
    it faded. Doug's note on this feature: "Trip comments will matter here,
    especially if the horse ran into unforseen or unpredictable issues" —
    which is why ``last_race_troubled_trip`` is built alongside it and both
    are activated together.
    """
    pos = parse_pace_positions(pace_json)
    if len(pos) < 2:
        return None
    return float(pos[0] - pos[-1])


def style_from_position(pos: int | float | None) -> str | None:
    if pos is None or (isinstance(pos, float) and not np.isfinite(pos)):
        return None
    p = int(pos)
    if p <= 2:
        return "front"
    if p <= 4:
        return "stalk"
    if p <= 6:
        return "mid"
    return "close"


# ---------------------------------------------------------------------------
# Small shared utilities
# ---------------------------------------------------------------------------

def grouped_prior_rate(
    df: pd.DataFrame,
    key_cols: list[str],
    prior_rate: float,
    k: float,
    value_col: str = "is_win",
    null_when_empty: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Prior-only shrunk rate for an arbitrary composite key.

    Returns ``(rate, starts)`` aligned to ``df``'s row order. "Prior" means
    strictly-earlier race dates — same-day races are excluded, so a feature
    can never see the card it is being computed for.

    ``null_when_empty=True`` returns NaN instead of the bare prior when the
    entity has no prior starts in the cell at all. Use it for horse-level
    cells (no evidence about *this* horse) and leave it False for
    population-level cells where the prior is a defensible estimate.
    """
    local = df[["entry_id", "race_date_dt", value_col] + key_cols].copy()
    local["one"] = 1.0
    local["_key"] = list(zip(*(local[c] for c in key_cols)))
    local["_key"], _ = pd.factorize(local["_key"], sort=False)
    rolled = _prior_by_entity_expanding(
        local, entity_col="_key", value_cols=[value_col, "one"], prefix="g",
    )
    rolled = df[["entry_id"]].merge(rolled, on="entry_id", how="left")
    events = rolled[f"g_{value_col}"].to_numpy()
    starts = rolled["g_one"].to_numpy()
    rate = shrink_rate_vec(events, starts, prior_rate, k)
    if null_when_empty:
        rate = np.where(starts == 0, np.nan, rate)
    return rate, starts


def as_int8(series: pd.Series) -> pd.Series:
    """Boolean-ish series -> nullable Int8, preserving NA."""
    return series.astype("boolean").astype("Int8")
