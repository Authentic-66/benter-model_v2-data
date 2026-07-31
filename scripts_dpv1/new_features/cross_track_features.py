"""Cross-track features — the Phase 4B payoff of the 3-track corpus.

None of these are computable from a single-track database. They are not part
of Doug's 154-feature catalog; Phase 4B adds them and flags them with
``"dpv1_addition": true`` in the config.

What they separate
------------------
* ``*_at_other_tracks_winrate`` — a barn that wins everywhere from a barn
  that only wins at home. With one track in the DB these are the same number.
* ``horse_shipping_success_rate`` — 3,467 horses in the corpus have raced at
  more than one of GP/CT/MNR (3,219 at two, 248 at all three). Some ship well
  and some leave their race in the van.
* ``*_home_track`` — where a connection actually operates, derived rather
  than assumed, so a GP-based trainer taking one over to Mountaineer is
  visibly off his home circuit.

Leakage discipline
------------------
Every count here is **prior-only** — strictly earlier race dates, same-day
races excluded. "Home track" is therefore the home track *as of that race*,
not as of today; a trainer who relocates mid-corpus shows the move.

Implementation note
-------------------
Per-track prior counts are obtained in a single expanding pass over
per-track indicator columns, which also yields the at-this-track counts for
free. "Other tracks" is then ``all_tracks - this_track``, which is exact
rather than an approximation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dpv1_common import (  # noqa: E402
    TRACK_CODES, shrink_rate_vec, _prior_by_entity_expanding,
)

TRACK_IDS = sorted(TRACK_CODES)


def _per_track_prior_counts(raw: pd.DataFrame, entity_col: str,
                            prefix: str) -> pd.DataFrame:
    """Prior starts and wins per track for one connection role.

    Returns a frame aligned to ``raw`` with, for each track id t:
        ``{prefix}_starts_t{t}``, ``{prefix}_wins_t{t}``
    plus overall ``{prefix}_starts_all`` / ``{prefix}_wins_all``.
    """
    local = raw[["entry_id", entity_col, "race_date_dt", "is_win",
                 "track_id"]].copy()
    local["one"] = 1.0
    value_cols = ["one", "is_win"]
    for t in TRACK_IDS:
        at_t = (local["track_id"] == t).astype(float)
        local[f"s_t{t}"] = at_t
        local[f"w_t{t}"] = at_t * local["is_win"].astype(float)
        value_cols += [f"s_t{t}", f"w_t{t}"]

    rolled = _prior_by_entity_expanding(
        local, entity_col=entity_col, value_cols=value_cols, prefix="x",
    )
    rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")

    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    out[f"{prefix}_starts_all"] = rolled["x_one"].to_numpy()
    out[f"{prefix}_wins_all"] = rolled["x_is_win"].to_numpy()
    for t in TRACK_IDS:
        out[f"{prefix}_starts_t{t}"] = rolled[f"x_s_t{t}"].to_numpy()
        out[f"{prefix}_wins_t{t}"] = rolled[f"x_w_t{t}"].to_numpy()
    return out


def _pick_by_track(counts: pd.DataFrame, track_id: pd.Series,
                   pattern: str) -> np.ndarray:
    """Select ``pattern.format(t)`` column per row according to track_id."""
    result = np.full(len(counts), np.nan)
    tid = track_id.to_numpy()
    for t in TRACK_IDS:
        mask = tid == t
        result[mask] = counts.loc[mask, pattern.format(t=t)].to_numpy()
    return result


def _home_track(counts: pd.DataFrame, prefix: str) -> pd.Series:
    """Track code with the most prior starts. NULL before any prior start."""
    cols = [f"{prefix}_starts_t{t}" for t in TRACK_IDS]
    mat = counts[cols].to_numpy()
    total = mat.sum(axis=1)
    idx = mat.argmax(axis=1)
    codes = np.array([TRACK_CODES[t] for t in TRACK_IDS], dtype=object)
    home = codes[idx]
    return pd.Series(np.where(total > 0, home, None), index=counts.index,
                     dtype="object")


def compute_connection_cross_track(
    raw: pd.DataFrame, cfg: dict, active: set[str], role: str
) -> pd.DataFrame:
    """``role`` is 'trainer' or 'jockey'."""
    entity_col = f"{role}_id"
    d = cfg["defaults"]
    prior_win = d["shrinkage_prior_win_rate"]
    k = d["shrinkage_k_defaults"][f"{role}_at_other_tracks"]

    wanted = {f"{role}_at_other_tracks_winrate",
              f"{role}_at_other_tracks_starts",
              f"{role}_home_track", f"is_at_{role}_home_track"}
    if not (wanted & active):
        return pd.DataFrame({"entry_id": raw["entry_id"]})

    counts = _per_track_prior_counts(raw, entity_col, role)
    out = pd.DataFrame({"entry_id": raw["entry_id"]})

    here_starts = _pick_by_track(counts, raw["track_id"], f"{role}_starts_t{{t}}")
    here_wins = _pick_by_track(counts, raw["track_id"], f"{role}_wins_t{{t}}")
    other_starts = counts[f"{role}_starts_all"].to_numpy() - here_starts
    other_wins = counts[f"{role}_wins_all"].to_numpy() - here_wins

    if f"{role}_at_other_tracks_winrate" in active:
        rate = shrink_rate_vec(other_wins, other_starts, prior_win, k)
        # A connection that has never left this track has no cross-track
        # record to report. NULL beats handing the model the bare prior.
        out[f"{role}_at_other_tracks_winrate"] = np.where(
            other_starts > 0, rate, np.nan)
    if f"{role}_at_other_tracks_starts" in active:
        out[f"{role}_at_other_tracks_starts"] = other_starts

    if wanted & {f"{role}_home_track", f"is_at_{role}_home_track"} & active:
        home = _home_track(counts, role)
        if f"{role}_home_track" in active:
            out[f"{role}_home_track"] = home
        if f"is_at_{role}_home_track" in active:
            today = raw["track_code"].astype(object)
            out[f"is_at_{role}_home_track"] = (
                (home == today).where(home.notna())
                .astype("boolean").astype("Int8")
            )
    return out


def compute_horse_shipping(
    raw: pd.DataFrame, ctx: dict, cfg: dict, active: set[str]
) -> pd.DataFrame:
    """Shipping record for the horse.

    A start counts as a *ship* when its track differs from the track of that
    horse's own immediately-preceding start. ``horse_shipping_success_rate``
    is the shrunk ITM rate over prior ships only — ITM rather than win
    because DPv1's target is ITM and ships are a thin sample.
    """
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    wanted = {"is_shipping_today", "horse_shipping_success_rate",
              "horse_shipping_starts"}
    if not (wanted & active):
        return out

    prev_track = ctx["prev"]["prev_track_id"]
    is_ship = (raw["track_id"] != prev_track).where(prev_track.notna())

    if "is_shipping_today" in active:
        out["is_shipping_today"] = is_ship.astype("boolean").astype("Int8")

    if not ({"horse_shipping_success_rate", "horse_shipping_starts"} & active):
        return out

    local = raw[["entry_id", "horse_id", "race_date_dt"]].copy()
    local["ship_start"] = is_ship.fillna(False).astype(float)
    local["ship_itm"] = local["ship_start"] * raw["is_itm"].astype(float)

    rolled = _prior_by_entity_expanding(
        local, entity_col="horse_id",
        value_cols=["ship_start", "ship_itm"], prefix="sh",
    )
    rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")
    starts = rolled["sh_ship_start"].to_numpy()
    itm = rolled["sh_ship_itm"].to_numpy()

    if "horse_shipping_starts" in active:
        out["horse_shipping_starts"] = starts
    if "horse_shipping_success_rate" in active:
        d = cfg["defaults"]
        rate = shrink_rate_vec(itm, starts, d["shrinkage_prior_itm_rate"],
                               d["shrinkage_k_defaults"]["horse_shipping"])
        # NULL for horses that have never shipped — the overwhelming majority.
        out["horse_shipping_success_rate"] = np.where(starts > 0, rate, np.nan)
    return out


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    frames = [
        compute_connection_cross_track(raw, cfg, active, "trainer"),
        compute_connection_cross_track(raw, cfg, active, "jockey"),
        compute_horse_shipping(raw, ctx, cfg, active),
    ]
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="entry_id", how="left")
    return out
