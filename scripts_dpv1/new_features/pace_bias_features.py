"""Pace-shape and track-bias features (Doug's buckets 6 and 8).

Doug on ``pace_progression_last_race`` (rank 2): *"Trip comments will matter
here, especially if the horse ran into unforseen or unpredictable issues"* —
``last_race_troubled_trip`` is activated alongside it for exactly that
reason, so a big negative progression can be read against whether the horse
was stopped or bumped.

Pace projection without leakage
-------------------------------
``pace_pressure_in_race`` describes today's race, but it is built only from
each entrant's **prior** starts: every runner's projected style comes from
races already run. No part of today's result is consulted, so the feature is
available pre-post exactly as a handicapper would have it.

Track bias
----------
Bias is measured on a 90-day trailing window per ``(track, surface)``, from
races strictly before the race being scored. Rail/outside bias compares the
win rate of inside (or outermost) posts against the field-share those posts
would win under no bias, which normalises out field-size differences between
a 6-horse CT card and a 12-horse GP turf race.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import (  # noqa: E402
    _prior_by_entity_windowed, _prior_by_entity_expanding, shrink_rate_vec,
    style_from_position, PACE_STYLES,
)

# Projected-style vocabulary Doug's catalog uses for
# early_pace_position_projected: front / press / off.
STYLE_TO_PROJECTED = {"front": "front", "stalk": "press",
                      "mid": "off", "close": "off"}

BIAS_RATIO_HOT = 1.15    # posts winning >15% more than their share = bias
BIAS_MIN_STARTS = 150    # minimum 90-day sample before we call a bias


def _dominant_style_last_3(raw: pd.DataFrame) -> pd.Series:
    """Most common own-race style over the horse's last <=3 prior starts."""
    s = raw[["entry_id", "horse_id", "race_date_dt", "own_style"]].sort_values(
        ["horse_id", "race_date_dt", "entry_id"]
    )
    shifts = [s.groupby("horse_id")["own_style"].shift(i) for i in (1, 2, 3)]
    mat = pd.concat(shifts, axis=1).to_numpy()

    dominant = np.full(len(s), None, dtype=object)
    for i in range(len(s)):
        vals = [v for v in mat[i] if isinstance(v, str)]
        if not vals:
            continue
        # Ties break toward the most recent start, which is vals[0].
        best, best_n = vals[0], 0
        for v in set(vals):
            n = vals.count(v)
            if n > best_n:
                best, best_n = v, n
        dominant[i] = best
    s = s.assign(running_style_last_3=dominant)
    return raw[["entry_id"]].merge(
        s[["entry_id", "running_style_last_3"]], on="entry_id", how="left"
    )["running_style_last_3"]


def compute_pace(raw: pd.DataFrame, ctx: dict, cfg: dict,
                 active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    prev = ctx["prev"]

    if "pace_progression_last_race" in active:
        out["pace_progression_last_race"] = prev["prev_pace_progression"]

    projected = None
    if {"early_pace_position_projected", "pace_pressure_in_race",
            "expected_pace_shape"} & active:
        # Projection = style of the most recent prior start.
        projected = prev["prev_own_style"].map(STYLE_TO_PROJECTED)
    if "early_pace_position_projected" in active:
        out["early_pace_position_projected"] = projected

    if {"pace_pressure_in_race", "expected_pace_shape"} & active:
        front = (projected == "front").astype(int)
        n_front = front.groupby(raw["race_id"]).transform("sum")
        # Horses with no prior start have no projection; if most of the field
        # is unprojectable the count is not trustworthy.
        n_known = projected.notna().astype(int).groupby(
            raw["race_id"]).transform("sum")
        shape = pd.Series(
            np.where(n_known < 3, None,
                     np.where(n_front >= 3, "hot",
                              np.where(n_front == 2, "moderate", "slow"))),
            index=raw.index, dtype="object",
        )
        if "pace_pressure_in_race" in active:
            out["pace_pressure_in_race"] = shape
        if "expected_pace_shape" in active:
            out["expected_pace_shape"] = shape

    if "running_style_last_3" in active:
        out["running_style_last_3"] = _dominant_style_last_3(raw)
    return out


def compute_bias(raw: pd.DataFrame, cfg: dict,
                 active: set[str]) -> pd.DataFrame:
    """Post and running-style bias per (track, surface), 90-day trailing."""
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    window = cfg["defaults"]["bias_window_days"]
    wanted = {"rail_bias_flag", "outside_bias_flag", "track_bias_running_style",
              "post_position_win_pct_at_track"}
    if not (wanted & active):
        return out

    if "post_position_win_pct_at_track" in active:
        local = raw[["entry_id", "race_date_dt", "is_win", "track_id",
                     "post_pos"]].copy()
        local["one"] = 1.0
        local["_key"] = list(zip(local["track_id"], local["post_pos"]))
        local["_key"], _ = pd.factorize(local["_key"], sort=False)
        rolled = _prior_by_entity_expanding(
            local, entity_col="_key", value_cols=["is_win", "one"], prefix="pp",
        )
        rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")
        d = cfg["defaults"]
        out["post_position_win_pct_at_track"] = shrink_rate_vec(
            rolled["pp_is_win"].to_numpy(), rolled["pp_one"].to_numpy(),
            d["shrinkage_prior_win_rate"],
            d["shrinkage_k_defaults"]["post_at_track"],
        )

    if not ({"rail_bias_flag", "outside_bias_flag",
             "track_bias_running_style"} & active):
        return out

    # One windowed pass over (track, surface) carrying every numerator we need.
    local = raw[["entry_id", "race_date_dt", "track_id", "surface"]].copy()
    local["one"] = 1.0
    win = raw["is_win"].astype(float)
    local["wins"] = win
    is_rail = (raw["post_pos"] <= 2).astype(float)
    is_out = (raw["post_pos"] >= raw["field_size"] - 1).astype(float)
    local["rail_starts"] = is_rail
    local["rail_wins"] = is_rail * win
    local["out_starts"] = is_out
    local["out_wins"] = is_out * win
    for st in PACE_STYLES:
        local[f"win_{st}"] = (raw["own_style"] == st).astype(float) * win

    value_cols = ["one", "wins", "rail_starts", "rail_wins",
                  "out_starts", "out_wins"] + [f"win_{s}" for s in PACE_STYLES]
    local["_key"] = list(zip(local["track_id"], local["surface"]))
    local["_key"], _ = pd.factorize(local["_key"], sort=False)
    rolled = _prior_by_entity_windowed(
        local, entity_col="_key", value_cols=value_cols,
        window_days=window, prefix="b",
    )
    rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")

    starts = rolled["b_one"].to_numpy()
    enough = starts >= BIAS_MIN_STARTS

    def _bias_flag(seg_starts: np.ndarray, seg_wins: np.ndarray) -> pd.Series:
        # Expected wins for the segment under no bias = the segment's share of
        # starts times all wins in the window.
        with np.errstate(invalid="ignore", divide="ignore"):
            share = np.where(starts > 0, seg_starts / starts, np.nan)
            expected = share * rolled["b_wins"].to_numpy()
            ratio = np.where(expected > 0, seg_wins / expected, np.nan)
        flag = np.where(enough & np.isfinite(ratio), ratio >= BIAS_RATIO_HOT,
                        None)
        return pd.Series(flag, index=raw.index).astype("boolean").astype("Int8")

    if "rail_bias_flag" in active:
        out["rail_bias_flag"] = _bias_flag(
            rolled["b_rail_starts"].to_numpy(), rolled["b_rail_wins"].to_numpy())
    if "outside_bias_flag" in active:
        out["outside_bias_flag"] = _bias_flag(
            rolled["b_out_starts"].to_numpy(), rolled["b_out_wins"].to_numpy())

    if "track_bias_running_style" in active:
        style_mat = np.column_stack(
            [rolled[f"b_win_{s}"].to_numpy() for s in PACE_STYLES])
        total = style_mat.sum(axis=1)
        idx = style_mat.argmax(axis=1)
        codes = np.array(PACE_STYLES, dtype=object)
        out["track_bias_running_style"] = pd.Series(
            np.where(enough & (total > 0), codes[idx], None),
            index=raw.index, dtype="object",
        )
    return out


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    a = compute_pace(raw, ctx, cfg, active)
    b = compute_bias(raw, cfg, active)
    return a.merge(b, on="entry_id", how="left")
