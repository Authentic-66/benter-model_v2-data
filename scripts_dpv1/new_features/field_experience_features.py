"""Field-experience composition (Phase 6D, Gap #6).

Every other feature in DPv1 describes a horse. These describe the *field* it
is running against — specifically, how much racing experience the field
collectively has.

Why the model needs this
------------------------
DPv1 already sees each horse's own ``career_starts``. What it cannot see is
whether the horse beside it has run twenty times or never. That gap is the
mechanism behind Gap #6: a maiden race where eight of twelve runners have
never started is a different object from a race where all twelve are seasoned,
and the model currently scores them identically.

The damage is not confined to the inexperienced horses either. Pace projection,
class-of-field and the field-relative features are all computed across the
whole field, so blank runners degrade those estimates for the experienced
horses standing beside them. On CT 2026-08-29 R3 the top pick had 80% feature
coverage of its own and still finished 5th, in a race where 5 of 7 runners had
fewer than three starts.

These features give the model a handle on that: not "this horse is unknown"
but "this race is mostly unknowns".

NULL handling: absent counts as zero
------------------------------------
``career_starts`` is a prior-start count from ``build_context`` and is 0, never
NULL, for a horse with no history. Any NULL that does reach this module is
filled with 0 rather than dropped, and the choice is load-bearing: excluding
unknown horses from the denominator would make ``field_pct_debut`` structurally
incapable of exceeding 0, since the horses it exists to count are exactly the
ones that would be excluded.

``field_experience_variance`` uses the population standard deviation (ddof=0)
so that a one-horse field yields 0.0 rather than NaN. With that, none of the
seven can be null, so the preprocessor generates no ``__missing`` indicators
for them — there is nothing missing to indicate.

What "experience" means here, precisely
---------------------------------------
It means **starts this corpus can see**, not starts the horse has run. DPv1
knows four tracks, so a shipper with twenty runs at Laurel contributes to
``field_pct_debut`` exactly as a true first-time starter does. That is Gap #1
showing through Gap #6, and it is not fixable here: separating the two needs
``pp_career_starts`` from ``pp_entries_raw``, which is blocked on routine PP
ingest (see PHASE_6D_ROADMAP.md).

So read ``field_pct_debut`` as "share of the field this model has never seen".
That is a weaker claim than "share of the field that has never raced", and it
is the honest one. It is still the right signal for the thing being modelled —
the model's uncertainty about this race — but it is a fact about the corpus as
much as about the horses, and a version of these features built after PP
ingest lands should be expected to behave differently.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEBUT_MAX_STARTS = 0
UNDERRACED_MAX_STARTS = 3

FEATURES = [
    "field_avg_career_starts",
    "field_median_career_starts",
    "field_max_career_starts",
    "field_min_career_starts",
    "field_pct_debut",
    "field_pct_underraced",
    "field_experience_variance",
]

# ---------------------------------------------------------------------------
# Interaction / relative terms (Phase 6D, 2026-09-01)
#
# The seven aggregates above are constant within a race, so under DPv1's
# no-interaction architecture they shift every horse's linear predictor
# equally and cannot reorder the race. Measured: -0.045pp top-pick ITM against
# a corpus-matched control. See the Feature Design Principle in
# PHASE_6D_ROADMAP.md.
#
# These six do vary within a race, by combining the horse's own
# ``career_starts`` with the field it is running against. They are the same
# information expressed at a grain the ranking can actually use.
#
# The mechanism they are meant to capture is the CT 2026-08-29 R6 signature:
# Zaptastic, 26 career starts, in a field where four runners had never been
# seen. It won, from the model's 7th choice. Nothing in the main-effects set
# could express "this horse is the only experienced runner here", because that
# is a statement about the horse *relative to* its field.
#
# Note that ``train_dpv1.py --with-interaction`` does NOT control these. That
# flag toggles a hardcoded pair of class-change terms
# (``INTERACTION_FEATURES`` in prepare_training_dpv1.py) and has nothing to do
# with field experience. These are ordinary features, on by default.
# ---------------------------------------------------------------------------
INTERACTIONS = [
    "career_starts_vs_field_mean",
    "career_starts_pctile_in_field",
    "is_most_experienced_in_field",
    "career_starts_x_field_pct_underraced",
    "career_starts_x_field_variance",
    "experience_edge_x_pct_underraced",
]

ALL_FEATURES = FEATURES + INTERACTIONS


def compute(raw: pd.DataFrame, ctx: dict, cfg: dict,
            active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})
    if not (set(ALL_FEATURES) & active):
        return out

    # Absent history counts as zero starts -- see the module docstring.
    starts = pd.to_numeric(
        ctx["career"]["career_starts"], errors="coerce").fillna(0.0)
    frame = pd.DataFrame({
        "race_id": raw["race_id"].to_numpy(),
        "starts": starts.to_numpy(),
    }, index=raw.index)

    grp = frame.groupby("race_id")["starts"]
    agg = {
        "field_avg_career_starts": grp.transform("mean"),
        "field_median_career_starts": grp.transform("median"),
        "field_max_career_starts": grp.transform("max"),
        "field_min_career_starts": grp.transform("min"),
        # Population std: a one-horse field is zero-variance, not undefined.
        "field_experience_variance": grp.transform(lambda s: s.std(ddof=0)),
        "field_pct_debut": frame.assign(
            f=(frame["starts"] <= DEBUT_MAX_STARTS).astype(float)
        ).groupby("race_id")["f"].transform("mean"),
        "field_pct_underraced": frame.assign(
            f=(frame["starts"] < UNDERRACED_MAX_STARTS).astype(float)
        ).groupby("race_id")["f"].transform("mean"),
    }

    for name, series in agg.items():
        if name in active:
            out[name] = pd.to_numeric(series, errors="coerce").fillna(0.0) \
                          .astype(float).to_numpy()

    # --- interaction / relative terms -------------------------------------
    # Each of these varies within a race, which is the whole point: a term
    # that is constant across the field cannot change which horse ranks first.
    own = frame["starts"]
    edge = own - agg["field_avg_career_starts"]
    inter = {
        "career_starts_vs_field_mean": edge,
        # Within-race percentile of own experience. Purely ordinal, so it is
        # immune to the scale problems the raw products can have.
        "career_starts_pctile_in_field":
            frame.groupby("race_id")["starts"].rank(pct=True),
        # "The only seasoned runner in a green field" -- the R6 signature.
        # Guarded on max > 0 so a field of all-debutants does not mark every
        # horse as most experienced.
        "is_most_experienced_in_field":
            ((own >= agg["field_max_career_starts"])
             & (agg["field_max_career_starts"] > 0)).astype(float),
        "career_starts_x_field_pct_underraced":
            own * agg["field_pct_underraced"],
        "career_starts_x_field_variance":
            own * agg["field_experience_variance"],
        # Experience edge, weighted by how green the field is: being three
        # starts above average matters more among maidens than among veterans.
        "experience_edge_x_pct_underraced":
            edge * agg["field_pct_underraced"],
    }
    for name, series in inter.items():
        if name in active:
            out[name] = pd.to_numeric(series, errors="coerce").fillna(0.0) \
                          .astype(float).to_numpy()
    return out
