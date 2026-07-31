"""Equipment and medication change flags (Doug's buckets 5 and 6).

Why these are derived rather than read off the chart
----------------------------------------------------
The schema has ``entries.first_time_blinkers`` and
``entries.first_time_bandages`` columns, but the parser never populates them:
both are 0 across all 207,976 rows. The Equibase charts in this corpus use
lowercase-only equipment codes, so the uppercase convention those columns
relied on never fires.

Rather than ship a rank-2 feature that is constant, the flags are derived by
comparing today's equipment string against the horse's previous start:

    Lb   -> Lasix + blinkers        b -> blinkers, no Lasix
    Lbf  -> Lasix + blinkers + front bandages
    L    -> Lasix only

"First time" therefore means *first time in this corpus*, which for a horse
with prior starts here is the real signal Doug is after; for a horse whose
debut predates the corpus it is NULL, not False.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _first_time(now_on: pd.Series, prev_on: pd.Series,
                has_prior: pd.Series) -> pd.Series:
    """On today, off last time, and there WAS a last time."""
    flag = now_on.astype("boolean") & (~prev_on.astype("boolean"))
    return flag.where(has_prior).astype("boolean").astype("Int8")


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    prev = ctx["prev"]

    has_prior = prev["prev_equipment"].notna()
    now_lasix = raw["has_lasix"].fillna(0).astype(bool)
    now_blink = raw["has_blinkers"].fillna(0).astype(bool)
    prev_lasix = prev["prev_has_lasix"].fillna(0).astype(bool)
    prev_blink = prev["prev_has_blinkers"].fillna(0).astype(bool)

    if "is_first_time_lasix" in active:
        out["is_first_time_lasix"] = _first_time(now_lasix, prev_lasix, has_prior)
    if "lasix_first_time" in active:
        # Doug's catalog lists this concept twice under two names; alias.
        out["lasix_first_time"] = _first_time(now_lasix, prev_lasix, has_prior)
    if "lasix_off" in active:
        off = (~now_lasix) & prev_lasix
        out["lasix_off"] = off.where(has_prior).astype("boolean").astype("Int8")
    if "is_first_time_blinkers" in active:
        out["is_first_time_blinkers"] = _first_time(now_blink, prev_blink,
                                                    has_prior)
    if "blinkers_change_flag" in active:
        chg = now_blink != prev_blink
        out["blinkers_change_flag"] = (
            chg.where(has_prior).astype("boolean").astype("Int8"))
    if "equipment_change_flag" in active:
        chg = raw["equipment"].fillna("") != prev["prev_equipment"].fillna("")
        out["equipment_change_flag"] = (
            chg.where(has_prior).astype("boolean").astype("Int8"))
    return out
