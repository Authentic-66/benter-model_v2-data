"""Class-movement features.

Doug on ``class_change_from_last`` (rank **1**, his only rank-1 candidate):
*"A significant change in class, up or down, is a big factor imo"*.
On ``purse_change_from_last`` (rank 2): *"This is part of a move up or down
in class I believe?"* — correct, and the two are computed from the same
prior-race lookup here.
On ``last_race_was_maiden`` (rank 2): *"If the last race was a maiden, the
horse won and are now going against other horses who have won previously and
have additional races under their belt that is usually a tougher race for
the horse that just had its first win last out"* — note this is specifically
about a horse that **won** its maiden, so the flag is paired with
``last_race_won`` rather than standing alone.

Substrate
---------
``races.class_level`` is NULL for all 28,105 races in the corpus, so class is
derived: see ``dpv1_common.class_score_vec``. Claiming races are positioned
by claiming tag (track-independent); everything else by purse.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import (  # noqa: E402
    class_score_vec, normalize_race_type, grouped_prior_rate,
)

MAIDEN_TYPES = {"MAIDENCLAIMING", "MAIDENSPECIALWEIGHT", "MAIDENOPTIONALCLAIMING"}


def add_class_score(raw: pd.DataFrame) -> pd.Series:
    """Row-local class ladder score for every entry's race."""
    return class_score_vec(raw["race_type"], raw["claiming_price"], raw["purse"])


def is_maiden_race(race_type: pd.Series) -> pd.Series:
    key = race_type.map(normalize_race_type)
    return key.isin(MAIDEN_TYPES).where(key.notna())


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict, active: set[str]) -> pd.DataFrame:
    """Class-movement features at entry grain.

    ``ctx`` supplies ``prev`` — the most recent prior start per horse, from
    ``_prior_last_value`` — so nothing here looks ahead.
    """
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    prev = ctx["prev"]
    thresh = cfg["defaults"]["class_ladder"]["class_change_threshold"]

    now_score = raw["class_score"]
    prev_score = prev["prev_class_score"]
    delta = now_score - prev_score

    if "class_score" in active:
        out["class_score"] = now_score
    if "class_score_change_from_last" in active:
        out["class_score_change_from_last"] = delta
    if "class_change_from_last" in active:
        # Deadband keeps trivial purse jitter from reading as a class move.
        cat = np.where(
            delta.isna(), None,
            np.where(delta >= thresh, "UP",
                     np.where(delta <= -thresh, "DOWN", "SAME")),
        )
        out["class_change_from_last"] = pd.Series(cat, index=raw.index,
                                                  dtype="object")
    if "purse_change_from_last" in active:
        prev_purse = prev["prev_purse"].astype("float64")
        pct = (raw["purse"].astype("float64") - prev_purse) / prev_purse
        out["purse_change_from_last"] = pct.replace([np.inf, -np.inf], np.nan)
    if "last_race_was_maiden" in active:
        out["last_race_was_maiden"] = (
            prev["prev_is_maiden"].astype("boolean").astype("Int8")
        )
    return out


def compute_trainer_class_rates(
    raw: pd.DataFrame, ctx: dict, cfg: dict, active: set[str]
) -> pd.DataFrame:
    """Trainer win rates conditioned on the class move they are making.

    Doug ranked ``trainer_dropping_class_win_pct`` and
    ``trainer_rising_class_win_pct`` at 2. Both are prior-only rates over the
    subset of that trainer's starts that were themselves a drop / a rise, so
    a barn with a known "drop 'em and win" pattern shows up.
    """
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    d = cfg["defaults"]
    prior_win = d["shrinkage_prior_win_rate"]
    k = d["shrinkage_k_defaults"]["trainer_context"]
    thresh = d["class_ladder"]["class_change_threshold"]
    layoff = d["layoff_days"]

    delta = raw["class_score"] - ctx["prev"]["prev_class_score"]
    days_off = ctx["prev"]["prev_days_ago"]
    first_start = ctx["career"]["career_starts"] == 0

    # Each is a (trainer, condition-met) cell. Rows where the condition is not
    # met sit in the "False" cell and are simply never read for that feature —
    # the value returned for them is that other cell's rate, so we mask.
    specs = [
        ("trainer_dropping_class_win_pct", delta <= -thresh),
        ("trainer_rising_class_win_pct", delta >= thresh),
        ("trainer_off_layoff_win_pct", days_off >= layoff),
        ("trainer_first_time_starters_win_pct", first_start),
    ]
    for name, cond in specs:
        if name not in active:
            continue
        local = raw[["entry_id", "race_date_dt", "is_win", "trainer_id"]].copy()
        local["_cond"] = cond.fillna(False).astype(int)
        rate, starts = grouped_prior_rate(
            local, ["trainer_id", "_cond"], prior_win, k, value_col="is_win",
        )
        # Only meaningful where the horse is actually in that situation today.
        out[name] = np.where(cond.fillna(False).to_numpy(), rate, np.nan)
    return out
