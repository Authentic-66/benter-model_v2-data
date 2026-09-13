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

Step 3 refinement (2026-09-13): the last-race class deadband
------------------------------------------------------------
Path A left a hole and slightly widened it. The model's only fine-grained
last-race class term is ``class_score_change_from_last``, a raw signed
difference on a ladder where 16% of rows move more than 20 points; after the
Preprocessor's standardisation a 1-2 point move is about 0.1 sigma. The
categorical ``class_change_from_last`` cannot rescue it either, because its
``class_change_threshold`` is 3.0, so every move of 1 or 2 points is labelled
SAME. The result is a blind spot exactly one to two ladder points wide.

Measured on the Path A fold predictions, residual (y - p_fund) by the integer
last-race move, with the multi-race window present:

    move   -2      -1       0      +1      +2
    resid  +2.88  +1.17   -0.03   -4.69   -5.27      (candidate)
    resid  +3.82  +1.97   -0.20   -5.14   -5.57      (control)

A clean monotone gradient the model treats as one flat category, asymmetric:
small rises hurt about twice as much as small drops help. It is present in the
control too, so it is a pre-existing error, not one Path A created. What Path A
did was credit these horses a second time: ``class_drop_signed`` resolves
fractional class, so a horse that dropped hard last out and steps back up 1-2
points today still reads BELOW its window average and is credited for relief it
is not getting. That is the -4.86pp last-race-RISE x window-BELOW cell.

Robustness: the gradient holds in all 4 years, all 4 tracks, and every race
type with a meaningful n (claiming -6.42, maiden-claiming -6.60, allowance
-4.30, MSW -2.97). It also holds where the multi-race window is missing
(-3.63, z -3.4), so the fine direction terms are deliberately **not** gated on
window context.

Leakage: every quantity uses starts with a strictly earlier race date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 5
FALLBACK = 3
DIRECTION_BAND = 0.5          # Doug's spec: |signed| <= 0.5 is "roughly same"
LOW_VARIANCE_SD = 1.5         # Gap #9 LOW bucket: sample SD of finish position
FINE_BAND = 0.5               # any nonzero ladder move; the model's own deadband is 3.0
MOVE_CLIP = 10.0              # bound the tier-jump tail so 1-2 point moves survive scaling

FEATURES = [
    "avg_class_recent",           # mean class_score over the window
    "class_drop_signed",          # today - avg_class_recent (+ = rising)
    "class_direction",            # DROPPING / SAME / RISING / NO_HISTORY
    "class_context_missing",      # 1 when < 3 prior finished starts
    "low_finish_variance",        # sample SD of window finishes <= 1.5
    "lowvar_x_dropping",          # consistency x direction (SAME is reference)
    "lowvar_x_rising",
    "lowvar_same_x_mean_finish",  # Gap #10 two-sided slope: consistent, same class, x mean finish
    # Step 3: the last-race deadband, plus the one interaction that earns its
    # place. Both window interactions rank near the bottom by |coef| (197 and
    # 220 of 250), but that measures the AVERAGE contribution. Dropping both
    # gave back 0.7pp on the target cell (-1.13 -> -1.84pp), because that cell
    # is where class_drop_signed is large and negative, so a small coefficient
    # on a +/-10 term still moves it. `_down` had no such cell and was dropped;
    # `_up` is kept. Coefficient rank is not evidence a term is idle — check
    # the cell it was built for.
    "last_class_direction_fine",   # UP / SAME / DOWN / NO_LAST at +/-0.5, not 3.0
    "last_class_move_clipped",     # last-race signed move, clipped to +/-10
    "class_drop_signed_x_last_up", # window position when the last race was a rise
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

    # --- Step 3: the last-race move at a band the model can actually see ---
    # ctx["prev"] is the most recent prior start per horse (built once in
    # feature_builder_dpv1.build_context), the same source
    # class_change_features uses for class_score_change_from_last. Null where
    # the horse has no prior start inside the corpus.
    prev_cls = ctx["prev"]["prev_class_score"].astype(float)
    last_move = today - prev_cls                      # + = today is a class rise
    has_last = last_move.notna()
    last_dir = np.select(
        [~has_last, last_move > FINE_BAND, last_move < -FINE_BAND],
        ["NO_LAST", "UP", "DOWN"], default="SAME")
    last_dir = pd.Series(last_dir, index=raw.index).where(today_known)
    last_up = (last_dir == "UP").astype(float)
    # 0 where there is no prior start; the NO_LAST level of the categorical
    # carries that case, so no second __missing flag is created for it.
    move_clipped = last_move.clip(-MOVE_CLIP, MOVE_CLIP).fillna(0.0)
    # Clipped on the same scale so a cross-band window average cannot dominate.
    signed_clipped = signed.clip(-MOVE_CLIP, MOVE_CLIP)

    cols = {
        "avg_class_recent": avg.where(today_known),
        "class_drop_signed": signed.where(today_known),
        "class_direction": direction,
        "class_context_missing": missing,
        "low_finish_variance": lowvar,
        "lowvar_x_dropping": lowvar * dropping,
        "lowvar_x_rising": lowvar * rising,
        "lowvar_same_x_mean_finish": (lowvar * same * w["mean_fin"].fillna(0.0)),
        "last_class_direction_fine": last_dir,
        "last_class_move_clipped": move_clipped.where(today_known),
        "class_drop_signed_x_last_up": (signed_clipped * last_up).where(today_known),
    }
    for name, series in cols.items():
        if name in active:
            categorical = name in ("class_direction", "last_class_direction_fine")
            out[name] = series.to_numpy() if categorical else \
                pd.to_numeric(series, errors="coerce").astype(float).to_numpy()
    return out
