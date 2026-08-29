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

    if pp_file:
        try:
            apply_to_card(card, pp_file, model)
        except SystemExit as exc:
            log.warning("R%s: PP bridge failed (%s)", race_num, exc)

    pred = predict_card(card, model, use="fundamental")
    sim = simulate_prediction(pred, n_iter=iters, seed=seed)
    cov = coverage_report(card, model)

    names = card.names()
    d = pd.DataFrame({
        "pgm": card.programs(),
        "horse": names,
        "P(ITM)": sim.p_itm(),
        "P(win)": sim.position_matrix()[:, 0],
        "cov": cov["per_horse"],
    })
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
    if "finish_pos" in card.frame.columns and card.frame["finish_pos"].notna().any():
        d["actual"] = card.frame["finish_pos"].to_numpy()

    d = d.sort_values("P(ITM)", ascending=False).reset_index(drop=True)
    d.insert(0, "rank", np.arange(1, len(d) + 1))

    return {"race_num": race_num, "n": card.n,
            "conditions": card.conditions, "coverage": cov["overall"],
            "table": d}


def print_race(r: dict) -> None:
    c = r["conditions"]
    bits = []
    for k in ("race_type", "distance_yards", "surface", "purse"):
        if c.get(k) is not None:
            bits.append(f"{c[k]}" if k != "purse" else f"${c[k]:,}")
    print(f"\n--- Race {r['race_num']}  ({r['n']} horses)  "
          f"{'  '.join(str(b) for b in bits)}")
    print(f"    feature coverage {r['coverage'] * 100:.0f}%")

    d = r["table"].copy()
    d["P(ITM)"] = (d["P(ITM)"] * 100).round(1)
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
        n_horses = int(len(table))
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
                   help="override logs/predictions.jsonl (--save only)")
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
