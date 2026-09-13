"""Multi-race class context (Phase 6D, Gaps #10 and #11).

DPv1's only class-movement feature, ``class_score_change_from_last``, looks
one race back. Gap #11 measured what that misses on 75,940 out-of-fold starts:
a horse racing BELOW its recent-average class is under-rated by +1.60pp raw
(z 7.58) and one racing ABOVE it over-rated by -2.01pp. Where the last race was
already at today's class, so the one-race feature sees no move at all, the miss
is +3.38pp (z 9.0). Gap #10 found a second, disjoint effect: the model
under-trusts a *consistent* finish record earned at today's class, in both
directions.

Window definition (identical to the Gap #9-#11 diagnostics)
-----------------------------------------------------------
The horse's prior **finished** starts (``finish_pos`` not null), strictly
before today's race date: the last 5, or the last 3 when only 3 or 4 exist.
With fewer than 3 the context is missing. DNFs carry no finish position and are
not in the window. Matching the diagnostic exactly is deliberate: it lets the
built columns be checked against the Gap #11 counts row for row.

Class crosses race-type bands on ``class_score`` (``dpv1_common.class_score_vec``),
which places allowance, starter, stakes and claiming races on one ladder. Gap
#11 found the ranking gain lives in exactly those cross-family drops.

Missingness
-----------
Fewer than 3 prior finished starts: ``avg_class_recent`` is imputed with
today's race ``class_score`` (constant within a race, so this is "the current
race's mean class"), ``class_drop_signed`` is therefore 0,
``class_direction`` is ``NO_HISTORY``, and ``class_context_missing`` is 1.
The imputation fills the value, so the preprocessor would generate no
``__missing`` flag on its own; the explicit indicator is emitted for that
reason. It is knowable at post time (it is a prior-start count), not a label
leak. Where today's own ``class_score`` is NULL (28 of 222,362 entries) every
numeric column stays NULL and the preprocessor's own median fill and flag
apply.

Leakage: every quantity uses starts with a strictly earlier race date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 5
FALLBACK = 3
DIRECTION_BAND = 0.5          # Doug's spec: |signed| <= 0.5 is "roughly same"
LOW_VARIANCE_SD = 1.5         # Gap #9 LOW bucket: sample SD of finish position

FEATURES = [
    "avg_class_recent",           # mean class_score over the window
    "class_drop_signed",          # today - avg_class_recent (+ = rising)
    "class_direction",            # DROPPING / SAME / RISING / NO_HISTORY
    "class_context_missing",      # 1 when < 3 prior finished starts
    "low_finish_variance",        # sample SD of window finishes <= 1.5
    "lowvar_x_dropping",          # consistency x direction (SAME is reference)
    "lowvar_x_rising",
    "lowvar_same_x_mean_finish",  # Gap #10 two-sided slope: consistent, same class, x mean finish
]


def _window_stats(raw: pd.DataFrame) -> pd.DataFrame:
    """Per-entry window mean class, mean finish, finish SD. Strictly prior dates."""
    n = len(raw)
    avg_cls = np.full(n, np.nan)
    mean_fin = np.full(n, np.nan)
    sd_fin = np.full(n, np.nan)

    dates = raw["race_date"].astype(str).to_numpy()
    fin = raw["finish_pos"].to_numpy(dtype=float)
    cls = raw["class_score"].to_numpy(dtype=float)
    race_ids = raw["race_id"].to_numpy()
    order = np.lexsort((race_ids, dates, raw["horse_id"].to_numpy()))
    horse_sorted = raw["horse_id"].to_numpy()[order]
    bounds = np.flatnonzero(np.r_[True, horse_sorted[1:] != horse_sorted[:-1], True])

    for s, e in zip(bounds[:-1], bounds[1:]):
        idx = order[s:e]                       # this horse's entries, date order
        done = idx[~np.isnan(fin[idx])]        # finished starts only
        if len(done) < FALLBACK:
            continue
        done_dates = dates[done]
        # number of finished starts strictly before each entry's date
        k_prior = np.searchsorted(done_dates, dates[idx], side="left")
        for pos, k in zip(idx, k_prior):
            if k < FALLBACK:
                continue
            take = WINDOW if k >= WINDOW else FALLBACK
            w = done[k - take:k]
            c = cls[w]
            c = c[~np.isnan(c)]
            if len(c):
                avg_cls[pos] = c.mean()
            f = fin[w]
            mean_fin[pos] = f.mean()
            sd_fin[pos] = f.std(ddof=1)
    return pd.DataFrame({"avg_cls": avg_cls, "mean_fin": mean_fin, "sd_fin": sd_fin},
                        index=raw.index)


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    if not (set(FEATURES) & active):
        return out

    w = _window_stats(raw)
    today = raw["class_score"].astype(float)
    has_ctx = w["avg_cls"].notna()
    today_known = today.notna()

    missing = (~has_ctx).astype(float)
    avg = w["avg_cls"].where(has_ctx, today)            # impute with today's race class
    signed = today - avg                                  # 0 where imputed
    direction = np.select(
        [~has_ctx, signed < -DIRECTION_BAND, signed > DIRECTION_BAND],
        ["NO_HISTORY", "DROPPING", "RISING"], default="SAME")
    direction = pd.Series(direction, index=raw.index).where(today_known)

    lowvar = ((w["sd_fin"] <= LOW_VARIANCE_SD) & has_ctx).astype(float)
    dropping = (direction == "DROPPING").astype(float)
    rising = (direction == "RISING").astype(float)
    same = (direction == "SAME").astype(float)

    cols = {
        "avg_class_recent": avg.where(today_known),
        "class_drop_signed": signed.where(today_known),
        "class_direction": direction,
        "class_context_missing": missing,
        "low_finish_variance": lowvar,
        "lowvar_x_dropping": lowvar * dropping,
        "lowvar_x_rising": lowvar * rising,
        "lowvar_same_x_mean_finish": (lowvar * same * w["mean_fin"].fillna(0.0)),
    }
    for name, series in cols.items():
        if name in active:
            out[name] = series.to_numpy() if name == "class_direction" else \
                pd.to_numeric(series, errors="coerce").astype(float).to_numpy()
    return out
