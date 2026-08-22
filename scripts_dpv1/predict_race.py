"""Phase 6A: score one race card with the trained DPv1 model.

    python scripts_dpv1/predict_race.py --track CT --date 2026-07-25 --race 5
    python scripts_dpv1/predict_race.py --file card.csv
    python scripts_dpv1/predict_race.py --interactive
    python scripts_dpv1/predict_race.py --template card.csv     # blank to fill

Three ways in, and they are not equally good
--------------------------------------------
**From the database** (``--track/--date/--race`` or ``--race-id``) replays a
race whose features ``feature_builder_dpv1`` already built. All 95 features are
present and are exactly what the model was trained on. This is the only path
that is fully faithful — and, because features exist only after the result
chart is loaded, the only path that cannot be used on a race that has not yet
been run. It is what Phase 6A validates against.

**From a file** (``--file``) reads whatever you can supply and leaves the rest
blank. **Interactively** (``--interactive``) prompts for a curated subset.

The gap between the first path and the other two is the honest limitation of
this tool, and it is worth being concrete about rather than burying. DPv1's 95
features include things like ``trainer_at_surface_winrate_shrunk`` and
``track_dirt_bias_90d`` — Bayesian-shrunk rates computed over the whole prior
corpus. Nobody hand-enters those. A hand-built card realistically supplies the
fifteen or so fields in ``MANUAL_SCHEMA`` below, and the model then scores the
horse as one with eighty blank fields.

That is not the same as the model ignoring them. The preprocessor emits a
``{col}__missing`` indicator per nullable column and the fitted model has real
coefficients on those indicators — ``last_race_finish_pos__missing`` carries
-0.249, among the largest in the model — because in training, blank history
overwhelmingly meant a first-time starter.

How much this costs was measured rather than guessed. Taking 300 real 2026
races with complete features, blanking every column outside ``MANUAL_SCHEMA``
(which leaves 26 of 95 features), and re-scoring:

    Spearman rho vs. the full-feature ranking   0.61 mean, 0.69 median
    top pick unchanged                          44% of races
    within-race P(ITM) spread                   36.7pp -> 20.1pp

So hand entry does two things, and the second is worse than the first. It
compresses the field toward the base rate, as expected. But it also *reorders*
it: the model's top pick survives in fewer than half of races. Sparse entry is
therefore not a degraded version of the real prediction, it is a materially
different one. ``--show-coverage`` prints what you actually supplied.

The practical reading: use the database path when you can. For a live card,
treat hand entry as a way to see the model's reasoning rather than as a source
of probabilities, and do not bet tickets priced off a 25%-coverage card. Making
live use real is a parser problem — feeding DPv1 the same features it trained
on from a Brisnet PP file, which ``brisnet_pp_parser.py`` already extracts —
not a problem this file can solve.

Derived fields
--------------
Some features are arithmetic on things a human does know, so
``derive_features`` fills them rather than making you compute them:
``distance_furlongs`` from yards, ``class_score`` from race type plus claiming
price plus purse (Doug's class ladder, ``dpv1_common.class_score_vec``),
``career_win_pct_shrunk`` / ``career_itm_pct_shrunk`` from raw career counts
using the same priors and shrinkage constant the feature builder used
(k=15, prior win 0.12, prior ITM 0.35), ``last_race_won`` from last finish
position, and ``field_size`` from the number of horses entered.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# dpv1_runtime must be imported first: it puts scripts/ and scripts_v2a/ on
# sys.path as an import side effect, which is what makes the two lines below
# resolvable.
from dpv1_runtime import (  # noqa: E402
    DEFAULT_DB, DEFAULT_MODEL, Prediction, RaceCard, coverage_report,
    load_model, load_race_from_db, load_race_from_file,
    load_race_from_records, predict_card,
)
from bayesian_shrinkage import shrink_rate_vec  # noqa: E402
from dpv1_common import class_score_vec  # noqa: E402

log = logging.getLogger("predict_race")

PRIOR_WIN = 0.12
PRIOR_ITM = 0.35
K_HORSE_CAREER = 15


# ---------------------------------------------------------------------------
# The hand-entry schema
# ---------------------------------------------------------------------------
#
# Chosen by fitted coefficient magnitude (see the top of dpv1.pkl's
# `coefficients`) intersected with "a human reading a program actually knows
# this". Everything here is either a model feature or an input to one.

RACE_FIELDS: list[tuple[str, str, str]] = [
    ("track_code",      "Track code (GP / CT / MNR)", "str"),
    ("surface",         "Surface (Dirt / Turf / AllWeather)", "str"),
    ("track_condition", "Track condition (Fast / Firm / Good / Sloppy / Muddy)", "str"),
    ("race_type",       "Race type (CLAIMING / MAIDENCLAIMING / "
                        "MAIDENSPECIALWEIGHT / ALLOWANCE / STAKES ...)", "str"),
    ("distance_yards",  "Distance in yards (6f=1320, 6.5f=1430, 7f=1540, 1m=1760)", "float"),
    ("purse",           "Purse in dollars", "float"),
    ("claiming_price",  "Claiming price (blank if not a claimer)", "float"),
]

HORSE_FIELDS: list[tuple[str, str, str]] = [
    ("program_num",            "Program number", "str"),
    ("horse_name",             "Horse name", "str"),
    ("post_position",          "Post position", "float"),
    ("final_odds",             "Odds (decimal to 1; morning line is fine; "
                               "blank = no market)", "float"),
    ("career_starts",          "Career starts", "float"),
    ("career_wins",            "Career wins", "float"),
    ("career_itm",             "Career in-the-money finishes", "float"),
    ("last_race_finish_pos",   "Finish position last out", "float"),
    ("last_race_beaten_lengths", "Lengths beaten last out (0 if won)", "float"),
    ("last_race_speed_figure", "Speed figure last out", "float"),
    ("last_race_field_size",   "Field size last out", "float"),
    ("days_since_last_race",   "Days since last race", "float"),
    ("class_change_from_last", "Class move (UP / DOWN / SAME)", "str"),
    ("pace_type_last_race",    "Running style last out (front / stalk / mid / close)", "str"),
    ("weight_lbs",             "Weight carried (lbs)", "float"),
    ("starts_at_track",        "Career starts at this track", "float"),
    ("wins_at_track",          "Career wins at this track", "float"),
]

# Inputs that are not themselves model features — they only feed derivations.
NON_FEATURE_INPUTS = ("career_itm", "horse_name", "program_num")


def derive_features(df: pd.DataFrame, conditions: dict) -> pd.DataFrame:
    """Fill the features that are arithmetic on hand-entered fields.

    Only fills a column when it is absent or entirely blank, so a value pulled
    from the database or supplied explicitly in a file always wins over a
    derivation.
    """
    out = df.copy()

    def blank(col: str) -> bool:
        return col not in out.columns or out[col].isna().all()

    n = len(out)
    if blank("field_size"):
        out["field_size"] = float(n)

    dist = conditions.get("distance_yards")
    if dist is None and "distance_yards" in out.columns:
        dist = out["distance_yards"].dropna().iloc[0] if out["distance_yards"].notna().any() else None
    if dist is not None:
        if blank("distance_yards"):
            out["distance_yards"] = float(dist)
        if blank("distance_furlongs"):
            out["distance_furlongs"] = float(dist) / 220.0

    # Doug's class ladder: tier from race type, offset from claiming tag or purse.
    if blank("class_score") and not blank("race_type"):
        out["class_score"] = class_score_vec(
            out["race_type"].astype("object"),
            (out["claiming_price"] if "claiming_price" in out.columns
             else pd.Series(np.nan, index=out.index)).astype("float64"),
            (out["purse"] if "purse" in out.columns
             else pd.Series(np.nan, index=out.index)).astype("float64"),
        )

    # Career rates, with the feature builder's priors and k.
    starts = pd.to_numeric(out.get("career_starts"), errors="coerce") \
        if "career_starts" in out.columns else pd.Series(np.nan, index=out.index)
    for num_col, out_col, prior in (("career_wins", "career_win_pct_shrunk", PRIOR_WIN),
                                    ("career_itm", "career_itm_pct_shrunk", PRIOR_ITM)):
        if blank(out_col) and num_col in out.columns and starts.notna().any():
            num = pd.to_numeric(out[num_col], errors="coerce")
            rate = shrink_rate_vec(num.to_numpy(dtype=float),
                                   starts.to_numpy(dtype=float),
                                   prior, K_HORSE_CAREER)
            # Zero prior starts means no evidence about this horse at all, so
            # the builder writes NULL rather than the bare prior. Match that.
            out[out_col] = np.where(starts.to_numpy(dtype=float) == 0, np.nan, rate)

    if blank("last_race_won") and "last_race_finish_pos" in out.columns:
        lp = pd.to_numeric(out["last_race_finish_pos"], errors="coerce")
        out["last_race_won"] = np.where(lp.isna(), np.nan, (lp == 1).astype(float))

    if blank("last_race_days_ago") and "days_since_last_race" in out.columns:
        out["last_race_days_ago"] = pd.to_numeric(out["days_since_last_race"],
                                                  errors="coerce")

    if blank("last_race_was_maiden") and "race_type" in out.columns:
        pass  # not derivable from what we ask; left NULL deliberately

    return out


# ---------------------------------------------------------------------------
# Templates and interactive entry
# ---------------------------------------------------------------------------

def write_template(path: str | Path, n_horses: int = 8) -> None:
    """Emit a blank card to fill in — CSV for a spreadsheet, JSON for an editor.

    In practice this is the way to hand-build a card. The interactive prompt is
    fine for a single race you are staring at; a full nine-race program is a
    spreadsheet job.
    """
    path = Path(path)
    horse_cols = [f for f, _, _ in HORSE_FIELDS]
    if path.suffix.lower() == ".json":
        blob = {
            "track": "CT", "race_date": "2026-07-25", "race_num": 1,
            "conditions": {f: None for f, _, _ in RACE_FIELDS},
            "horses": [{c: None for c in horse_cols} for _ in range(n_horses)],
            "_note": ("Blank/null means unknown — the model imputes it and "
                      "flags it as missing. Delete unused horse rows. Any "
                      "column named in model.fund_cols is also accepted."),
        }
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    else:
        cols = [f for f, _, _ in RACE_FIELDS] + horse_cols
        pd.DataFrame([{c: "" for c in cols} for _ in range(n_horses)]).to_csv(
            path, index=False)
    print(f"wrote blank template: {path}")
    print("Race-level columns repeat on every row; horse-level differ per row.")


def _ask(prompt: str, kind: str, default=None):
    raw = input(f"  {prompt}: ").strip()
    if not raw:
        return default
    if kind == "float":
        try:
            return float(raw)
        except ValueError:
            print("    (not a number — left blank)")
            return default
    return raw


def interactive_card(model) -> RaceCard:
    """Prompt for the minimum useful field set. Blank means unknown."""
    print("\nDPv1 interactive race entry")
    print("Press Enter to leave any field blank (the model treats blank as "
          "unknown and flags it).\n")
    print("Race conditions")
    track = _ask("Track code (GP / CT / MNR)", "str", "?")
    race_date = _ask("Race date (YYYY-MM-DD)", "str", "?")
    race_num = _ask("Race number", "float")
    conditions: dict = {"track_code": track}
    for name, prompt, kind in RACE_FIELDS:
        if name == "track_code":
            continue
        v = _ask(prompt, kind)
        if v is not None:
            conditions[name] = v

    n = _ask("\nHow many horses in the field", "float")
    n = int(n) if n else 0
    if n < 2:
        raise SystemExit("need at least 2 horses")

    horses = []
    for i in range(n):
        print(f"\nHorse {i + 1} of {n}")
        rec: dict = {}
        for name, prompt, kind in HORSE_FIELDS:
            v = _ask(prompt, kind)
            if v is not None:
                rec[name] = v
        rec.setdefault("program_num", str(i + 1))
        rec.setdefault("horse_name", f"Horse {i + 1}")
        horses.append(rec)

    return load_race_from_records(
        model, horses, track=str(track), race_date=str(race_date),
        race_num=int(race_num) if race_num else None,
        conditions=conditions, source="interactive entry")


# ---------------------------------------------------------------------------
# Card loading (shared with the other Phase 6A entry points)
# ---------------------------------------------------------------------------

def build_card(args, model) -> RaceCard:
    """Resolve whichever race source the flags name, then derive + backfill."""
    if getattr(args, "interactive", False):
        card = interactive_card(model)
    elif getattr(args, "file", None):
        card = load_race_from_file(model, args.file)
    elif getattr(args, "race_id", None) or (args.track and args.date and args.race):
        card = load_race_from_db(model, args.db, race_id=args.race_id,
                                 track=args.track, race_date=args.date,
                                 race_num=args.race)
    else:
        raise SystemExit(
            "specify a race:\n"
            "  --track CT --date 2026-07-25 --race 5   (from the database)\n"
            "  --race-id 12345                         (from the database)\n"
            "  --file card.csv                         (hand-built)\n"
            "  --interactive                           (prompt)\n"
            "  --template card.csv                     (write a blank one)")

    card.frame = derive_features(card.frame, card.conditions)
    # Derivation can introduce columns the model does not use and can leave
    # model columns absent; re-align so transform() never sees a KeyError.
    for c in model.fund_cols:
        if c not in card.frame.columns:
            card.frame[c] = np.nan

    if getattr(args, "pp_file", None):
        from pp_feature_bridge import apply_to_card
        card.pp_report = apply_to_card(card, args.pp_file, model)
    return card


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_prediction(pred: Prediction, model, *, show_coverage: bool = False,
                     show_features: int = 0) -> None:
    card = pred.card
    print(f"\n{'=' * 78}")
    print(f"{card.label()}   {card.n} horses")
    print(f"source: {card.source}")
    if card.conditions:
        cond = "  ".join(f"{k}={v}" for k, v in card.conditions.items()
                         if v is not None)
        if cond:
            print(f"conditions: {cond}")
    print(f"model: {model.version} (trained {model.trained_at[:10]}, "
          f"target = {model.hyperparameters['target']})")
    print(f"probability source: {pred.used_name}")
    print("=" * 78)

    f = pred.to_frame()
    f = f.sort_values("p_itm", ascending=False)
    disp = pd.DataFrame({
        "pgm": f["program"],
        "horse": f["horse"].str.slice(0, 22),
        "P(ITM)": (f["p_itm"] * 100).round(1),
        "P(win)": (f["p_win"] * 100).round(1),
        "log P(win)": f["log_p_win"].round(3),
    })
    if "p_itm_fund" in f.columns:
        disp.insert(3, "fund", (f["p_itm_fund"] * 100).round(1))
    if "p_itm_market" in f.columns:
        disp.insert(4, "mkt", (f["p_itm_market"] * 100).round(1))
    if "odds" in f.columns and f["odds"].notna().any():
        disp["odds"] = f["odds"]
    if "actual" in f.columns and f["actual"].notna().any():
        disp["actual"] = f["actual"].astype("Int64")
    print()
    print(disp.to_string(index=False))

    if card.n <= 3:
        print("\nWARNING: three or fewer runners. Every horse finishes in the "
              "money, so an ITM")
        print("         model says nothing about this race and P(win) is a "
              "flat 1/N.")

    raw_sum = pred.p_used.sum()
    print(f"\nraw P(ITM) sums to {raw_sum:.3f}; rescaled to 3.000 before "
          f"inverting to win probabilities")
    print(f"Harville inversion residual: {pred.inversion['max_abs_error']:.2e} "
          f"({'converged' if pred.inversion['converged'] else 'DID NOT CONVERGE'})")

    if pred.p_market is not None and pred.p_blend is not None:
        a, b = model.blend.alpha_, model.blend.beta_
        print(f"\nblend weights: alpha={a:.3f} on the fundamental logit, "
              f"beta={b:.3f} on the market logit.")
        print("  The blend is mostly the tote board. It is the more accurate "
              "estimate of the two,")
        print("  and the less useful one for finding a mispriced ticket — "
              "exotic payouts are")
        print("  themselves set by that same tote money. Use "
              "--use fundamental to see where")
        print("  the model actually disagrees with the crowd.")

    if show_coverage:
        cov = coverage_report(card, model)
        print(f"\nfeature coverage: {cov['overall'] * 100:.1f}% of "
              f"{cov['n_features']} features supplied")
        per = np.array(cov["per_horse"])
        print(f"  per horse: min {per.min() * 100:.0f}%  "
              f"median {np.median(per) * 100:.0f}%  max {per.max() * 100:.0f}%")
        if cov["fully_missing"]:
            print(f"  {len(cov['fully_missing'])} features blank for every "
                  f"horse: {', '.join(cov['fully_missing'][:8])}"
                  + (" ..." if len(cov["fully_missing"]) > 8 else ""))
        if card.pp_report:
            r = card.pp_report
            print(f"  PP bridge: {r['matched_to_pp']}/{r['rows']} horses "
                  f"matched to the PP file, {r['total_cells_filled']} "
                  f"feature cells filled")
        if cov["overall"] < 0.5:
            print("  WARNING: under half the feature set is present. Measured "
                  "against full-feature")
            print("           scoring on 300 real races, entry at this level "
                  "keeps only rho=0.61 of")
            print("           the ranking and changes the top pick in 56% of "
                  "races. Read the order as")
            print("           a rough opinion, not a ranking, and do not "
                  "price tickets off it.")

    if show_features:
        cols = [c for c in model.fund_cols if card.frame[c].notna().any()]
        # Order by the model's own coefficient magnitude, so what prints first
        # is what moved the number most.
        weight = {}
        for name, coef in model.coefficients.items():
            base = name.split("__")[0]
            weight[base] = max(weight.get(base, 0.0), abs(coef))
        cols.sort(key=lambda c: -weight.get(c, 0.0))
        cols = cols[:show_features]
        print(f"\nFeature values used (top {len(cols)} by fitted coefficient "
              f"magnitude)")
        t = card.frame[cols].copy()
        t.insert(0, "horse", [n[:16] for n in card.names()])
        t.insert(0, "pgm", card.programs())
        with pd.option_context("display.width", 200, "display.max_columns", 60):
            print(t.to_string(index=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def add_source_args(p: argparse.ArgumentParser) -> None:
    src = p.add_argument_group("race source")
    src.add_argument("--race-id", type=int, help="races.id in racing_full.db")
    src.add_argument("--track", help="track code, e.g. CT / GP / MNR")
    src.add_argument("--date", help="race date, YYYY-MM-DD")
    src.add_argument("--race", type=int, help="race number on the card")
    src.add_argument("--file", help="hand-built card, CSV or JSON")
    src.add_argument("--interactive", action="store_true",
                     help="prompt for the fields interactively")
    src.add_argument("--pp-file", metavar="PDF",
                     help="Brisnet PP PDF; fills feature slots the corpus "
                          "left NULL (Phase 6B). Combine with the database "
                          "path for the highest coverage available.")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--use", default="auto",
                   choices=["auto", "fundamental", "blend", "market"],
                   help="which probability to report and simulate from "
                        "(default: blend when odds present, else fundamental)")


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Score a race card with DPv1.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Three ways in")[0])
    add_source_args(p)
    p.add_argument("--template", metavar="PATH",
                   help="write a blank card template and exit")
    p.add_argument("--template-horses", type=int, default=8)
    p.add_argument("--show-coverage", action="store_true",
                   help="report how much of the feature set was supplied")
    p.add_argument("--show-features", type=int, default=0, metavar="N",
                   help="print the N most influential feature values used")
    p.add_argument("--json", help="write predictions to this path")
    p.add_argument("--csv", help="write predictions to this path")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if args.template:
        write_template(args.template, args.template_horses)
        return 0

    model = load_model(args.model)
    card = build_card(args, model)
    pred = predict_card(card, model, use=args.use)
    print_prediction(pred, model, show_coverage=args.show_coverage,
                     show_features=args.show_features)

    if args.csv:
        pred.to_frame().to_csv(args.csv, index=False)
        print(f"\nwrote {args.csv}")
    if args.json:
        payload = {
            "race": card.label(), "source": card.source,
            "model_version": model.version,
            "probability_source": pred.used_name,
            "raw_p_itm_sum": float(pred.p_used.sum()),
            "inversion": pred.inversion,
            "coverage": coverage_report(card, model),
            "horses": json.loads(pred.to_frame().to_json(orient="records")),
        }
        Path(args.json).write_text(json.dumps(payload, indent=2),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
