"""Phase 6A: the whole pipeline on one race, or a whole card.

    python scripts_dpv1/handicap_card.py --track CT --date 2026-07-25 --race 5
    python scripts_dpv1/handicap_card.py --track CT --date 2026-07-25   # card
    python scripts_dpv1/handicap_card.py --file mycard.json --interactive

Predict, simulate, price the standard tickets, and say which — if any — are
worth anything. This is the front door; ``predict_race``, ``simulate_race`` and
``ticket_ev`` are each usable alone when you want one stage in isolation.

Reading the output
------------------
The **value table** is the part worth looking at, and it is deliberately built
from the fundamental model rather than the blend. Both are shown per horse:

    fund    what the horses say, independent of the tote
    mkt     what the tote says, as Harville P(ITM)
    edge    fund / mkt

``edge`` above 1 means the model likes a horse more than the crowd does. That
disagreement is the only thing in this toolkit that can produce a bet worth
making — the blended number is 77% market by fitted weight and so mostly
agrees with the price by construction.

Treat a large edge as a question rather than an answer. The fundamental model
is worse than the blend at predicting who finishes in the money; that is what
the blend weights mean. Its value is not accuracy, it is independence. A horse
at ``edge 1.6`` is one where an independent estimate disagrees with the price,
and the useful next step is to find out why — not to bet it because a number
was large.

Negative EV is the expected outcome
-----------------------------------
Nearly every ticket will price negative, and the tool says so rather than
hunting for something to recommend. Covering every combination in a race
returns 55-70 cents on the dollar (measured, see ``payout_model``), so a
positive number requires a real disagreement with the crowd, of a size that
clears that drag. When nothing clears it, the correct output is "nothing here",
and a handicapping tool that never prints that is not measuring anything.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dpv1_runtime import (  # noqa: E402
    Prediction, load_model, load_race_from_db, predict_card, coverage_report,
)
from payout_model import PayoutModel  # noqa: E402
from predict_race import add_source_args, build_card  # noqa: E402
from simulate_race import (  # noqa: E402
    DEFAULT_ITERS, Simulation, check_against_harville, simulate_prediction,
)
from ticket_ev import (  # noqa: E402
    TicketEV, add_ticket_args, build_tickets, evaluate, results_frame,
    validation_warning,
)

log = logging.getLogger("handicap_card")

# A model/market disagreement below this is noise, not a signal.
EDGE_FLAG = 1.25
LONGSHOT_ODDS = 8.0


# ---------------------------------------------------------------------------
# One race
# ---------------------------------------------------------------------------

def value_table(pred: Prediction, sim: Simulation) -> pd.DataFrame:
    """Per-horse model vs market, with the simulated finish distribution."""
    card = pred.card
    pm = sim.position_matrix()
    d = pd.DataFrame({
        "pgm": card.programs(),
        "horse": [n[:20] for n in card.names()],
        "fund": pred.p_fund,
        "P(win)": pm[:, 0],
        "P(ITM)": sim.p_itm(),
    })
    if pred.p_market is not None:
        d.insert(3, "mkt", pred.p_market)
        d.insert(4, "edge", pred.p_fund / np.clip(pred.p_market, 1e-9, None))
    if card.odds is not None:
        d["odds"] = card.odds
    if "finish_pos" in card.frame.columns and card.frame["finish_pos"].notna().any():
        d["actual"] = card.frame["finish_pos"].to_numpy()
    return d.sort_values("P(win)", ascending=False)


def print_value_table(d: pd.DataFrame) -> None:
    disp = d.copy()
    for c in ("fund", "mkt", "P(win)", "P(ITM)"):
        if c in disp.columns:
            disp[c] = (disp[c] * 100).round(1)
    if "edge" in disp.columns:
        disp["edge"] = disp["edge"].round(2)
    if "actual" in disp.columns:
        disp["actual"] = disp["actual"].astype("Int64")
    print(disp.to_string(index=False))


def flag_value_horses(pred: Prediction, d: pd.DataFrame) -> list[str]:
    """Horses the model rates well above the crowd."""
    if "edge" not in d.columns:
        return []
    out = []
    for _, r in d.iterrows():
        if r["edge"] < EDGE_FLAG:
            continue
        odds = r.get("odds", float("nan"))
        tag = " (longshot)" if np.isfinite(odds) and odds >= LONGSHOT_ODDS else ""
        out.append(
            f"#{r['pgm']} {r['horse']}: model {r['fund'] * 100:.0f}% ITM vs "
            f"market {r['mkt'] * 100:.0f}%  (edge {r['edge']:.2f}x"
            + (f", {odds:.1f}-1" if np.isfinite(odds) else "") + f"){tag}")
    return out


def handicap_one(card, model, payouts, args) -> dict:
    """Score, simulate and price one race. Returns a JSON-able summary."""
    pred = predict_card(card, model, use=args.use)
    sim = simulate_prediction(pred, n_iter=args.iters, seed=args.seed)
    tickets = build_tickets(args, pred, sim)
    results = [evaluate(t, sim, pred, payouts, card.track) for t in tickets]

    cov = coverage_report(card, model)

    print(f"\n{'=' * 78}")
    print(f" {card.label()}   {card.n} horses")
    print(f"{'=' * 78}")
    if card.conditions:
        cond = "  ".join(f"{k}={v}" for k, v in card.conditions.items()
                         if v is not None)
        if cond:
            print(f"  {cond}")
    print(f"  probability source: {pred.used_name}   "
          f"feature coverage: {cov['overall'] * 100:.0f}%   "
          f"simulation: {sim.n_iter:,} runnings")

    if cov["overall"] < 0.5:
        print("  WARNING: under half the feature set is present. Rankings are "
              "indicative;")
        print("           the probabilities and every EV below are not "
              "reliable.")

    if card.n <= 3:
        print("  WARNING: three or fewer runners. Every horse is in the money "
              "by definition, so")
        print("           an ITM model carries no information here and the "
              "win probabilities below")
        print("           are a flat 1/N. Ignore this race.")

    print()
    d = value_table(pred, sim)
    print_value_table(d)

    flags = flag_value_horses(pred, d)
    if flags:
        print(f"\n  Model disagrees with the market (edge >= {EDGE_FLAG}x):")
        for f in flags:
            print(f"    * {f}")

    print()
    f = results_frame(results)
    print(f.round(3).to_string(index=False))

    priced = [r for r in results if r.priced]
    pos = [r for r in priced if r.ev > 0]
    if pos:
        print(f"\n  POSITIVE EV ({len(pos)} of {len(priced)}):")
        for r in sorted(pos, key=lambda r: -r.roi):
            print(f"    + {r.ticket.name:<32} EV {r.ev:+7.2f} on {r.cost:6.2f}"
                  f"   ROI {r.roi * 100:+6.1f}%   half-Kelly "
                  f"{r.kelly * 50:.2f}% of bankroll")
            if r.note:
                print(f"      ! {r.note}")
        print()
        for line in validation_warning(pred.used_name):
            print(line)
        if pred.used_name != "fundamental":
            print(f"      Scored with --use {pred.used_name}, which is built "
                  "partly from the tote board")
            print("      that also sets the payout. Re-check with "
                  "--use fundamental before believing it.")
    elif priced:
        best = max(priced, key=lambda r: r.roi)
        print(f"\n  No positive-EV ticket. Least bad: {best.ticket.name} at "
              f"{best.roi * 100:+.1f}% ROI.")

    unpriced = [r for r in results if not r.priced]
    if unpriced:
        print(f"\n  {len(unpriced)} ticket(s) unpriced: {unpriced[0].note}")

    return {
        "race": card.label(),
        "n_horses": card.n,
        "probability_source": pred.used_name,
        "coverage": cov["overall"],
        "harville_check": check_against_harville(sim),
        "horses": json.loads(d.to_json(orient="records")),
        "value_flags": flags,
        "tickets": json.loads(results_frame(results).to_json(orient="records")),
        "n_positive_ev": len(pos),
    }


# ---------------------------------------------------------------------------
# Whole card
# ---------------------------------------------------------------------------

def race_numbers(db: str | Path, track: str, date: str) -> list[int]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            """
            SELECT r.race_num FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            WHERE t.code = ? AND rd.race_date = ?
            ORDER BY r.race_num
            """, (track.upper(), date)).fetchall()
    finally:
        conn.close()
    return [int(r[0]) for r in rows]


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Predict, simulate and price tickets for a race or a card.")
    add_source_args(p)
    add_ticket_args(p)
    p.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    p.add_argument("--seed", type=int, default=6001)
    p.add_argument("--json", help="write the full card summary here")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    model = load_model(args.model)
    try:
        payouts = PayoutModel.load()
    except FileNotFoundError as exc:
        print(f"note: {exc}")
        print("      tickets will show P(hit) but no EV.\n")
        payouts = None

    print(f"DPv1 {model.version}  (trained {model.trained_at[:10]}, "
          f"target {model.hyperparameters['target']})")
    if payouts:
        print(f"payout curves fitted to {payouts.source_rows:,} real payoffs")

    # Whole card: --track and --date with no --race.
    whole_card = (args.track and args.date and not args.race
                  and not args.race_id and not args.file
                  and not args.interactive)

    summaries = []
    if whole_card:
        nums = race_numbers(args.db, args.track, args.date)
        if not nums:
            raise SystemExit(
                f"no races found for {args.track.upper()} {args.date}")
        print(f"\n{args.track.upper()} {args.date}: {len(nums)} races")
        for rn in nums:
            args.race = rn
            try:
                card = build_card(args, model)
                summaries.append(handicap_one(card, model, payouts, args))
            except Exception as exc:                      # noqa: BLE001
                print(f"\n  R{rn}: skipped — {exc}")
    else:
        card = build_card(args, model)
        summaries.append(handicap_one(card, model, payouts, args))

    if len(summaries) > 1:
        print(f"\n{'=' * 78}")
        print(" CARD SUMMARY")
        print("=" * 78)
        rows = []
        for s in summaries:
            best = max((t for t in s["tickets"]
                        if t["ROI%"] is not None and np.isfinite(t["ROI%"])),
                       key=lambda t: t["ROI%"], default=None)
            rows.append({
                "race": s["race"].split()[-1],
                "horses": s["n_horses"],
                "coverage%": round(s["coverage"] * 100),
                "value flags": len(s["value_flags"]),
                "+EV tickets": s["n_positive_ev"],
                "best ROI%": round(best["ROI%"], 1) if best else np.nan,
                "best ticket": best["ticket"] if best else "-",
            })
        print(pd.DataFrame(rows).to_string(index=False))
        tot = sum(s["n_positive_ev"] for s in summaries)
        print(f"\n{tot} positive-EV ticket(s) across {len(summaries)} races.")
        if tot == 0:
            print("Nothing on this card prices as a bet. That is the usual "
                  "and correct answer.")
        else:
            print()
            for line in validation_warning(summaries[0]["probability_source"]):
                print(line)

    if args.json:
        Path(args.json).write_text(json.dumps(summaries, indent=2),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
