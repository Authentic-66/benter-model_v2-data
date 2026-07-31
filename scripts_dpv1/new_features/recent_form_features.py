"""Recent-form features new in DPv1 (Doug's bucket 3).

Doug's notes carried by these features:

``last_race_won`` (rank **1**)
    *"In thouroughbred racing, winning multiple races in a row is difficult,
    unless the horse really is that good, and especially if/as it moves up in
    class"* — so it is built to be read alongside ``class_change_from_last``.

``distance_specialist_flag`` (rank 2)
    *"If a majority of the horse's success or ITM standings come at the
    distance of their current race, it matters"* — note **majority of ITM
    finishes**, not simply "has two wins here" as the catalog description
    says. Doug's reading is implemented: the flag fires when a majority of
    the horse's prior in-the-money finishes came at today's distance bucket,
    and a raw share is exposed alongside it.

``second_race_back_pattern`` (rank 2)
    *"Past results at the distance, on the surface, at the track and any
    workouts leading up to the race are a factor"* — the workout half is not
    available in this corpus (see ``recent_bullet_workout``, blocked); the
    rest is covered by the specialist flags computed here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import _prior_by_entity_expanding  # noqa: E402


def _specialist(raw: pd.DataFrame, cell_col: str, name: str,
                out: pd.DataFrame, active: set[str]) -> None:
    """Share of the horse's prior ITM finishes earned in today's cell.

    Fires when that share exceeds half AND the horse has at least two prior
    ITM finishes to share out — one ITM finish would make every horse a
    100% "specialist" at whatever it happened to hit the board at.
    """
    share_name = f"{name}_itm_share"
    if name not in active and share_name not in active:
        return

    local = raw[["entry_id", "horse_id", "race_date_dt"]].copy()
    local["_cell"] = raw[cell_col].astype(object)
    local["itm"] = raw["is_itm"].astype(float)
    local["one"] = 1.0

    # Prior ITM finishes overall...
    all_r = _prior_by_entity_expanding(
        local, entity_col="horse_id", value_cols=["itm"], prefix="a",
    )
    # ...and prior ITM finishes in this specific cell.
    local["_key"] = list(zip(local["horse_id"], local["_cell"]))
    local["_key"], _ = pd.factorize(local["_key"], sort=False)
    cell_r = _prior_by_entity_expanding(
        local, entity_col="_key", value_cols=["itm"], prefix="c",
    )
    m = (raw[["entry_id"]]
         .merge(all_r, on="entry_id", how="left")
         .merge(cell_r, on="entry_id", how="left"))
    total_itm = m["a_itm"].to_numpy()
    cell_itm = m["c_itm"].to_numpy()

    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total_itm > 0, cell_itm / total_itm, np.nan)
    # No prior ITM finish at all -> no opinion, not "not a specialist".
    share = np.where(raw[cell_col].isna().to_numpy(), np.nan, share)

    if share_name in active:
        out[share_name] = share
    if name in active:
        flag = (total_itm >= 2) & (share > 0.5)
        out[name] = pd.Series(
            np.where(np.isnan(share), None, flag), index=raw.index
        ).astype("boolean").astype("Int8")


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    prev = ctx["prev"]
    career = ctx["career"]
    layoff = cfg["defaults"]["layoff_days"]

    if "last_race_won" in active:
        out["last_race_won"] = (
            (prev["prev_finish_pos"] == 1).where(prev["prev_finish_pos"].notna())
            .astype("boolean").astype("Int8")
        )
    if "last_race_troubled_trip" in active:
        out["last_race_troubled_trip"] = (
            prev["prev_troubled"].astype("boolean").astype("Int8")
        )
    if "last_race_beaten_favorite" in active:
        # Beat the favourite = finished ahead of whoever went off favourite.
        out["last_race_beaten_favorite"] = (
            prev["prev_beat_favorite"].astype("boolean").astype("Int8")
        )
    if "second_race_back_pattern" in active:
        # This is start #2 after a layoff: the horse's PREVIOUS start was
        # itself the layoff-return. "Bounce" candidates.
        prev_gap = prev["prev_prev_days_ago"]
        out["second_race_back_pattern"] = (
            (prev_gap >= layoff).where(prev_gap.notna())
            .astype("boolean").astype("Int8")
        )
    if "career_avg_speed_figure" in active:
        local = raw[["entry_id", "horse_id", "race_date_dt"]].copy()
        sf = raw["speed_figure_own"].astype("float64")
        local["sf"] = sf.fillna(0.0)
        local["has_sf"] = sf.notna().astype(float)
        rolled = _prior_by_entity_expanding(
            local, entity_col="horse_id", value_cols=["sf", "has_sf"],
            prefix="sf",
        )
        rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")
        n = rolled["sf_has_sf"].to_numpy()
        out["career_avg_speed_figure"] = np.where(
            n > 0, rolled["sf_sf"].to_numpy() / np.where(n > 0, n, 1), np.nan)

    _specialist(raw, "dist_bucket", "distance_specialist_flag", out, active)
    _specialist(raw, "surface", "surface_specialist_flag", out, active)
    _specialist(raw, "track_code", "track_specialist_flag", out, active)

    if "start_pos_last_race" in active:
        out["start_pos_last_race"] = prev["prev_start_pos"]
    return out
