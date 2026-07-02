"""Feature engineering pipeline (v1 baseline).

Reads scripts/feature_config.json, pulls raw data from gp_full.db, computes
ONLY the features marked ``"active": true``, and writes one wide row per
entry into a new table ``entry_features_v1``.

Design principles
-----------------
* **NULL is honest.** We never fabricate a value. A rookie horse's
  `last_race_finish_pos` stays NULL. A trainer's prior-race window with
  zero starts leaves rate features at the shrinkage prior (which is the
  correct Bayesian answer for "no evidence"), but the accompanying
  `_starts` column reveals the sample size.
* **Prior-only computation.** Every "career" or "rolling" statistic is
  computed strictly from races BEFORE the target race — never look ahead.
* **Bayesian shrinkage for rates.** All shrunk-rate features go through
  the ``bayesian_shrinkage`` module with per-feature k values.
* **No cross-distance mixing.** For features that depend on distance, we
  never average across distance regimes (sprint vs route).

Usage
-----
    python feature_builder.py build --db scripts/gp_full.db \
                                    --config scripts/feature_config.json
    python feature_builder.py summarize --db scripts/gp_full.db
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bayesian_shrinkage import shrink_rate_vec  # noqa: E402


log = logging.getLogger("feature_builder")

FEATURES_TABLE = "entry_features_v1"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def active_features(cfg: dict) -> dict:
    return {k: v for k, v in cfg["features"].items() if v.get("active")}


# ---------------------------------------------------------------------------
# Raw data loading — one big flat table joined at the entry grain
# ---------------------------------------------------------------------------

def load_entries_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return a DataFrame at entry grain with all columns we might need."""
    log.info("Loading entries + races + horses + speed figures…")
    df = pd.read_sql_query(
        """
        SELECT
            e.id                        AS entry_id,
            e.race_id                   AS race_id,
            e.horse_id                  AS horse_id,
            e.trainer_id                AS trainer_id,
            e.jockey_id                 AS jockey_id,
            e.program_num               AS program_num,
            e.post_pos                  AS post_pos,
            e.start_pos                 AS start_pos,
            e.weight_lbs                AS weight_lbs,
            e.equipment                 AS equipment,
            e.has_lasix                 AS has_lasix,
            e.has_blinkers              AS has_blinkers,
            e.first_time_blinkers       AS first_time_blinkers,
            e.first_time_bandages       AS first_time_bandages,
            e.finish_pos                AS finish_pos,
            e.beaten_lengths            AS beaten_lengths,
            e.final_odds                AS final_odds,
            e.is_favorite               AS is_favorite,
            e.pace_calls_json           AS pace_calls_json,
            e.trip_comment              AS trip_comment,
            e.last_raced_raw            AS last_raced_raw,
            r.race_num                  AS race_num,
            r.race_type                 AS race_type,
            r.distance_yards            AS distance_yards,
            r.surface                   AS surface,
            r.track_condition           AS track_condition,
            r.purse                     AS purse,
            r.claiming_price            AS claiming_price,
            r.field_size                AS field_size,
            r.temporary_rail_feet       AS temporary_rail_feet,
            r.temperature_f             AS temperature_f,
            rd.race_date                AS race_date,
            rd.track_id                 AS track_id,
            h.sex                       AS horse_sex,
            h.color                     AS horse_color,
            h.country                   AS horse_country,
            h.foaled_date               AS foaled_date,
            h.foaled_place              AS foaled_place,
            h.sire_id                   AS sire_id,
            h.dam_id                    AS dam_id,
            csf.speed_figure            AS speed_figure_own,
            csf.par_time_sec            AS par_time_sec_own
        FROM entries e
        JOIN races r      ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        LEFT JOIN horses h  ON h.id = e.horse_id
        LEFT JOIN computed_speed_figures csf ON csf.entry_id = e.id
        """,
        conn,
    )
    df["race_date_dt"] = pd.to_datetime(df["race_date"])
    df["is_win"] = (df["finish_pos"] == 1).astype("float64")
    df["is_itm"] = (df["finish_pos"].fillna(999) <= 3).astype("float64")
    log.info("  %d entries loaded", len(df))
    return df


# ---------------------------------------------------------------------------
# Prior-lookup helpers (as-of-time queries)
# ---------------------------------------------------------------------------

def _prior_by_entity_expanding(
    df: pd.DataFrame,
    entity_col: str,
    value_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    """For each row, sum of `value_cols` over PRIOR rows of same entity.

    "Prior" means race_date strictly earlier — same-day races are also
    excluded (safer default for daily-card feature engineering).

    Returns a DataFrame with columns f"{prefix}_{col}" aligned by entry_id.
    """
    df_sorted = df[["entry_id", entity_col, "race_date_dt"] + value_cols].copy()
    df_sorted = df_sorted.sort_values([entity_col, "race_date_dt", "entry_id"])
    results: dict[str, np.ndarray] = {
        f"{prefix}_{col}": np.zeros(len(df_sorted), dtype=float) for col in value_cols
    }
    entity_vals = df_sorted[entity_col].to_numpy()
    dates = df_sorted["race_date_dt"].to_numpy()
    value_arrays = {col: df_sorted[col].to_numpy(dtype=float, na_value=0.0)
                    for col in value_cols}

    n = len(df_sorted)
    if n == 0:
        return pd.DataFrame({"entry_id": df_sorted["entry_id"]})

    # For each contiguous same-entity block, cumulative sum with same-day
    # exclusion.
    start = 0
    while start < n:
        end = start + 1
        while end < n and entity_vals[end] == entity_vals[start]:
            end += 1
        # slice [start:end) = same entity
        # For each i, sum of values[j] for j in [start, i) where dates[j] < dates[i]
        cum = {col: 0.0 for col in value_cols}
        j = start
        for i in range(start, end):
            # Advance j to include only rows strictly before dates[i]
            while j < i and dates[j] < dates[i]:
                for col in value_cols:
                    cum[col] += value_arrays[col][j]
                j += 1
            for col in value_cols:
                results[f"{prefix}_{col}"][i] = cum[col]
        start = end

    out = pd.DataFrame({"entry_id": df_sorted["entry_id"].values})
    for k, v in results.items():
        out[k] = v
    return out


def _prior_by_entity_windowed(
    df: pd.DataFrame,
    entity_col: str,
    value_cols: list[str],
    window_days: int,
    prefix: str,
) -> pd.DataFrame:
    """Like `_prior_by_entity_expanding` but limited to a rolling window."""
    df_sorted = df[["entry_id", entity_col, "race_date_dt"] + value_cols].copy()
    df_sorted = df_sorted.sort_values([entity_col, "race_date_dt", "entry_id"])
    results: dict[str, np.ndarray] = {
        f"{prefix}_{col}": np.zeros(len(df_sorted), dtype=float) for col in value_cols
    }
    entity_vals = df_sorted[entity_col].to_numpy()
    dates = df_sorted["race_date_dt"].to_numpy()
    value_arrays = {col: df_sorted[col].to_numpy(dtype=float, na_value=0.0)
                    for col in value_cols}
    window = np.timedelta64(window_days, "D")

    n = len(df_sorted)
    start = 0
    while start < n:
        end = start + 1
        while end < n and entity_vals[end] == entity_vals[start]:
            end += 1
        # For each i in [start, end):
        #   sum of values[j] for j in [win_start, i) where dates[j] >= dates[i] - window
        j_add = start   # advances forward as we include
        j_drop = start  # advances forward as we drop
        cum = {col: 0.0 for col in value_cols}
        for i in range(start, end):
            # First, include all j in [j_add, i) with dates[j] < dates[i]
            while j_add < i and dates[j_add] < dates[i]:
                for col in value_cols:
                    cum[col] += value_arrays[col][j_add]
                j_add += 1
            # Then, drop leading entries outside the window
            while j_drop < j_add and dates[j_drop] < dates[i] - window:
                for col in value_cols:
                    cum[col] -= value_arrays[col][j_drop]
                j_drop += 1
            for col in value_cols:
                results[f"{prefix}_{col}"][i] = cum[col]
        start = end

    out = pd.DataFrame({"entry_id": df_sorted["entry_id"].values})
    for k, v in results.items():
        out[k] = v
    return out


def _prior_last_value(
    df: pd.DataFrame,
    entity_col: str,
    value_cols: list[str],
    date_col: str,
    prefix: str,
) -> pd.DataFrame:
    """Return, for each row, the value_cols from the most recent PRIOR row
    of the same entity."""
    df_sorted = df[["entry_id", entity_col, "race_date_dt", date_col] + value_cols].copy()
    df_sorted = df_sorted.sort_values([entity_col, "race_date_dt", "entry_id"])
    results: dict[str, list] = {f"{prefix}_{col}": [None] * len(df_sorted) for col in value_cols}
    results[f"{prefix}_{date_col}"] = [None] * len(df_sorted)
    entity_vals = df_sorted[entity_col].to_numpy()
    dates = df_sorted["race_date_dt"].to_numpy()
    dates_iso = df_sorted[date_col].to_numpy()
    value_arrays = {col: df_sorted[col].to_numpy() for col in value_cols}

    n = len(df_sorted)
    start = 0
    while start < n:
        end = start + 1
        while end < n and entity_vals[end] == entity_vals[start]:
            end += 1
        last_idx = None
        last_date_val = None
        for i in range(start, end):
            if last_idx is not None and dates[last_idx] < dates[i]:
                for col in value_cols:
                    results[f"{prefix}_{col}"][i] = value_arrays[col][last_idx]
                results[f"{prefix}_{date_col}"][i] = last_date_val
            last_idx = i
            last_date_val = dates_iso[i]
        start = end

    out = pd.DataFrame({"entry_id": df_sorted["entry_id"].values})
    for k, v in results.items():
        out[k] = v
    return out


def _prior_days_to_event(
    df: pd.DataFrame,
    entity_col: str,
    event_mask_col: str,
    prefix: str,
) -> pd.DataFrame:
    """For each row, days since the same entity's most recent PRIOR row where
    ``event_mask_col`` was 1 (e.g., days_since_trainer_last_win)."""
    df_sorted = df[["entry_id", entity_col, "race_date_dt", event_mask_col]].copy()
    df_sorted = df_sorted.sort_values([entity_col, "race_date_dt", "entry_id"])
    result = np.full(len(df_sorted), np.nan)
    entity_vals = df_sorted[entity_col].to_numpy()
    dates = df_sorted["race_date_dt"].to_numpy()
    event_vals = df_sorted[event_mask_col].to_numpy()

    n = len(df_sorted)
    start = 0
    while start < n:
        end = start + 1
        while end < n and entity_vals[end] == entity_vals[start]:
            end += 1
        last_event_date: np.datetime64 | None = None
        for i in range(start, end):
            if last_event_date is not None and last_event_date < dates[i]:
                result[i] = (dates[i] - last_event_date) / np.timedelta64(1, "D")
            if event_vals[i] == 1:
                last_event_date = dates[i]
        start = end

    return pd.DataFrame({
        "entry_id": df_sorted["entry_id"].values,
        f"days_since_{prefix}": result,
    })


# ---------------------------------------------------------------------------
# Feature computation — one function per feature (or feature group)
# ---------------------------------------------------------------------------

def compute_bucket1_race_context(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})
    if "distance_yards" in active:
        out["distance_yards"] = df["distance_yards"]
    if "distance_furlongs" in active:
        out["distance_furlongs"] = df["distance_yards"] / 220.0
    if "surface" in active:
        out["surface"] = df["surface"]
    if "track_condition" in active:
        out["track_condition"] = df["track_condition"]
    if "is_sealed_track" in active:
        out["is_sealed_track"] = df["track_condition"].isin(
            {"Sloppy", "Muddy", "WetFast"}
        ).astype("int8")
    if "purse" in active:
        out["purse"] = df["purse"]
    if "log_purse" in active:
        out["log_purse"] = np.log1p(df["purse"].astype(float))
    if "race_type" in active:
        out["race_type"] = df["race_type"]
    if "claiming_price" in active:
        out["claiming_price"] = df["claiming_price"]
    if "field_size" in active:
        out["field_size"] = df["field_size"]
    if "month_of_year" in active:
        out["month_of_year"] = df["race_date_dt"].dt.month.astype("Int16")
    if "day_of_week" in active:
        out["day_of_week"] = df["race_date_dt"].dt.weekday.astype("Int16") + 1
    return out


def compute_bucket2_horse_immutable(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})
    if "horse_age" in active:
        foaled = pd.to_datetime(df["foaled_date"], errors="coerce")
        age_days = (df["race_date_dt"] - foaled).dt.days
        age_years = (age_days / 365.25).round(2)
        # A negative age means the parser mis-read the foaled year (rare —
        # ~0.001% of horses per Phase 3B). NULL out impossible values rather
        # than pass a nonsense feature to the model.
        age_years = age_years.where(age_years > 0)
        out["horse_age"] = age_years
    if "horse_sex" in active:
        out["horse_sex"] = df["horse_sex"]
    if "horse_country_origin" in active:
        out["horse_country_origin"] = df["horse_country"].fillna(
            df["foaled_place"].map(_country_map)
        )
    if "is_florida_bred" in active:
        out["is_florida_bred"] = (df["foaled_place"] == "Florida").astype("int8")
    return out


def _country_map(place: str | None) -> str | None:
    """Cheap heuristic mapping foaled_place → country code."""
    if not isinstance(place, str):
        return None
    place_lower = place.lower()
    US_STATES = {"kentucky", "florida", "new york", "california", "louisiana",
                 "maryland", "pennsylvania", "ohio", "texas", "virginia",
                 "washington", "oklahoma", "arkansas", "illinois", "indiana",
                 "michigan", "minnesota", "new mexico", "iowa", "arizona",
                 "colorado", "west virginia", "on", "wa", "ky", "fl"}
    if place_lower in US_STATES:
        return "USA"
    return place.strip().upper()[:3]


def compute_bucket3_recent_form(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})

    # Prior race lookup — most recent prior entry per horse
    prior = _prior_last_value(
        df,
        entity_col="horse_id",
        value_cols=["finish_pos", "beaten_lengths", "field_size", "speed_figure_own"],
        date_col="race_date",
        prefix="prev",
    )
    df_m = df[["entry_id", "race_date_dt"]].merge(prior, on="entry_id", how="left")
    df_m["prev_race_date_dt"] = pd.to_datetime(df_m["prev_race_date"], errors="coerce")

    if "last_race_finish_pos" in active:
        out["last_race_finish_pos"] = df_m["prev_finish_pos"]
    if "last_race_beaten_lengths" in active:
        out["last_race_beaten_lengths"] = df_m["prev_beaten_lengths"]
    if "last_race_field_size" in active:
        out["last_race_field_size"] = df_m["prev_field_size"]
    if "last_race_days_ago" in active or "days_since_last_race" in active:
        ldg = (df_m["race_date_dt"] - df_m["prev_race_date_dt"]).dt.days
        if "last_race_days_ago" in active:
            out["last_race_days_ago"] = ldg
        if "days_since_last_race" in active:
            out["days_since_last_race"] = ldg
    if "last_race_speed_figure" in active:
        out["last_race_speed_figure"] = df_m["prev_speed_figure_own"]

    # Career expanding counts (prior-only)
    career = _prior_by_entity_expanding(
        df,
        entity_col="horse_id",
        value_cols=["is_win", "is_itm"],
        prefix="horse",
    )
    # We also need starts count
    df_w = df[["entry_id", "horse_id", "race_date_dt"]].copy()
    df_w["one"] = 1.0
    career_starts = _prior_by_entity_expanding(
        df_w, entity_col="horse_id", value_cols=["one"], prefix="horse",
    )
    career = career.merge(career_starts, on="entry_id", how="left")
    career = career.rename(columns={"horse_one": "career_starts",
                                    "horse_is_win": "career_wins",
                                    "horse_is_itm": "career_itm"})
    if "career_starts" in active:
        out["career_starts"] = career["career_starts"].astype("Int32")
    if "career_wins" in active:
        out["career_wins"] = career["career_wins"].astype("Int32")

    priors = cfg["defaults"]
    prior_win = priors["shrinkage_prior_win_rate"]
    prior_itm = priors["shrinkage_prior_itm_rate"]
    k_horse = priors["shrinkage_k_defaults"]["horse_career"]

    if "career_win_pct_shrunk" in active:
        out["career_win_pct_shrunk"] = shrink_rate_vec(
            career["career_wins"].to_numpy(),
            career["career_starts"].to_numpy(),
            prior_win,
            k_horse,
        )
        # NULL when horse has ZERO prior starts — no evidence at all
        out.loc[career["career_starts"] == 0, "career_win_pct_shrunk"] = np.nan
    if "career_itm_pct_shrunk" in active:
        out["career_itm_pct_shrunk"] = shrink_rate_vec(
            career["career_itm"].to_numpy(),
            career["career_starts"].to_numpy(),
            prior_itm,
            k_horse,
        )
        out.loc[career["career_starts"] == 0, "career_itm_pct_shrunk"] = np.nan

    # Last 3 avg finish + speed trajectory require the last-3-window sums.
    # We approximate via 365-day window sums bounded by career_starts.
    # Simpler + more accurate: sort by horse+date, use rolling(3) window over
    # the sorted per-horse series.
    df_sorted = df[["entry_id", "horse_id", "race_date_dt", "finish_pos",
                    "speed_figure_own"]].sort_values(
        ["horse_id", "race_date_dt", "entry_id"]
    )
    if "last_3_avg_finish" in active:
        # For each entry: mean of finish_pos over the 3 PRIOR entries by the horse
        fin_prior = (df_sorted.groupby("horse_id")["finish_pos"]
                     .shift(1)  # exclude current
                     .rolling(3, min_periods=1).mean().reset_index(drop=True))
        df_sorted["last_3_avg_finish"] = fin_prior.values
        merged = df_sorted[["entry_id", "last_3_avg_finish"]]
        out = out.merge(merged, on="entry_id", how="left")
    if "speed_trajectory_3_races" in active:
        # Slope over last 3 speed figures. Positive = improving.
        # Simple: (SF[-1] - SF[-3]) / 2 over the *prior* 3 races.
        sf_shift1 = df_sorted.groupby("horse_id")["speed_figure_own"].shift(1)
        sf_shift3 = df_sorted.groupby("horse_id")["speed_figure_own"].shift(3)
        df_sorted["speed_trajectory_3_races"] = (sf_shift1 - sf_shift3) / 2.0
        merged = df_sorted[["entry_id", "speed_trajectory_3_races"]]
        out = out.merge(merged, on="entry_id", how="left")

    return out


def _connection_features(
    df: pd.DataFrame, entity_col: str, cfg: dict, key_prefix: str
) -> pd.DataFrame:
    """Compute the standard trainer/jockey feature set for one connection role.

    key_prefix is 'trainer' or 'jockey' and drives feature naming +
    shrinkage-k lookup.
    """
    priors = cfg["defaults"]
    prior_win = priors["shrinkage_prior_win_rate"]
    k_overall = priors["shrinkage_k_defaults"][f"{key_prefix}_overall"]
    k_track = priors["shrinkage_k_defaults"][f"{key_prefix}_at_track"]
    k_surface = priors["shrinkage_k_defaults"][f"{key_prefix}_at_surface"]
    k_distance = priors["shrinkage_k_defaults"][f"{key_prefix}_at_distance"]
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})

    df_w = df[["entry_id", entity_col, "race_date_dt", "is_win",
               "track_id", "surface", "distance_yards"]].copy()
    df_w["one"] = 1.0

    # ---- Rolling windowed win rates ----
    for window in (30, 90, 365):
        feat_wr = f"{key_prefix}_{window}d_winrate_shrunk"
        feat_starts = f"{key_prefix}_starts_{window}d"
        if feat_wr not in active and feat_starts not in active:
            continue
        rolled = _prior_by_entity_windowed(
            df_w, entity_col=entity_col,
            value_cols=["is_win", "one"], window_days=window,
            prefix=f"{key_prefix}_{window}d",
        )
        wins = rolled[f"{key_prefix}_{window}d_is_win"].to_numpy()
        starts = rolled[f"{key_prefix}_{window}d_one"].to_numpy()
        if feat_wr in active:
            rate = shrink_rate_vec(wins, starts, prior_win, k_overall)
            out[feat_wr] = rate
        if feat_starts in active:
            out[feat_starts] = starts.astype(int)

    # ---- All-time contextual rates: at_track, at_surface, at_distance ----
    # We treat "at_track" as (entity, track_id) all-time prior. Group by
    # (entity, track_id) sub-entity and compute expanding sums.
    def _grouped_rate(
        sub_cols: list[str],
        feat_wr: str,
        k: float,
    ) -> None:
        if feat_wr not in active:
            return
        df_local = df_w[["entry_id", entity_col, "race_date_dt", "is_win"] + sub_cols].copy()
        df_local["one"] = 1.0
        df_local["_key"] = list(zip(*(df_local[c] for c in [entity_col] + sub_cols)))
        # Turn tuples into codes for numpy speed
        df_local["_key"], _ = pd.factorize(df_local["_key"], sort=False)
        rolled = _prior_by_entity_expanding(
            df_local, entity_col="_key",
            value_cols=["is_win", "one"], prefix=f"tmp_{feat_wr}",
        )
        wins = rolled[f"tmp_{feat_wr}_is_win"].to_numpy()
        starts = rolled[f"tmp_{feat_wr}_one"].to_numpy()
        rate = shrink_rate_vec(wins, starts, prior_win, k)
        out[feat_wr] = rate

    _grouped_rate(["track_id"], f"{key_prefix}_at_track_winrate_shrunk", k_track)
    _grouped_rate(["surface"], f"{key_prefix}_at_surface_winrate_shrunk", k_surface)

    # Distance bucket: sprint (< 1540y) vs route (>= 1540y).
    df_w["dist_bucket"] = np.where(
        df_w["distance_yards"] < 1540, "sprint", "route"
    )
    _grouped_rate_df = df_w.copy()
    if f"{key_prefix}_at_distance_winrate_shrunk" in active:
        _grouped_rate(["dist_bucket"], f"{key_prefix}_at_distance_winrate_shrunk", k_distance)

    # ---- Days since last win ----
    if f"days_since_{key_prefix}_last_win" in active:
        dsw = _prior_days_to_event(
            df_w, entity_col=entity_col, event_mask_col="is_win",
            prefix=f"{key_prefix}_last_win",
        )
        out = out.merge(dsw, on="entry_id", how="left")

    # ---- Recent form trend: 30d rate minus 90d rate (already computed above) ----
    if f"{key_prefix}_recent_form_trend" in active:
        if (f"{key_prefix}_30d_winrate_shrunk" in out.columns
                and f"{key_prefix}_90d_winrate_shrunk" in out.columns):
            out[f"{key_prefix}_recent_form_trend"] = (
                out[f"{key_prefix}_30d_winrate_shrunk"]
                - out[f"{key_prefix}_90d_winrate_shrunk"]
            )

    return out


def compute_bucket4_connections(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    trainer_feats = _connection_features(df, "trainer_id", cfg, "trainer")
    jockey_feats = _connection_features(df, "jockey_id", cfg, "jockey")
    combo = pd.DataFrame({"entry_id": df["entry_id"]})

    # Trainer × jockey combo: prior wins/starts for this (trainer_id, jockey_id) pair
    if any(k in active for k in (
        "trainer_jockey_combo_winrate_shrunk",
        "trainer_jockey_combo_starts",
        "is_first_time_combo",
    )):
        df_c = df[["entry_id", "trainer_id", "jockey_id", "race_date_dt", "is_win"]].copy()
        df_c["one"] = 1.0
        df_c["_key"] = list(zip(df_c["trainer_id"], df_c["jockey_id"]))
        df_c["_key"], _ = pd.factorize(df_c["_key"], sort=False)
        rolled = _prior_by_entity_expanding(
            df_c, entity_col="_key",
            value_cols=["is_win", "one"], prefix="tj",
        )
        wins = rolled["tj_is_win"].to_numpy()
        starts = rolled["tj_one"].to_numpy()
        priors = cfg["defaults"]
        prior_win = priors["shrinkage_prior_win_rate"]
        k = priors["shrinkage_k_defaults"]["trainer_jockey_combo"]

        if "trainer_jockey_combo_winrate_shrunk" in active:
            combo["trainer_jockey_combo_winrate_shrunk"] = shrink_rate_vec(
                wins, starts, prior_win, k
            )
        if "trainer_jockey_combo_starts" in active:
            combo["trainer_jockey_combo_starts"] = starts.astype(int)
        if "is_first_time_combo" in active:
            combo["is_first_time_combo"] = (starts == 0).astype("int8")

    result = trainer_feats.merge(jockey_feats, on="entry_id", how="outer")
    result = result.merge(combo, on="entry_id", how="outer")
    return result


def compute_bucket6_race_dynamics(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})

    if "post_position" in active:
        out["post_position"] = df["post_pos"]
    if "post_rank_in_field" in active:
        out["post_rank_in_field"] = df["post_pos"] / df["field_size"].replace(0, np.nan)
    if "is_outside_post" in active:
        out["is_outside_post"] = (
            df["post_pos"] >= df["field_size"] - 1
        ).astype("int8")
    if "is_inside_post" in active:
        out["is_inside_post"] = (df["post_pos"] <= 2).astype("int8")
    if "weight_lbs" in active:
        out["weight_lbs"] = df["weight_lbs"]
    if "weight_vs_field_avg" in active:
        field_avg = df.groupby("race_id")["weight_lbs"].transform("mean")
        out["weight_vs_field_avg"] = df["weight_lbs"] - field_avg

    # Weight change vs distance change use the prior lookup
    prior = _prior_last_value(
        df, entity_col="horse_id",
        value_cols=["weight_lbs", "distance_yards", "surface", "track_condition",
                    "pace_calls_json", "start_pos"],
        date_col="race_date", prefix="prev",
    )
    df_m = df[["entry_id"]].merge(prior, on="entry_id", how="left")
    if "weight_change_from_last_race" in active:
        out["weight_change_from_last_race"] = (
            df["weight_lbs"] - df_m["prev_weight_lbs"]
        )
    if "distance_change_from_last_race" in active:
        out["distance_change_from_last_race"] = (
            df["distance_yards"] - df_m["prev_distance_yards"]
        )
    if "pace_type_last_race" in active:
        out["pace_type_last_race"] = df_m["prev_pace_calls_json"].map(_classify_pace_type)
    if "gate_break_avg_last_3" in active:
        # Mean of start_pos over prior ≤3 starts, using rolling shift
        df_sorted = df[["entry_id", "horse_id", "race_date_dt", "start_pos"]].sort_values(
            ["horse_id", "race_date_dt", "entry_id"]
        )
        prior_sp = df_sorted.groupby("horse_id")["start_pos"].shift(1).rolling(3, min_periods=1).mean()
        df_sorted["gate_break_avg_last_3"] = prior_sp.values
        out = out.merge(df_sorted[["entry_id", "gate_break_avg_last_3"]],
                        on="entry_id", how="left")
    if "surface_change_from_last_race" in active:
        out["surface_change_from_last_race"] = (
            (df["surface"] != df_m["prev_surface"]) & df_m["prev_surface"].notna()
        ).astype("int8")

    return out


def _classify_pace_type(pace_json: str | None) -> str | None:
    """Classify running style from the first-call position.

    Chart pace tokens are ``<position><margin>``. Examples:
        ``1Head``   → position 1, margin head
        ``64``      → position 6, margin 4 lengths
        ``211/2``   → position 2, margin 1 1/2 lengths
        ``10Head``  → position 10, margin head
        ``102``     → position 10, margin 2 lengths

    Parsing rule: if the token starts with a two-digit run 10-14 followed by
    a letter (Head/Neck/Nose) or fraction, the position is 2 digits;
    otherwise the position is the FIRST digit only and the remainder is the
    margin. This mirrors the parser's disambiguation.

    Buckets:
        front  (1-2)  stalk (3-4)  mid (5-6)  close (7+)
    """
    if not isinstance(pace_json, str) or not pace_json:
        return None
    try:
        d = json.loads(pace_json)
    except json.JSONDecodeError:
        return None
    for label, tok in d.items():
        if label in ("Start", "Str", "Fin", "_extra_1") or not isinstance(tok, str):
            continue
        if len(tok) == 0:
            continue
        # Two-digit position (10-14) — recognized only when followed by a
        # letter or fraction. `12` alone = pos 1 by 2 lengths.
        if len(tok) >= 3 and tok[:2] in {"10", "11", "12", "13", "14"} \
                and (tok[2].isalpha() or "/" in tok[2:]):
            pos = int(tok[:2])
        elif tok[0].isdigit():
            pos = int(tok[0])
        else:
            continue
        if pos <= 2:
            return "front"
        if pos <= 4:
            return "stalk"
        if pos <= 6:
            return "mid"
        return "close"
    return None


def compute_bucket7_market(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})

    if "final_odds" in active:
        out["final_odds"] = df["final_odds"]
    if "log_final_odds" in active:
        out["log_final_odds"] = np.log1p(df["final_odds"].astype(float))
    if "implied_probability" in active:
        out["implied_probability"] = 1.0 / (df["final_odds"].astype(float) + 1.0)
    if "is_favorite" in active:
        out["is_favorite"] = df["is_favorite"].astype("Int8")
    if "odds_rank_in_field" in active:
        out["odds_rank_in_field"] = df.groupby("race_id")["final_odds"].rank(method="min")
    if "odds_ratio_to_favorite" in active:
        min_odds = df.groupby("race_id")["final_odds"].transform("min")
        out["odds_ratio_to_favorite"] = df["final_odds"] / min_odds.replace(0, np.nan)
    return out


def compute_bucket8_track_specific(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    active = active_features(cfg)
    out = pd.DataFrame({"entry_id": df["entry_id"]})

    if "track_distance_par_time_sec" in active:
        out["track_distance_par_time_sec"] = df["par_time_sec_own"]

    # Prior at-track starts and wins for the horse
    if "starts_at_track" in active or "wins_at_track" in active:
        df_w = df[["entry_id", "horse_id", "race_date_dt", "is_win", "track_id"]].copy()
        df_w["one"] = 1.0
        df_w["_key"] = list(zip(df_w["horse_id"], df_w["track_id"]))
        df_w["_key"], _ = pd.factorize(df_w["_key"], sort=False)
        rolled = _prior_by_entity_expanding(
            df_w, entity_col="_key",
            value_cols=["is_win", "one"], prefix="hi_track",
        )
        if "starts_at_track" in active:
            out["starts_at_track"] = rolled["hi_track_one"].astype(int)
        if "wins_at_track" in active:
            out["wins_at_track"] = rolled["hi_track_is_win"].astype(int)

    # Horse × surface / condition shrunk winrates
    priors = cfg["defaults"]
    prior_win = priors["shrinkage_prior_win_rate"]
    k_horse = priors["shrinkage_k_defaults"]["horse_career"]

    def _horse_context_rate(sub_col: str, feat: str) -> None:
        if feat not in active:
            return
        df_w = df[["entry_id", "horse_id", "race_date_dt", "is_win", sub_col]].copy()
        df_w["one"] = 1.0
        df_w["_key"] = list(zip(df_w["horse_id"], df_w[sub_col]))
        df_w["_key"], _ = pd.factorize(df_w["_key"], sort=False)
        rolled = _prior_by_entity_expanding(
            df_w, entity_col="_key",
            value_cols=["is_win", "one"], prefix=f"tmp_{feat}",
        )
        wins = rolled[f"tmp_{feat}_is_win"].to_numpy()
        starts = rolled[f"tmp_{feat}_one"].to_numpy()
        rate = shrink_rate_vec(wins, starts, prior_win, k_horse)
        # NULL when horse has no prior in this cell — no evidence
        rate = np.where(starts == 0, np.nan, rate)
        out[feat] = rate

    _horse_context_rate("surface", "historical_surface_winrate_shrunk")
    _horse_context_rate("track_condition", "historical_condition_winrate_shrunk")

    # Condition change from last race
    if "condition_change_from_last_race" in active:
        prior = _prior_last_value(
            df, entity_col="horse_id",
            value_cols=["track_condition"], date_col="race_date", prefix="prev",
        )
        df_m = df[["entry_id", "track_condition"]].merge(prior, on="entry_id", how="left")
        out["condition_change_from_last_race"] = (
            (df_m["track_condition"] != df_m["prev_track_condition"])
            & df_m["prev_track_condition"].notna()
        ).astype("int8")

    # Track speed bias (recent 90d) — computed at the race grain then joined
    if "track_dirt_bias_90d" in active or "track_turf_bias_90d" in active:
        bias = _compute_track_bias(df)
        out = out.merge(bias, on="entry_id", how="left")

    return out


def _compute_track_bias(df: pd.DataFrame) -> pd.DataFrame:
    """90-day rolling mean of (par_time_sec - horse_time_sec) per (track, surface).

    Positive bias = recent races have been running faster than par (fast surface).
    We compute one bias per (track, surface) rolling 90 days back from the race
    date, then merge back to entries.

    Only the winner's row per race is used (finish_pos = 1) to isolate a
    single "race speed" observation per race.
    """
    # Winner's row per race with useful cols
    win_rows = df[df["finish_pos"] == 1][
        ["race_id", "track_id", "surface", "race_date_dt", "par_time_sec_own",
         "speed_figure_own"]
    ].copy()
    # bias = par - horse_time = raw_diff sign; but we already stored raw_diff
    # indirectly. Use speed_figure_own centered at 80 as a proxy for bias.
    win_rows["race_bias"] = (win_rows["speed_figure_own"] - 80.0)
    win_rows["one"] = 1.0
    win_rows["_key"] = list(zip(win_rows["track_id"], win_rows["surface"]))
    win_rows["_key"], _ = pd.factorize(win_rows["_key"], sort=False)
    win_rows["entry_id"] = win_rows["race_id"]  # placeholder for helper
    rolled = _prior_by_entity_windowed(
        win_rows.rename(columns={"race_date_dt": "race_date_dt"}),
        entity_col="_key",
        value_cols=["race_bias", "one"],
        window_days=90,
        prefix="bias90",
    )
    # rolled has entry_id = race_id; compute mean = sum/count
    rolled["bias_mean"] = np.where(
        rolled["bias90_one"] > 0,
        rolled["bias90_race_bias"] / rolled["bias90_one"],
        np.nan,
    )
    rolled = rolled.rename(columns={"entry_id": "race_id"})[["race_id", "bias_mean"]]
    # Merge back to per-entry frame
    winners_by_race = win_rows[["race_id", "surface"]].merge(rolled, on="race_id")

    # Now attach to every entry by race_id and surface split
    ent_merge = df[["entry_id", "race_id", "surface"]].merge(
        winners_by_race, on=["race_id", "surface"], how="left"
    )
    ent_merge["track_dirt_bias_90d"] = np.where(
        ent_merge["surface"] == "Dirt", ent_merge["bias_mean"], np.nan
    )
    ent_merge["track_turf_bias_90d"] = np.where(
        ent_merge["surface"] == "Turf", ent_merge["bias_mean"], np.nan
    )
    return ent_merge[["entry_id", "track_dirt_bias_90d", "track_turf_bias_90d"]]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

BUCKET_FUNCS: dict[int, Callable[[pd.DataFrame, dict], pd.DataFrame]] = {
    1: compute_bucket1_race_context,
    2: compute_bucket2_horse_immutable,
    3: compute_bucket3_recent_form,
    4: compute_bucket4_connections,
    6: compute_bucket6_race_dynamics,
    7: compute_bucket7_market,
    8: compute_bucket8_track_specific,
    # Bucket 5 (pedigree) deferred to Phase 3F
}


def build_features(conn: sqlite3.Connection, cfg: dict) -> pd.DataFrame:
    raw = load_entries_frame(conn)
    active = active_features(cfg)
    buckets_used = sorted({int(f["bucket"]) for f in active.values()})
    log.info("Active features: %d across buckets %s",
             len(active), buckets_used)

    frames = [raw[["entry_id", "race_id", "horse_id",
                   "trainer_id", "jockey_id"]]]
    for b in buckets_used:
        fn = BUCKET_FUNCS.get(b)
        if fn is None:
            log.warning("no builder for bucket %d", b)
            continue
        t0 = time.perf_counter()
        log.info("Bucket %d…", b)
        result = fn(raw, cfg)
        log.info("  %d columns, %d rows in %.1fs",
                 len(result.columns) - 1, len(result),
                 time.perf_counter() - t0)
        frames.append(result)

    log.info("Merging bucket frames…")
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="entry_id", how="left")

    log.info("Final feature frame: %d rows × %d columns", len(out), len(out.columns))
    return out


def write_features_table(
    conn: sqlite3.Connection, df: pd.DataFrame, table_name: str = FEATURES_TABLE
) -> int:
    log.info("Writing %s (drop-and-replace)…", table_name)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_race "
        f"ON {table_name}(race_id)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_horse "
        f"ON {table_name}(horse_id)"
    )
    conn.commit()
    return len(df)


def cmd_build(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    cfg = load_config(Path(args.config))
    conn = sqlite3.connect(db_path)
    df = build_features(conn, cfg)
    write_features_table(conn, df, table_name=args.table)
    log.info("done — wrote %d rows to table %s", len(df), args.table)
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {args.table}", conn)
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print()
    print("Non-null coverage per column:")
    coverage = df.notna().mean().sort_values()
    for col, pct in coverage.items():
        print(f"  {col:<45} {pct*100:6.2f}%")
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("build")
    p_b.add_argument("--db", default="scripts/gp_full.db")
    p_b.add_argument("--config", default="scripts/feature_config.json")
    p_b.add_argument("--table", default=FEATURES_TABLE)
    p_b.set_defaults(func=cmd_build)
    p_s = sub.add_parser("summarize")
    p_s.add_argument("--db", default="scripts/gp_full.db")
    p_s.add_argument("--table", default=FEATURES_TABLE)
    p_s.set_defaults(func=cmd_summarize)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
