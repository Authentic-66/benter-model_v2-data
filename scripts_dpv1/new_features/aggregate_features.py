"""Career, connection and at-track aggregates — correctly aligned.

Why DPv1 re-implements these instead of calling ``scripts/feature_builder.py``
-----------------------------------------------------------------------------
The Phase 3C helpers ``_prior_by_entity_expanding`` and
``_prior_by_entity_windowed`` return their rows sorted by
``(entity, race_date, entry_id)`` with a fresh ``RangeIndex``. Several call
sites in ``scripts/feature_builder.py`` then assign the result straight onto
an entry-ordered frame::

    rolled = _prior_by_entity_expanding(df_w, "horse_id", ["one"], "horse")
    out["career_starts"] = rolled["horse_one"]      # positional, not by key

``out`` is in ``entries.id`` order and ``rolled`` is in horse order, so the
values land on the wrong rows. Measured against a SQL ground-truth count of
prior starts, the v1 path reproduces the correct value on **9.8%** of sampled
entries (chance level); merging on ``entry_id`` instead reproduces it on
**100%**.

The affected v1 outputs are the career counts and rates, every trainer and
jockey rolling/contextual win rate, and the horse's at-track and
surface/condition rates — roughly two dozen features, including four Doug
ranked 1. ``_prior_last_value``-derived features (last_race_*, weight and
distance deltas, gate break) merge on ``entry_id`` in v1 and are unaffected.

``scripts/`` is left untouched per the DPv1 brief — this module supersedes
those code paths for DPv1 only, and every result here is joined on
``entry_id``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import (  # noqa: E402
    grouped_prior_rate, shrink_rate_vec, dist_bucket_vec,
    _prior_by_entity_expanding, _prior_by_entity_windowed,
    _prior_days_to_event,
)
from cross_track_features import _per_track_prior_counts, _pick_by_track  # noqa: E402


def _aligned(raw: pd.DataFrame, rolled: pd.DataFrame) -> pd.DataFrame:
    """Join a prior-lookup result back onto entry order by key, never by position."""
    return raw[["entry_id"]].merge(rolled, on="entry_id", how="left")


# ---------------------------------------------------------------------------
# Bucket 3 — career + last-race form
# ---------------------------------------------------------------------------

def compute_recent_form(raw: pd.DataFrame, ctx: dict, cfg: dict,
                        active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    prev, career = ctx["prev"], ctx["career"]
    d = cfg["defaults"]

    simple = {
        "last_race_finish_pos": "prev_finish_pos",
        "last_race_beaten_lengths": "prev_beaten_lengths",
        "last_race_field_size": "prev_field_size",
        "last_race_speed_figure": "prev_speed_figure_own",
    }
    for name, src in simple.items():
        if name in active:
            out[name] = prev[src].to_numpy()
    for name in ("last_race_days_ago", "days_since_last_race"):
        if name in active:
            out[name] = prev["prev_days_ago"].to_numpy()

    starts = career["career_starts"].to_numpy()
    if "career_starts" in active:
        out["career_starts"] = starts.astype("int64")
    if "career_wins" in active:
        out["career_wins"] = career["career_wins"].to_numpy().astype("int64")
    if "career_win_pct_shrunk" in active:
        rate = shrink_rate_vec(career["career_wins"].to_numpy(), starts,
                               d["shrinkage_prior_win_rate"],
                               d["shrinkage_k_defaults"]["horse_career"])
        # No prior start at all -> no evidence about this horse.
        out["career_win_pct_shrunk"] = np.where(starts == 0, np.nan, rate)
    if "career_itm_pct_shrunk" in active:
        rate = shrink_rate_vec(career["career_itm"].to_numpy(), starts,
                               d["shrinkage_prior_itm_rate"],
                               d["shrinkage_k_defaults"]["horse_career"])
        out["career_itm_pct_shrunk"] = np.where(starts == 0, np.nan, rate)

    if {"last_3_avg_finish", "speed_trajectory_3_races"} & active:
        s = raw[["entry_id", "horse_id", "race_date_dt", "finish_pos",
                 "speed_figure_own"]].sort_values(
            ["horse_id", "race_date_dt", "entry_id"])
        if "last_3_avg_finish" in active:
            s["last_3_avg_finish"] = (
                s.groupby("horse_id")["finish_pos"].shift(1)
                 .rolling(3, min_periods=1).mean().to_numpy())
        if "speed_trajectory_3_races" in active:
            sf1 = s.groupby("horse_id")["speed_figure_own"].shift(1)
            sf3 = s.groupby("horse_id")["speed_figure_own"].shift(3)
            s["speed_trajectory_3_races"] = ((sf1 - sf3) / 2.0).to_numpy()
        cols = [c for c in ("last_3_avg_finish", "speed_trajectory_3_races")
                if c in active]
        out = out.merge(s[["entry_id"] + cols], on="entry_id", how="left")
    return out


# ---------------------------------------------------------------------------
# Bucket 4 — trainer / jockey
# ---------------------------------------------------------------------------

def _connection(raw: pd.DataFrame, cfg: dict, active: set[str],
                role: str) -> pd.DataFrame:
    entity = f"{role}_id"
    d = cfg["defaults"]
    prior = d["shrinkage_prior_win_rate"]
    ks = d["shrinkage_k_defaults"]
    out = pd.DataFrame({"entry_id": raw["entry_id"]})

    base = raw[["entry_id", entity, "race_date_dt", "is_win", "track_id",
                "surface", "dist_bucket"]].copy()
    base["one"] = 1.0

    for window in (30, 90, 365):
        f_rate = f"{role}_{window}d_winrate_shrunk"
        f_starts = f"{role}_starts_{window}d"
        if f_rate not in active and f_starts not in active:
            continue
        rolled = _aligned(raw, _prior_by_entity_windowed(
            base, entity_col=entity, value_cols=["is_win", "one"],
            window_days=window, prefix="w"))
        wins = rolled["w_is_win"].to_numpy()
        starts = rolled["w_one"].to_numpy()
        if f_rate in active:
            out[f_rate] = shrink_rate_vec(wins, starts, prior,
                                          ks[f"{role}_overall"])
        if f_starts in active:
            out[f_starts] = starts.astype("int64")

    for ctx_col, suffix, k_key in (("track_id", "at_track", f"{role}_at_track"),
                                   ("surface", "at_surface", f"{role}_at_surface"),
                                   ("dist_bucket", "at_distance",
                                    f"{role}_at_distance")):
        name = f"{role}_{suffix}_winrate_shrunk"
        if name not in active:
            continue
        rate, _ = grouped_prior_rate(base, [entity, ctx_col], prior, ks[k_key])
        out[name] = rate

    if f"days_since_{role}_last_win" in active:
        out = out.merge(
            _aligned(raw, _prior_days_to_event(
                base, entity_col=entity, event_mask_col="is_win",
                prefix=f"{role}_last_win")),
            on="entry_id", how="left")

    trend = f"{role}_recent_form_trend"
    if trend in active and {f"{role}_30d_winrate_shrunk",
                            f"{role}_90d_winrate_shrunk"} <= set(out.columns):
        out[trend] = (out[f"{role}_30d_winrate_shrunk"]
                      - out[f"{role}_90d_winrate_shrunk"])
    return out


def compute_connections(raw: pd.DataFrame, ctx: dict, cfg: dict,
                        active: set[str]) -> pd.DataFrame:
    t = _connection(raw, cfg, active, "trainer")
    j = _connection(raw, cfg, active, "jockey")
    out = t.merge(j, on="entry_id", how="left")

    d = cfg["defaults"]
    combo = {"trainer_jockey_combo_winrate_shrunk",
             "trainer_jockey_combo_starts", "is_first_time_combo"} & active
    if combo:
        base = raw[["entry_id", "trainer_id", "jockey_id", "race_date_dt",
                    "is_win"]].copy()
        rate, starts = grouped_prior_rate(
            base, ["trainer_id", "jockey_id"], d["shrinkage_prior_win_rate"],
            d["shrinkage_k_defaults"]["trainer_jockey_combo"])
        if "trainer_jockey_combo_winrate_shrunk" in active:
            out["trainer_jockey_combo_winrate_shrunk"] = rate
        if "trainer_jockey_combo_starts" in active:
            out["trainer_jockey_combo_starts"] = starts.astype("int64")
        if "is_first_time_combo" in active:
            out["is_first_time_combo"] = (starts == 0).astype("int8")
        if "trainer_jockey_bond_strength" in active:
            # Share of the trainer's recent starts that used this jockey.
            tr_starts = out.get("trainer_starts_30d")
            if tr_starts is not None:
                with np.errstate(invalid="ignore", divide="ignore"):
                    out["trainer_jockey_bond_strength"] = np.where(
                        starts > 0, starts / np.maximum(starts, 1), np.nan)
    return out


# ---------------------------------------------------------------------------
# Bucket 8 — horse at this track / surface / condition, and track bias
# ---------------------------------------------------------------------------

def compute_track_specific(raw: pd.DataFrame, ctx: dict, cfg: dict,
                           active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    d = cfg["defaults"]
    prior_win = d["shrinkage_prior_win_rate"]
    k_horse = d["shrinkage_k_defaults"]["horse_career"]

    if "track_distance_par_time_sec" in active:
        out["track_distance_par_time_sec"] = raw["par_time_sec_own"].to_numpy()

    if {"starts_at_track", "wins_at_track"} & active:
        counts = _per_track_prior_counts(raw, "horse_id", "horse")
        if "starts_at_track" in active:
            out["starts_at_track"] = _pick_by_track(
                counts, raw["track_id"], "horse_starts_t{t}").astype("int64")
        if "wins_at_track" in active:
            out["wins_at_track"] = _pick_by_track(
                counts, raw["track_id"], "horse_wins_t{t}").astype("int64")

    for ctx_col, name in (("surface", "historical_surface_winrate_shrunk"),
                          ("track_condition",
                           "historical_condition_winrate_shrunk")):
        if name not in active:
            continue
        base = raw[["entry_id", "horse_id", "race_date_dt", "is_win",
                    ctx_col]].copy()
        rate, starts = grouped_prior_rate(
            base, ["horse_id", ctx_col], prior_win, k_horse)
        # No prior start in this cell -> no evidence about THIS horse there.
        out[name] = np.where(starts == 0, np.nan, rate)

    # Both change-flags are NULL for a first-time starter. v1 emitted 0 there
    # ("no change"), which asserts something we do not know — a horse with no
    # prior start has no surface or condition to have changed from.
    for now_col, prev_col, name in (
        ("track_condition", "prev_track_condition",
         "condition_change_from_last_race"),
        ("surface", "prev_surface", "surface_change_from_last_race"),
    ):
        if name not in active:
            continue
        prev_val = ctx["prev"][prev_col]
        out[name] = ((raw[now_col] != prev_val).where(prev_val.notna())
                     .astype("boolean").astype("Int8").to_numpy())

    if {"track_dirt_bias_90d", "track_turf_bias_90d"} & active:
        out = out.merge(_track_speed_bias(raw, cfg), on="entry_id", how="left")
    return out


def _track_speed_bias(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """90-day trailing speed bias per (track, surface).

    One observation per race (the winner's figure, centred on the 80-point
    scale midpoint), averaged over the trailing window from races strictly
    before the race being scored. Positive = the surface has been playing
    fast lately.

    Unlike the v1 version this keys on (track, surface) rather than surface
    alone — with three tracks in one corpus a surface-only key mixes CT's
    bullring dirt into GP's main track.
    """
    window = cfg["defaults"]["bias_window_days"]
    win_rows = raw.loc[raw["finish_pos"] == 1,
                       ["race_id", "track_id", "surface", "race_date_dt",
                        "speed_figure_own"]].copy()
    win_rows["race_bias"] = win_rows["speed_figure_own"] - 80.0
    win_rows["one"] = win_rows["race_bias"].notna().astype(float)
    win_rows["race_bias"] = win_rows["race_bias"].fillna(0.0)
    win_rows["_key"] = list(zip(win_rows["track_id"], win_rows["surface"]))
    win_rows["_key"], _ = pd.factorize(win_rows["_key"], sort=False)
    win_rows["entry_id"] = win_rows["race_id"]  # helper keys on entry_id

    rolled = _prior_by_entity_windowed(
        win_rows, entity_col="_key", value_cols=["race_bias", "one"],
        window_days=window, prefix="b")
    rolled = win_rows[["entry_id", "surface"]].merge(
        rolled, on="entry_id", how="left")
    n = rolled["b_one"].to_numpy()
    rolled["bias_mean"] = np.where(n > 0, rolled["b_race_bias"].to_numpy()
                                   / np.where(n > 0, n, 1), np.nan)
    rolled = rolled.rename(columns={"entry_id": "race_id"})

    m = raw[["entry_id", "race_id", "surface"]].merge(
        rolled[["race_id", "bias_mean"]], on="race_id", how="left")
    m["track_dirt_bias_90d"] = np.where(m["surface"] == "Dirt",
                                        m["bias_mean"], np.nan)
    m["track_turf_bias_90d"] = np.where(m["surface"] == "Turf",
                                        m["bias_mean"], np.nan)
    return m[["entry_id", "track_dirt_bias_90d", "track_turf_bias_90d"]]


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    frames = [
        compute_recent_form(raw, ctx, cfg, active),
        compute_connections(raw, ctx, cfg, active),
        compute_track_specific(raw, ctx, cfg, active),
    ]
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="entry_id", how="left")
    return out
