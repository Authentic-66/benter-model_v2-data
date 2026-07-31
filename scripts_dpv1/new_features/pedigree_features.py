"""Sire / broodmare-sire progeny rates, computed from our own corpus.

Phase 3C deferred bucket 5 entirely. Doug ranked twelve pedigree features at
2, of which four are v10-workbook signals held for Phase 4D; the rest are
progeny win rates that the 3-track corpus can produce directly.

Coverage ceiling
----------------
``horses.sire_id`` is populated for 13,636 of 32,822 horses — but those are
the horses that run most often, so entry-level coverage is 146,205 / 207,976
(70.3%). Every feature here is therefore NULL for roughly three entries in
ten, honestly, rather than imputed.

Cross-track priors
------------------
Progeny rates pool across GP, CT and MNR by design. A sire's aptitude for
dirt is a property of the sire, not of the track, and pooling is what makes
the estimates usable at all — a sire with 40 starters spread over three
tracks is a usable sample where 13 at one track is not. This is the clearest
case in DPv1 where the cross-track corpus buys statistical power directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import grouped_prior_rate  # noqa: E402

WET_CONDITIONS = {"Sloppy", "Muddy", "Yielding", "Heavy", "Good", "WetFast"}


def _rate(raw: pd.DataFrame, out: pd.DataFrame, name: str, active: set[str],
          parent_col: str, mask: pd.Series | None, prior: float, k: float,
          today_mask: pd.Series | None = None) -> None:
    """Prior-only shrunk progeny win rate over a subset of starts.

    ``mask`` restricts which HISTORICAL starts feed the rate (e.g. dirt only).
    ``today_mask``, when given, restricts which rows the value is reported
    for — used where the feature is only meaningful in context.
    """
    if name not in active:
        return
    local = raw[["entry_id", "race_date_dt", parent_col]].copy()
    local["is_win"] = raw["is_win"].astype(float)
    if mask is not None:
        # Starts outside the subset land in their own cell and are never read.
        local["_sub"] = mask.fillna(False).astype(int)
        keys = [parent_col, "_sub"]
    else:
        keys = [parent_col]
    rate, starts = grouped_prior_rate(local, keys, prior, k, value_col="is_win")

    valid = raw[parent_col].notna().to_numpy().copy()
    if mask is not None:
        valid &= mask.fillna(False).to_numpy()
    if today_mask is not None:
        valid &= today_mask.fillna(False).to_numpy()
    valid &= starts > 0
    out[name] = np.where(valid, rate, np.nan)


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    d = cfg["defaults"]
    prior = d["shrinkage_prior_win_rate"]
    k_sire = d["shrinkage_k_defaults"]["sire_progeny"]
    k_dam = d["shrinkage_k_defaults"]["damsire_progeny"]

    if "sire_id" in active:
        out["sire_id"] = raw["sire_id"]

    is_dirt = raw["surface"] == "Dirt"
    is_turf = raw["surface"] == "Turf"
    is_sprint = raw["dist_bucket"] == "sprint"
    is_route = raw["dist_bucket"] == "route"
    is_wet = raw["track_condition"].isin(WET_CONDITIONS)
    is_fts = ctx["career"]["career_starts"] == 0

    # (feature, parent column, historical subset, report-only-when, k)
    specs = [
        ("sire_overall_win_pct", "sire_id", None, None, k_sire),
        ("sire_dirt_win_pct", "sire_id", is_dirt, is_dirt, k_sire),
        ("sire_turf_win_pct", "sire_id", is_turf, is_turf, k_sire),
        ("sire_sprint_win_pct", "sire_id", is_sprint, is_sprint, k_sire),
        ("sire_route_win_pct", "sire_id", is_route, is_route, k_sire),
        ("sire_off_track_win_pct", "sire_id", is_wet, is_wet, k_sire),
        ("sire_first_time_starter_win_pct", "sire_id", is_fts, is_fts, k_sire),
        ("sire_at_surface_winrate_shrunk", "sire_id", None, None, k_sire),
        ("sire_at_distance_winrate_shrunk", "sire_id", None, None, k_sire),
        ("broodmare_sire_dirt_win_pct", "damsire_id", is_dirt, is_dirt, k_dam),
        ("broodmare_sire_turf_win_pct", "damsire_id", is_turf, is_turf, k_dam),
        ("damsire_at_surface_winrate", "damsire_id", None, None, k_dam),
    ]
    for name, parent, mask, today, k in specs:
        # The two "_at_surface"/"_at_distance" forms key on the context column
        # itself rather than a boolean subset, so they carry a value on every
        # surface/distance rather than only one.
        if name in ("sire_at_surface_winrate_shrunk",
                    "damsire_at_surface_winrate"):
            _keyed_rate(raw, out, name, active, parent, "surface", prior, k)
        elif name == "sire_at_distance_winrate_shrunk":
            _keyed_rate(raw, out, name, active, parent, "dist_bucket", prior, k)
        else:
            _rate(raw, out, name, active, parent, mask, prior, k, today)
    return out


def _keyed_rate(raw: pd.DataFrame, out: pd.DataFrame, name: str,
                active: set[str], parent_col: str, context_col: str,
                prior: float, k: float) -> None:
    """Progeny rate keyed on (parent, context value) — one value per context."""
    if name not in active:
        return
    local = raw[["entry_id", "race_date_dt", parent_col, context_col]].copy()
    local["is_win"] = raw["is_win"].astype(float)
    rate, starts = grouped_prior_rate(
        local, [parent_col, context_col], prior, k, value_col="is_win")
    valid = (raw[parent_col].notna() & raw[context_col].notna()).to_numpy().copy()
    valid &= starts > 0
    out[name] = np.where(valid, rate, np.nan)
