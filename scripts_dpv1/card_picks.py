"""Phase 6B: top-4 ITM rankings for a whole card, in a form usable at a track.

    python scripts_dpv1/card_picks.py --track ELP --date 2026-08-23 \
        --pp-file Ellis/elp-pps-files/elp0823y.pdf --save

This is the Phase 6B deliverable and it is deliberately the plainest thing in
the toolkit: a ranked list per race, the model's P(ITM), and the morning line
next to it. No tickets, no EV, no bet sizing. Phase 6A backtested the EV path
over 14,517 races and found that tickets it labelled +EV returned -34% against
-28.6% for betting indiscriminately, so pricing tickets is not something this
toolkit should be doing. Ranking horses is.

How to read it
--------------
``P(ITM)`` is the model's probability the horse finishes in the top three,
formed from the horses alone — DPv1's fundamental side, with no odds input.
That independence is the whole point: it is a second opinion formed without
looking at the board, so where it disagrees with the morning line, the
disagreement is real information about the model rather than an echo of the
price.

``ML`` is the Brisnet morning line, carried purely for comparison. It is not
an input to any prediction here. The v1 model gave morning-line odds its single
largest coefficient and that anchoring is the specific flaw the v2/DPv1 rebuild
exists to correct, so it is shown beside the model's opinion and never inside
it.

``cov`` is the fraction of DPv1's 95 features that were available for that
horse. It is the most important column on the page and the easiest to skip.
A horse at 45% is one the corpus has never seen — a shipper or a first-time
starter — and its probability is closer to a field-average prior than to a
real assessment. Phase 6A measured what low coverage does: at 27% coverage the
ranking retains rho=0.61 against a full-feature score and the top pick changes
in 56% of races. Weight the rankings by ``cov`` when you read them.

What the model does not know
----------------------------
As of Phase 6C, DPv1 is trained on GP, CT, MNR **and ELP**, so an Ellis Park
row now scores with a real ``track_code`` coefficient rather than an all-zero
block. Measured on held-out folds, that moved the ELP fundamental model from
AUC 0.627 to 0.659 against 0.696 on the home tracks — better, still worse.
Scoring any *other* track remains extrapolation and the runner says so.

The binding limitation is no longer the track list, it is the corpus. ELP is a
~30-day boutique meet and most of its runners ship in from Churchill, Indiana
Grand and Kentucky Downs, none of which are loaded. 38% of ELP starters in
*non-maiden* races have no prior start in ``racing_full.db`` — against 5-7% at
GP/CT/MNR — so their history-derived features are blank and their ``cov`` is
low. That is what the ``cov`` column is measuring here, and it is why it is the
most important column on the page.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
LOG_DIR = DPV1_DIR / "logs"
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import (  # noqa: E402
    DEFAULT_DB, DEFAULT_MODEL, coverage_report, load_model,
    load_race_from_db, predict_card, resolve_race_id,
)
from pp_feature_bridge import apply_to_card, pp_index  # noqa: E402
from simulate_race import simulate_prediction  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Human-readable feature labels for the "reasons" block.
# Add entries as you learn which features come up. Anything not listed falls
# back to the raw name. Run this to see what's showing up:
#   python -c "import pickle; m=pickle.load(open('scripts_dpv1/dpv1.pkl','rb')); \
#              print('\n'.join(m.fundamental.feature_names_[:40]))"
# ─────────────────────────────────────────────────────────────────────────────
# Human-readable feature labels for the "reasons" block.
PLAIN_LABELS: dict[str, str] = {
    # ── Class ───────────────────────────────────────────────────────
    "class_score": "class rating",
    "class_score_change_from_last": "class rating change vs last",
    "class_change_from_last__UP": "moving up in class",
    "class_change_from_last__DOWN": "dropping in class",
    "class_change_from_last__SAME": "same class as last",
    "claiming_price": "claiming price",
    "purse_change_from_last": "purse change vs last",

    # ── Speed / recent form ─────────────────────────────────────────
    "last_race_speed_figure": "speed figure last race",
    "speed_trajectory_3_races": "speed trend (last 3)",
   "last_race_beaten_lengths": "closeness to winner (last race)",
    "last_race_finish_pos": "finish placement (last race)",
    "last_race_won": "won last race",
    "last_3_avg_finish": "avg finish placement (last 3)",
    "last_race_troubled_trip": "trouble in last trip",
    "second_race_back_pattern": "2nd-back off layoff pattern",
    "last_race_was_maiden": "last race was maiden",
    "last_race_field_size": "last race field size",
    "condition_change_from_last_race": "track-condition change vs last",

    # ── Distance ────────────────────────────────────────────────────
    "distance_furlongs": "distance (furlongs)",
    "distance_yards": "distance (yards)",
    "distance_specialist_flag": "distance specialist",
    "distance_change_from_last_race": "distance change vs last",
    "distance_change_bucket__sprint_to_route": "sprint → route stretch-out",
    "distance_change_bucket__route_to_sprint": "route → sprint cutback",
    "distance_change_bucket__sprint_to_sprint": "sprint → sprint",
    "distance_change_bucket__route_to_route": "route → route",

    # ── Surface ─────────────────────────────────────────────────────
    "surface_specialist_flag": "surface specialist",
    "surface_change_from_last_race": "surface change vs last",
    "surface__Dirt": "on dirt",
    "surface__Turf": "on turf",
    "surface__AllWeather": "on all-weather",
    "historical_surface_winrate_shrunk": "career win% on surface",
    "historical_condition_winrate_shrunk": "career win% in these conditions",

    # ── Jockey ──────────────────────────────────────────────────────
    "jockey_30d_winrate_shrunk": "jockey win% (30d)",
    "jockey_90d_winrate_shrunk": "jockey win% (90d)",
    "jockey_365d_winrate_shrunk": "jockey win% (1yr)",
    "jockey_at_track_winrate_shrunk": "jockey win% at track",
    "jockey_at_distance_winrate_shrunk": "jockey win% at distance",
    "jockey_at_surface_winrate_shrunk": "jockey win% on surface",
    "jockey_at_other_tracks_winrate": "jockey win% at other tracks",
    "jockey_at_other_tracks_starts": "jockey starts at other tracks",
    "jockey_starts_30d": "jockey starts (30d)",
    "days_since_jockey_last_win": "jockey recency (days since win)",
    "is_at_jockey_home_track": "at jockey's home track",
    "jockey_home_track__CT": "jockey home = CT",
    "jockey_home_track__ELP": "jockey home = ELP",
    "jockey_home_track__GP": "jockey home = GP",
    "jockey_home_track__MNR": "jockey home = MNR",

    # ── Trainer ─────────────────────────────────────────────────────
    "trainer_30d_winrate_shrunk": "trainer win% (30d)",
    "trainer_90d_winrate_shrunk": "trainer win% (90d)",
    "trainer_365d_winrate_shrunk": "trainer win% (1yr)",
    "trainer_at_track_winrate_shrunk": "trainer win% at track",
    "trainer_at_distance_winrate_shrunk": "trainer win% at distance",
    "trainer_at_surface_winrate_shrunk": "trainer win% on surface",
    "trainer_at_other_tracks_winrate": "trainer win% at other tracks",
    "trainer_at_other_tracks_starts": "trainer starts at other tracks",
    "trainer_starts_30d": "trainer starts (30d)",
    "days_since_trainer_last_win": "trainer recency (days since win)",
    "trainer_dropping_class_win_pct": "trainer win% dropping class",
    "trainer_rising_class_win_pct": "trainer win% rising class",
    "trainer_off_layoff_win_pct": "trainer win% off layoff",
    "trainer_first_time_starters_win_pct": "trainer win% first-time starters",
    "trainer_recent_form_trend": "trainer recent form trend",
    "new_trainer_flag": "new trainer",
    "is_at_trainer_home_track": "at trainer's home track",
    "trainer_home_track__CT": "trainer home = CT",
    "trainer_home_track__ELP": "trainer home = ELP",
    "trainer_home_track__GP": "trainer home = GP",
    "trainer_home_track__MNR": "trainer home = MNR",

    # ── Career ──────────────────────────────────────────────────────
    "career_starts": "career starts",
    "career_wins": "career wins",
    "career_win_pct_shrunk": "career win%",
    "career_itm_pct_shrunk": "career ITM%",

    # ── Shipping ────────────────────────────────────────────────────
    "is_shipping_today": "shipping in today",
    "horse_shipping_starts": "prior shipping starts",
    "horse_shipping_success_rate": "shipping success rate",

    # ── Layoff / recency ────────────────────────────────────────────
    "days_since_last_race": "days since last (recency)",
    "last_race_days_ago": "last race (days ago)",

    # ── Equipment / meds ────────────────────────────────────────────
    "blinkers_change_flag": "blinkers change",
    "is_first_time_blinkers": "first-time blinkers",
    "equipment_change_flag": "equipment change",
    "lasix_first_time": "first-time Lasix",
    "is_first_time_lasix": "first-time Lasix",
    "lasix_off": "Lasix off",

    # ── Physical / draw ─────────────────────────────────────────────
    "weight_lbs": "weight (lbs)",
    "weight_change_from_last_race": "weight change vs last",
    "gate_break_avg_last_3": "avg gate break (last 3)",
    "post_position": "post position",
    "field_size": "field size",

    # ── Pace ────────────────────────────────────────────────────────
    "pace_progression_last_race": "pace progression last race",
    "pace_type_last_race__front": "front-runner last race",
    "pace_type_last_race__stalk": "stalker last race",
    "pace_type_last_race__mid": "mid-pack last race",
    "pace_type_last_race__close": "closer last race",
    "early_pace_position_projected__front": "projected early: on the lead",
    "early_pace_position_projected__press": "projected early: pressing",
    "early_pace_position_projected__off": "projected early: off the pace",
    "expected_pace_shape__hot": "expected hot pace",
    "expected_pace_shape__moderate": "expected moderate pace",
    "expected_pace_shape__slow": "expected slow pace",
    "pace_pressure_in_race__hot": "pace pressure: hot",
    "pace_pressure_in_race__moderate": "pace pressure: moderate",
    "pace_pressure_in_race__slow": "pace pressure: slow",
    "running_style_last_3__front": "front-runner style",
    "running_style_last_3__stalk": "stalking style",
    "running_style_last_3__mid": "mid-pack style",
    "running_style_last_3__close": "closer style",

    # ── Track / bias ────────────────────────────────────────────────
    "track_dirt_bias_90d": "track dirt bias (90d)",
    "track_turf_bias_90d": "track turf bias (90d)",
    "outside_bias_flag": "outside bias flag",
    "rail_bias_flag": "rail bias flag",
    "is_sealed_track": "sealed track",
    "track_specialist_flag": "track specialist",
    "starts_at_track": "starts at this track",
    "wins_at_track": "wins at this track",
    "track_distance_par_time_sec": "par time at distance",
    "track_bias_running_style__front": "track bias favors front",
    "track_bias_running_style__stalk": "track bias favors stalkers",
    "track_bias_running_style__mid": "track bias favors mid-pack",
    "track_bias_running_style__close": "track bias favors closers",
    "track_condition__Fast": "track: fast",
    "track_condition__Firm": "track: firm",
    "track_condition__Good": "track: good",
    "track_condition__Muddy": "track: muddy",
    "track_condition__Sloppy": "track: sloppy",
    "track_condition__Heavy": "track: heavy",
    "track_condition__WetFast": "track: wet-fast",
    "track_condition__Yielding": "track: yielding",
    "track_code__CT": "at CT",
    "track_code__ELP": "at ELP",
    "track_code__GP": "at GP",
    "track_code__MNR": "at MNR",

    # ── Field experience (Phase 6D gap #6) ─────────────────────────
    "field_avg_career_starts": "field avg career starts",
    "field_median_career_starts": "field median career starts",
    "field_max_career_starts": "most experienced rival",
    "field_min_career_starts": "least experienced rival",
    "field_pct_debut": "share of field unraced (debut or shipper)",
    "field_pct_underraced": "share of field under 3 starts",
    "field_experience_variance": "spread of field experience",
    "career_starts_vs_field_mean": "experience vs field average",
    "career_starts_pctile_in_field": "experience rank within field",
    "is_most_experienced_in_field": "most experienced in the field",
    "career_starts_x_field_pct_underraced": "experience in a green field",
    "career_starts_x_field_variance": "experience in a mixed-experience field",
    "experience_edge_x_pct_underraced": "experience edge, weighted by field greenness",

    # ── Race type ──────────────────────────────────────────────────
    "race_type__ALLOWANCE": "allowance race",
    "race_type__ALLOWANCEOPTIONALCLAIMING": "allowance optional claiming",
    "race_type__CLAIMING": "claiming race",
    "race_type__HANDICAP": "handicap race",
    "race_type__MAIDENCLAIMING": "maiden claiming",
    "race_type__MAIDENOPTIONALCLAIMING": "maiden optional claiming",
    "race_type__MAIDENSPECIALWEIGHT": "maiden special weight",
    "race_type__STAKES": "stakes race",
    "race_type__STARTERALLOWANCE": "starter allowance",
    "race_type__STARTERHANDICAP": "starter handicap",
    "race_type__STARTEROPTIONALCLAIMING": "starter optional claiming",

}


def _label(raw: str) -> str:
    """Map an internal feature name to something readable.

    Handles three patterns:
      1. Direct lookup in PLAIN_LABELS.
      2. ``__missing`` suffix — resolve the base name, then wrap.
      3. Anything else — swap underscores for spaces.
    """
    if raw in PLAIN_LABELS:
        return PLAIN_LABELS[raw]

    if raw.endswith("__missing"):
        base = raw[: -len("__missing")]
        base_label = PLAIN_LABELS.get(base, base.replace("_", " "))
        return f"no data: {base_label}"

    # Categorical one-hot Claude doesn't have an explicit label for
    # ("something____MISSING__", "foo__bar_baz"): render cleanly.
    if "__" in raw:
        head, _, tail = raw.rpartition("__")
        head_label = PLAIN_LABELS.get(head, head.replace("_", " "))
        tail_clean = tail.replace("_", " ").strip()
        if tail_clean.upper() == "MISSING":
            return f"no data: {head_label}"
        return f"{head_label} = {tail_clean}"

    # Case 3 from the docstring. This line was indented one level too far and
    # sat after a return, so it was unreachable: any name without a "__" and
    # without a PLAIN_LABELS entry fell off the end and rendered as the string
    # "None" in the reasons block. Found 2026-09-01 via the field-experience
    # interaction terms, which are exactly that shape.
    return raw.replace("_", " ")


def compute_reasons(card, model, top_k: int = 3,
                    threshold: float = 0.05) -> list[dict]:
    """For each horse, return the top pushes above/below the race baseline.

    Returned value is a list (one per horse, in card order) of dicts with
    ``pos`` and ``neg`` lists of ``(label, log_odds_delta)`` tuples.

    The delta is in log-odds relative to this race's average horse. A +0.20
    push roughly means "this feature makes the horse ~20% more likely to hit
    the board than the field average, before other effects."
    """
    X = np.asarray(model.preprocessor.transform(card.frame), dtype=float)
    coef = np.asarray(model.fundamental.coef_, dtype=float)
    names = list(model.fundamental.feature_names_)

    # (n_horses × n_features) contribution to each horse's log-odds
    contribs = X * coef
    # This race's baseline horse (the field average)
    baseline = contribs.mean(axis=0)
    # How each horse differs from that baseline
    deltas = contribs - baseline

    out = []
    for h in range(X.shape[0]):
        d = deltas[h]
        order = np.argsort(-np.abs(d))
        pos: list[tuple[str, float]] = []
        neg: list[tuple[str, float]] = []
        for idx in order:
            val = float(d[idx])
            if abs(val) < threshold:
                continue
            if len(pos) >= top_k and len(neg) >= top_k:
                break
            if val > 0 and len(pos) < top_k:
                pos.append((_label(names[idx]), val))
            elif val < 0 and len(neg) < top_k:
                neg.append((_label(names[idx]), val))
        out.append({"pos": pos, "neg": neg})
    return out

log = logging.getLogger("card_picks")

# ─────────────────────────────────────────────────────────────────────────────
# Shipper detection (Phase 6D gap #1, interim warning only).
#
# DPv1's history features are built from ``entries`` and
# ``computed_speed_figures_dpv1``, and both hold rows for the four training
# tracks and nothing else. A horse whose whole career has been at Laurel, Parx
# or Churchill is therefore invisible to the model: not "a horse with a weak
# record" but "a horse with no record", which the feature block renders as a
# near-prior guess and the ranking treats as a bad one.
#
# The PP file has that horse's full past performances, parsed and sitting right
# there. Wiring them into the feature builder is Phase 6D proper. Until then
# this flags the horses where the ranking is least trustworthy so a reader
# knows to open the PP rather than believe the number.
# ─────────────────────────────────────────────────────────────────────────────
TRAINING_TRACKS = ("CT", "ELP", "GP", "MNR")
SHIPPER_COV_MAX = 0.60
SHIPPER_MIN_PRIOR_STARTS = 2

# ─────────────────────────────────────────────────────────────────────────────
# PP reranker (Phase 6D Gap #1, shipped 2026-09-01).
#
# A second-stage logistic model over the base model's fundamental logit, fitted
# on the rows where Brisnet PP data exists. It corrects a measured bias: the
# base model OVER-rates horses the corpus cannot see, because a blank history
# block is median-imputed and flagged, which pulls the estimate toward a
# population prior of ~0.35-0.41 while those horses actually hit at 0.286-0.324.
#
# Standalone cross-validated effect: +3.9pp top-pick ITM over 259 races
# (p=0.064). Positive on every track with data. See PHASE_6D_ROADMAP.md.
#
# Applied per horse and only where PP data exists. On a live card handed a PP
# file that is every horse; a horse without PP data passes through untouched,
# so the runner degrades exactly to base behaviour rather than failing.
# ─────────────────────────────────────────────────────────────────────────────
RERANK_SHOW_DELTA_PP = 2.0      # show the +/- marker at this many points

_RERANKER = None
_RERANKER_TRIED = False


def get_reranker(path=None):
    """Load the reranker once. Returns None if unavailable, never raises.

    ``load_reranker`` rather than ``pickle.load``: the artifact is written by
    its training script run as ``__main__``, so the class is pickled as
    ``__main__.PPReranker`` and a bare load elsewhere raises AttributeError.
    """
    global _RERANKER, _RERANKER_TRIED
    if _RERANKER_TRIED:
        return _RERANKER
    _RERANKER_TRIED = True
    try:
        from dpv1_pp_reranker_train import load_reranker
        _RERANKER = load_reranker(path) if path else load_reranker()
        log.debug("loaded reranker %s", _RERANKER.version)
    except Exception as exc:  # noqa: BLE001 - picks must survive a bad artifact
        log.warning("PP reranker unavailable (%s); using base model only", exc)
        _RERANKER = None
    return _RERANKER


def pp_rows_for_race(db, track: str, date: str, race_num: int) -> dict:
    """``normalised program number -> pp_entries_raw row`` for one race."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT program_num, pp_career_starts, pp_days_off, pp_races_in_60d,
                   pp_running_style, pp_best_speed
            FROM pp_entries_raw
            WHERE track = ? AND race_date = ? AND race_num = ?
            """, (track.upper(), date, int(race_num))).fetchall()
    except sqlite3.OperationalError as exc:
        log.warning("pp_entries_raw not readable (%s)", exc)
        return {}
    finally:
        conn.close()
    return {_norm_pgm(r["program_num"]): dict(r) for r in rows}


def _norm_pgm(v) -> str:
    return str(v).strip().upper() if v is not None else ""


def rerank_probabilities(card, p_fund, db, track, date, race_num):
    """Adjusted fundamental P(ITM) plus the per-horse logit delta.

    Returns ``(p_adjusted, delta, n_applied)``. Horses with no PP row keep
    their base probability and a delta of NaN, which is what the log records
    as "the reranker had nothing to say about this horse".
    """
    import numpy as _np
    p_fund = _np.asarray(p_fund, dtype=float)
    delta = _np.full(len(p_fund), _np.nan)
    rr = get_reranker()
    if rr is None:
        return p_fund, delta, 0

    pp = pp_rows_for_race(db, track, date, race_num)
    if not pp:
        return p_fund, delta, 0

    programs = [_norm_pgm(p) for p in card.programs()]
    have = [i for i, pg in enumerate(programs) if pg in pp]
    if not have:
        return p_fund, delta, 0

    from dpv1_pp_reranker_train import build_features, logit as _rr_logit
    corpus = (card.frame["career_starts"].to_numpy()
              if "career_starts" in card.frame.columns
              else _np.zeros(len(p_fund)))
    base_logit = _rr_logit(p_fund)

    # Build through the training module's own feature builder so inference and
    # training cannot drift apart.
    sub = pd.DataFrame({
        "corpus_starts": [corpus[i] for i in have],
        "pp_career_starts": [pp[programs[i]]["pp_career_starts"] for i in have],
        "pp_days_off": [pp[programs[i]]["pp_days_off"] for i in have],
        "pp_races_in_60d": [pp[programs[i]]["pp_races_in_60d"] for i in have],
        "pp_running_style": [pp[programs[i]]["pp_running_style"] for i in have],
        "pp_best_speed": [pp[programs[i]]["pp_best_speed"] for i in have],
        "base_logit": [base_logit[i] for i in have],
    })
    X, names = build_features(sub, rr.mode,
                              rr.training_notes.get("style_spec", "explicit-na"),
                              rr.training_notes.get("impute"))
    if list(names) != list(rr.feature_names):
        log.warning("reranker feature mismatch (built %s, expected %s); "
                    "skipping rerank", names, rr.feature_names)
        return p_fund, delta, 0

    adj_logit = rr.adjust_logit(sub["base_logit"].to_numpy(), X.to_numpy())
    out = p_fund.copy()
    for k, i in enumerate(have):
        delta[i] = adj_logit[k] - base_logit[i]
        out[i] = 1.0 / (1.0 + _np.exp(-adj_logit[k]))
    return out, delta, len(have)


# ─────────────────────────────────────────────────────────────────────────────
# Maiden-race variance warning (Phase 6D gap #6, interim warning only).
#
# A maiden race is where the model has least to work with by construction:
# the horses have barely run, so the history block that carries most of DPv1's
# signal is thin or empty for a large share of the field. The damage is not
# confined to the underraced horses either -- pace projection and
# class-of-field are computed across the whole field, so a few blank runners
# degrade the estimate for the experienced horses beside them.
#
# The flag is race-level, because that is the level at which the warning is
# true: it is the race that is a coin flip, not one horse in it.
# ─────────────────────────────────────────────────────────────────────────────
MAIDEN_MIN_CAREER_STARTS = 3
# Share of the field that must be underraced before a maiden race is flagged.
#
# The first version of this rule fired on *any* underraced starter, which
# turned out to be 98.4% of maiden races -- a category label, not a
# discriminator. Keying on the share of the field instead cuts that to 58.4%
# and separates the compound-chaos maiden from the mostly-experienced one.
#
# The comparison is >=, not >, and that is load-bearing rather than incidental:
# CT 2026-08-29 R6 -- the worked compound case in the roadmap, six underraced
# of ten -- sits at exactly 0.60, so a strict > would drop the very race the
# threshold was chosen to catch.
MAIDEN_UNDERRACED_SHARE = 0.60


def underraced_starters(card) -> list[tuple[str, str, int | None]]:
    """``(program, name, career_starts)`` for every horse under the threshold.

    A NULL ``career_starts`` counts as underraced: the feature builder writes
    NULL when it found no history at all, which is the most underraced a horse
    can be, not a missing measurement to be skipped.

    Note this is *corpus* career starts. A shipper with twenty runs at Laurel
    reads as zero here, so this flag and the shipper flag fire together on a
    maiden race full of ship-ins -- correctly, since both describe the same
    blindness, but the count is "starts this model can see", not "starts".
    """
    if "career_starts" not in card.frame.columns:
        return []
    out = []
    for pgm, name, cs in zip(card.frame.get("program_num", []),
                             card.frame.get("horse_name", []),
                             card.frame["career_starts"]):
        if pd.isna(cs) or float(cs) < MAIDEN_MIN_CAREER_STARTS:
            out.append((str(pgm), str(name),
                        None if pd.isna(cs) else int(cs)))
    return out


def is_maiden_race(conditions: dict) -> bool:
    rt = (conditions or {}).get("race_type")
    return bool(rt) and str(rt).strip().upper().startswith("MAIDEN")


def prior_start_counts(db, horse_ids: list[int], before_date: str,
                       tracks: tuple[str, ...] = TRAINING_TRACKS) -> dict[int, int]:
    """Starts each horse has in the corpus strictly before ``before_date``.

    The horse's row for *today's* race is already in ``entries`` when a card is
    loaded for prediction, so the date bound is strict — otherwise every runner
    would show at least one "prior" start, which is the race being predicted.
    """
    if not horse_ids:
        return {}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        qh = ",".join("?" * len(horse_ids))
        qt = ",".join("?" * len(tracks))
        rows = conn.execute(
            f"""
            SELECT e.horse_id, COUNT(*)
            FROM entries e
            JOIN races r      ON r.id  = e.race_id
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id  = rd.track_id
            WHERE e.horse_id IN ({qh})
              AND t.code IN ({qt})
              AND rd.race_date < ?
            GROUP BY e.horse_id
            """, (*horse_ids, *tracks, before_date)).fetchall()
    finally:
        conn.close()
    counts = {int(h): 0 for h in horse_ids}
    counts.update({int(h): int(n) for h, n in rows})
    return counts


def shipper_flags(card, per_horse_cov, db, race_date: str) -> list[bool]:
    """Which horses the model is probably blind to. Aligned to card order.

    Two conditions, both required. Low coverage alone catches first-time
    starters, who are genuinely unknown to everyone and not a model failure.
    No corpus history alone catches horses the feature block still covers well
    through today's-race fields. It is the pair -- thin features *and* no
    history here -- that says the ranking is guessing.
    """
    if "horse_id" not in card.frame.columns:
        log.warning("no horse_id on the card frame; shipper detection skipped")
        return [False] * len(per_horse_cov)
    ids = [int(h) for h in card.frame["horse_id"]]
    counts = prior_start_counts(db, ids, race_date)
    return [bool(cov < SHIPPER_COV_MAX
                 and counts.get(hid, 0) < SHIPPER_MIN_PRIOR_STARTS)
            for hid, cov in zip(ids, per_horse_cov)]




def card_is_scored(db, track: str, date: str) -> tuple[int, int]:
    """``(races with a recorded finish, races on the card)`` for one card.

    A card whose results are loaded has already been predicted, scored and
    folded into the live record. Re-running picks on it produces a *different*
    opinion -- the field is now the post-scratch starter list -- and logging
    that opinion makes it the newest run, which is the one
    ``score_predictions.latest_run_only`` keeps. The earlier, genuine pre-race
    prediction is then silently superseded and the scored record changes.

    This has happened three times, most recently when a verification run on
    CT 2026-08-29 overwrote a scored 3/8 record with a post-scratch re-read.
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT CASE WHEN e.finish_pos IS NOT NULL
                                       THEN r.id END),
                   COUNT(DISTINCT r.id)
            FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id  = rd.track_id
            LEFT JOIN entries e ON e.race_id = r.id
            WHERE t.code = ? AND rd.race_date = ?
            """, (track.upper(), date)).fetchone()
        return (int(row[0] or 0), int(row[1] or 0))
    except sqlite3.OperationalError as exc:
        log.warning("could not check whether %s %s is scored (%s)",
                    track, date, exc)
        return (0, 0)
    finally:
        conn.close()


def race_numbers(db, track: str, date: str) -> list[int]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [int(r[0]) for r in conn.execute(
            """
            SELECT r.race_num FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            WHERE t.code = ? AND rd.race_date = ?
            ORDER BY r.race_num
            """, (track.upper(), date))]
    finally:
        conn.close()


def ml_lookup(pdf, track: str | None) -> dict:
    """``(race_num, normalized name) -> morning line`` for display only."""
    from equibase_pdf_parser import normalize_name
    bundle = pp_index(pdf, track)
    out = {}
    for (rn, nm), h in bundle["index"].items():
        out[(rn, nm)] = (h.get("ml"), h.get("pp_ml_decimal"),
                         h.get("pp_prime_power"))
    return out


def one_race(track: str, date: str, race_num: int, model, db, pp_file,
             ml_map: dict, iters: int, seed: int) -> dict | None:
    from equibase_pdf_parser import normalize_name

    try:
        card = load_race_from_db(model, db, track=track, race_date=date,
                                 race_num=race_num)
    except LookupError as exc:
        log.warning("R%s: %s", race_num, exc)
        return None
    if card.n < 2:
        return None

    # Shipper detection reads coverage *before* the PP bridge fills anything
    # in. The bridge lifts a shipper's coverage substantially -- Outdoor Cat on
    # CT 2026-08-29 goes 46% -> 64% -- which would push the horse back over the
    # threshold and silence the warning on exactly the runs where a reader has
    # the PP open. What the warning is about is what the *corpus* knows, and
    # that is the pre-bridge number.
    base_cov = coverage_report(card, model)["per_horse"]

    if pp_file:
        try:
            apply_to_card(card, pp_file, model)
        except SystemExit as exc:
            log.warning("R%s: PP bridge failed (%s)", race_num, exc)

    pred = predict_card(card, model, use="fundamental")
    base_sim = simulate_prediction(pred, n_iter=iters, seed=seed)
    cov = coverage_report(card, model)

    # PP reranker. The adjustment is applied to the fundamental probability and
    # then pushed back through normalisation and the Harville inversion, so the
    # win probabilities and the simulator stay consistent with the reranked
    # P(ITM) rather than describing a different race.
    p_adj, rr_delta, n_reranked = rerank_probabilities(
        card, pred.p_fund, db, track, date, race_num)
    if n_reranked:
        from dpv1_runtime import Prediction, invert_harville, normalise_itm
        p_norm = normalise_itm(p_adj)
        p_win, info = invert_harville(p_norm)
        pred = Prediction(card=card, p_fund=pred.p_fund, p_market=pred.p_market,
                          p_blend=pred.p_blend, p_used=p_adj,
                          used_name="fundamental+reranker",
                          p_itm_normalised=p_norm, p_win=p_win, inversion=info)
        sim = simulate_prediction(pred, n_iter=iters, seed=seed)
    else:
        sim = base_sim

    names = card.names()
    d = pd.DataFrame({
        "pgm": card.programs(),
        "horse": names,
        "P(ITM)": sim.p_itm(),
        "base": base_sim.p_itm(),
        "P(win)": sim.position_matrix()[:, 0],
        "cov": cov["per_horse"],
    })
    d["_rr_delta"] = rr_delta
    mls, pps = [], []
    for nm in names:
        v = ml_map.get((race_num, normalize_name(nm)), (None, None, None))
        mls.append(v[0] if v[0] and v[0] != "?" else "")
        pps.append(v[2])
    d["ML"] = mls
    d["PrimePwr"] = pps
    # Explainability: what pushes this horse up/down vs the race baseline?
    reasons = compute_reasons(card, model)
    d["_reasons"] = reasons  # list of dicts, aligned to card order
    d["_shipper"] = shipper_flags(card, base_cov, db, date)
    # Kept alongside the displayed post-bridge figure so a reader of the log
    # can see why the flag fired: the PP bridge can lift a shipper well over
    # the threshold, and shipper_flag=true beside cov=64% otherwise reads as
    # a bug rather than as the two different measurements it is.
    d["_corpus_cov"] = base_cov
    if "finish_pos" in card.frame.columns and card.frame["finish_pos"].notna().any():
        d["actual"] = card.frame["finish_pos"].to_numpy()

    d = d.sort_values("P(ITM)", ascending=False).reset_index(drop=True)
    d.insert(0, "rank", np.arange(1, len(d) + 1))

    under = underraced_starters(card)
    under_share = len(under) / card.n if card.n else 0.0
    maiden = (is_maiden_race(card.conditions)
              and under_share >= MAIDEN_UNDERRACED_SHARE)

    return {"race_num": race_num, "n": card.n,
            "conditions": card.conditions, "coverage": cov["overall"],
            "maiden_flag": maiden, "underraced": under,
            "underraced_share": under_share,
            "n_reranked": n_reranked,
            "table": d}


def print_race(r: dict) -> None:
    c = r["conditions"]
    bits = []
    for k in ("race_type", "distance_yards", "surface", "purse"):
        if c.get(k) is not None:
            bits.append(f"{c[k]}" if k != "purse" else f"${c[k]:,}")
    print(f"\n--- Race {r['race_num']}  ({r['n']} horses)  "
          f"{'  '.join(str(b) for b in bits)}")
    if r.get("maiden_flag"):
        print("    ⚠ MAIDEN with underraced horses — high variance, model "
              "recommends handicapping directly")
        print(f"      ({len(r.get('underraced', []))} of {r['n']} = "
              f"{r.get('underraced_share', 0) * 100:.0f}% have under "
              f"{MAIDEN_MIN_CAREER_STARTS} career starts)")
    print(f"    feature coverage {r['coverage'] * 100:.0f}%")

    d = r["table"].copy()
    # "+/-" makes visible WHEN the reranker acted and in WHICH direction, so a
    # reader is never left guessing whether a pick is the base model's opinion
    # or an adjusted one. Blank below the threshold to keep the page quiet.
    shown = (d["P(ITM)"] - d["base"]) * 100
    d["+/-"] = [f"{v:+.1f}" if pd.notna(v) and abs(v) >= RERANK_SHOW_DELTA_PP
                else "" for v in shown]
    d["P(ITM)"] = (d["P(ITM)"] * 100).round(1)
    d["base"] = (d["base"] * 100).round(1)
    d["P(win)"] = (d["P(win)"] * 100).round(1)
    d["cov"] = (d["cov"] * 100).round(0).astype(int)
    if "PrimePwr" in d.columns:
        d["PrimePwr"] = d["PrimePwr"].astype(object).where(
            d["PrimePwr"].notna(), "")
           # We want the pandas table for alignment, but with per-row reasons under
    # each line. Format the table, then interleave.
    display_cols = [c for c in d.columns if not c.startswith("_")]
    table_lines = d[display_cols].to_string(index=False).splitlines()
    header, body = table_lines[0], table_lines[1:]
    print(header)
    for row_line, (_, row) in zip(body, d.iterrows()):
        print(row_line)
        r = row["_reasons"]
        for label, val in r["pos"]:
            print(f"        ↑ {label:<32} {val:+.2f}")
        for label, val in r["neg"]:
            print(f"        ↓ {label:<32} {val:+.2f}")
        if row.get("_shipper"):
            print("        ⚠ SHIPPER — check PP directly, model may be blind "
                  "to prior form")


# -----------------------------------------------------------------------------
# Phase 6E piece 1: prediction logging.
#
# Every --save run appends one row per horse to logs/predictions.jsonl. That
# file is the audit trail the post-race scorer and the health dashboard read,
# so it is append-only: nothing here ever rewrites a row that is already down.
# It is also never fatal. A card that generates picks but fails to log costs us
# one row; a card that crashes because the log volume is full costs an
# afternoon, so every failure below is a warning, not an exception.
# -----------------------------------------------------------------------------


def _jsonable(v):
    """Coerce a numpy/pandas scalar to a plain JSON type.

    NaN and the empty strings the display table uses for "no morning line"
    both become None, so a missing value reads the same way downstream however
    it went missing.
    """
    if v is None:
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if np.isnan(f) else f
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, str):
        return v.strip() or None
    if pd.isna(v):
        return None
    return v


def _round(v, nd: int):
    v = _jsonable(v)
    return None if v is None else round(float(v), nd)


def prediction_rows(results: list[dict], *, track: str, race_date: str,
                    model, model_pkl: str, picks_file: str,
                    generated_at: datetime, stamp: str) -> list[dict]:
    """Build one JSONL row per horse per race for a single --save run.

    ``prediction_id`` carries ``stamp``, so re-running a card produces a
    fresh, non-colliding set of rows rather than shadowing the earlier ones.
    Which run was right is exactly the question the scorer exists to answer.
    Pass a second-resolution stamp: the picks *filename* is stamped to the
    minute and two runs in one minute are routine (re-run one race after a
    scratch), which is fine for a file that gets overwritten and fatal for an
    id that has to stay unique.
    """
    rows: list[dict] = []
    for r in results:
        race_num = int(r["race_num"])
        table = r["table"]
        # Recorded per row so a later analysis can separate reranked picks from
        # base-only ones without having to know when deployment happened.
        reranker_version = (getattr(get_reranker(), "version", None)
                            if r.get("n_reranked") else None)
        n_horses = int(len(table))
        maiden = bool(r.get("maiden_flag"))
        maiden_share = _round(r.get("underraced_share"), 4)
        for _, h in table.iterrows():
            pgm = _jsonable(h.get("pgm"))
            rows.append({
                "prediction_id": (f"{track.upper()}_{race_date}_R{race_num}"
                                  f"_pgm{pgm}_{stamp}"),
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "track": track.upper(),
                "race_date": race_date,
                "race_num": race_num,
                "pgm": pgm,
                "horse_name": _jsonable(h.get("horse")),
                "p_itm": _round(h.get("P(ITM)"), 4),
                "p_win": _round(h.get("P(win)"), 4),
                "coverage": _round(h.get("cov"), 4),
                "race_coverage": _round(r.get("coverage"), 4),
                "ml_odds": _jsonable(h.get("ML")),
                "prime_power": _jsonable(h.get("PrimePwr")),
                "model_version": getattr(model, "version", None),
                "model_pkl": model_pkl,
                "rank": _jsonable(h.get("rank")),
                "n_horses_in_race": n_horses,
                "picks_file": picks_file,
                "base_p_itm": _round(h.get("base"), 4),
                "final_p_itm": _round(h.get("P(ITM)"), 4),
                "reranker_delta": _round(h.get("_rr_delta"), 4),
                "reranker_version": reranker_version,
                "corpus_coverage": _round(h.get("_corpus_cov"), 4),
                "shipper_flag": bool(h.get("_shipper", False)),
                "maiden_flag": maiden,   # race-level, repeated on each row
                "underraced_share": maiden_share,
            })
    return rows


def append_predictions(rows: list[dict], path: Path | None = None) -> int:
    """Append ``rows`` to predictions.jsonl. Returns rows written; never raises."""
    path = Path(path) if path else LOG_DIR / "predictions.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for row in rows:
                print(json.dumps(row, ensure_ascii=False), file=f)
        return len(rows)
    except OSError as exc:
        log.warning("prediction log not written (%s): %s", path, exc)
        return 0


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Top-4 ITM rankings for a card (Phase 6B deliverable).")
    p.add_argument("--track", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--race", type=int, help="one race only")
    p.add_argument("--pp-file", help="Brisnet PP PDF for this card")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--iters", type=int, default=10000)
    p.add_argument("--seed", type=int, default=6001)
    p.add_argument("--save", action="store_true",
                   help="write a timestamped copy of this output")
    p.add_argument("--outdir", default=str(DPV1_DIR / "picks"))
    p.add_argument("--log-file", default=None,
                   help="override logs/predictions.jsonl (--save only); also "
                        "the safe way to re-read an already-scored card")
    p.add_argument("--force", action="store_true",
                   help="log even when the card is already scored, "
                        "overwriting the pre-race prediction of record")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    model = load_model(args.model)
    ml_map = ml_lookup(args.pp_file, args.track) if args.pp_file else {}
    nums = [args.race] if args.race else race_numbers(args.db, args.track,
                                                      args.date)
    if not nums:
        raise SystemExit(f"no races for {args.track.upper()} {args.date}")

    import io
    buf = io.StringIO()

    class Tee:
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)

        def flush(self):
            sys.__stdout__.flush()

    sys.stdout = Tee()
    try:
        print("=" * 72)
        print(f" DPv1 {model.version} — {args.track.upper()} {args.date}")
        print(f" generated {datetime.now():%Y-%m-%d %H:%M}")
        print("=" * 72)
        print(" P(ITM) is the model's own opinion, formed without odds.")
        print(" ML is the morning line, shown for comparison only — it is not "
              "a model input.")
        print(" cov is how much of the 95-feature set was available; low cov "
              "means a")
        print(" near-prior guess, not a real assessment.")
        trained = tuple(model.hyperparameters.get("tracks", ("GP", "CT", "MNR")))
        if args.track.upper() not in trained:
            print(f" NOTE: this model was trained on {'/'.join(trained)}. "
                  f"{args.track.upper()} is outside that set, so the model")
            print("       carries no track coefficient or track-bias figures "
                  "for it.")

        results = []
        for rn in nums:
            r = one_race(args.track, args.date, rn, model, args.db,
                         args.pp_file, ml_map, args.iters, args.seed)
            if r:
                print_race(r)
                results.append(r)

        if len(results) > 1:
            print("\n" + "=" * 72)
            print(" CARD SUMMARY — top pick per race")
            print("=" * 72)
            rows = []
            for r in results:
                t = r["table"].iloc[0]
                rows.append({
                    "R": r["race_num"],
                    "top pick": f"#{t['pgm']} {t['horse'][:20]}",
                    "P(ITM)%": round(t["P(ITM)"] * 100, 1),
                    "ML": t.get("ML", ""),
                    "cov%": round(r["coverage"] * 100),
                })
            print(pd.DataFrame(rows).to_string(index=False))
            lo = [r["race_num"] for r in results if r["coverage"] < 0.6]
            if lo:
                print(f"\n Races with under 60% feature coverage: {lo}. "
                      f"Treat those rankings as weak.")
    finally:
        sys.stdout = sys.__stdout__

    if args.save:
        # Guard the audit trail before writing anything. A scored card's
        # prediction log is a historical record; re-running picks on it and
        # logging the result rewrites that history.
        n_scored, n_races = card_is_scored(args.db, args.track, args.date)
        if n_scored and not args.log_file and not args.force:
            print(f"\nREFUSING to log: {args.track.upper()} {args.date} is "
                  f"already scored ({n_scored} of {n_races} races have "
                  f"finishing positions).")
            print("\n  Re-running picks on a scored card predicts the "
                  "post-scratch field, and logging")
            print("  that would make it the newest run -- superseding the "
                  "genuine pre-race prediction")
            print("  that the live record is built on.")
            print("\n  Two ways forward:")
            print(f"    --log-file <path>   write to a scratch log, leaving "
                  f"the audit trail alone")
            print(f"    --force             acknowledge and update the audit "
                  f"trail anyway")
            return 3

        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now()
        stamp = generated_at.strftime("%Y%m%d-%H%M")
        base = outdir / f"{args.track.upper()}_{args.date}_{stamp}"
        base.with_suffix(".txt").write_text(buf.getvalue(), encoding="utf-8")
        frames = []
        for r in results:
            t = r["table"].copy()
            t.insert(0, "race_num", r["race_num"])
            frames.append(t)
        if frames:
            pd.concat(frames).to_csv(base.with_suffix(".csv"), index=False)
        print(f"\nsaved {base.with_suffix('.txt')}")
        print(f"saved {base.with_suffix('.csv')}")

        # Phase 6E: the machine-readable twin of the card above.
        # Best effort by design -- a logging failure is reported
        # but never costs us the picks we just wrote.
        picks_file = base.with_suffix('.txt')
        try:
            picks_rel = picks_file.relative_to(DPV1_DIR).as_posix()
        except ValueError:
            picks_rel = picks_file.as_posix()
        log_path = Path(args.log_file) if args.log_file else (
            LOG_DIR / 'predictions.jsonl')
        if n_scored and args.force:
            log.warning("--force: %s %s is already scored; this run becomes "
                        "the newest and supersedes the pre-race prediction",
                        args.track.upper(), args.date)
            print("")
            print("WARNING: --force on an already-scored card. This run "
                  "supersedes the pre-race")
            print(f"         prediction for {args.track.upper()} "
                  f"{args.date} in the audit trail.")
        try:
            rows = prediction_rows(
                results, track=args.track, race_date=args.date,
                model=model, model_pkl=Path(args.model).name,
                picks_file=picks_rel, generated_at=generated_at,
                stamp=generated_at.strftime('%Y%m%d-%H%M%S'))
        except Exception as exc:  # noqa: BLE001 -- picks come first
            log.warning('prediction log rows not built: %s', exc)
            rows = []
        n_logged = append_predictions(rows, log_path)
        if n_logged:
            print(f'logged {n_logged} predictions -> {log_path}')
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
