"""Phase 6A: expected value of a ticket, given the model and the tote board.

    python scripts_dpv1/ticket_ev.py --track CT --date 2026-07-25 --race 5 \
        --use fundamental --tribox 6,8,9 --trikey "9/6,8/6,8,10"

What an EV number here actually means
-------------------------------------
Every ticket is a set of ordered finishing combinations. For each combination
``c`` in the set there are two numbers:

    p(c)  what the *model* thinks the chance of that exact order is,
          counted from the Monte Carlo simulation
    v(c)  what it would pay, from the parimutuel curve in ``payout_model.py``
          fitted to 99,021 real payoffs

and the whole calculation is

    EV = sum_c p(c) * v(c)  -  cost

The two inputs come from genuinely different places, and that is the only
reason this can ever produce a positive number. ``v(c)`` is built from the tote
board — it is the crowd's opinion, converted into a price. ``p(c)`` is built
from the horses. A ticket is +EV exactly when the model's probability exceeds
the crowd's by more than the takeout, and by no other route.

Which is why ``--use`` matters more than any other flag here. Scored with
``--use blend``, ``p(c)`` is itself 77% market by fitted weight, so it can
hardly ever disagree with ``v(c)`` enough to clear takeout, and essentially
every ticket prices as negative. That is not a bug and it is not pessimism —
it is what betting into a parimutuel pool with the crowd's own opinion is
worth. ``--use fundamental`` is the only setting where a positive EV means
something, because it is the only one where the probability is formed
independently of the price.

Expect most tickets to be negative anyway, and by more than the posted takeout.
Published exotic takeout is 20-25%, but that is the drag on the *pool*, not on
a bettor buying particular combinations. Measured from real payoffs in
``racing_full.db``, covering every combination in a race returns 55-70 cents on
the dollar — worse than takeout alone, because the crowd's money is spread
across combinations in a way that penalises anyone holding all of them. A
ticket has to beat that, not merely beat 25%.

Kelly
-----
Reported as the fraction of bankroll that maximises expected log wealth,
solved numerically against the simulation's own distribution of returns rather
than from the two-outcome textbook formula — a box has many different payoffs,
not one. Two warnings attach to the number:

* It assumes ``p(c)`` is *correct*. Kelly is famously unforgiving about that;
  a fraction computed from an overconfident model overbets badly, and DPv1's
  probabilities on a hand-entered card are not that reliable. The half-Kelly
  column exists because full Kelly on an estimated edge is not the right bet.
* It ignores payout variance. ``v(c)`` is an expectation over a residual
  distribution with a standard deviation of 0.26 in logs for exactas and 0.61
  for superfectas, and treating it as certain understates the risk.

This file reports. It does not recommend, size, or place anything.
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dpv1_runtime import Prediction, load_model, predict_card  # noqa: E402
from payout_model import PayoutModel, implied_win_probs, pl_combo_prob  # noqa: E402
from predict_race import add_source_args, build_card  # noqa: E402
from simulate_race import DEFAULT_ITERS, Simulation, simulate_prediction  # noqa: E402

log = logging.getLogger("ticket_ev")

# Base amounts that are actually offered. Used for the default ticket menu.
DEFAULT_BASES = {"WIN": 2.00, "Exacta": 1.00, "Trifecta": 0.50,
                 "Superfecta": 0.10}

WAGER_DEPTH = {"WIN": 1, "Exacta": 2, "Trifecta": 3, "Superfecta": 4}

VALIDATION_PATH = Path(__file__).resolve().parent / "phase6a_validation.json"


def load_validation() -> dict | None:
    """The measured out-of-sample performance of this file's own EV column.

    Read at runtime rather than hardcoded so that the warning printed next to
    a positive EV always reflects the current backtest. If
    ``validate_phase6a.py`` is re-run after a model change, the caveat updates
    with it; if the numbers ever come out positive, the caveat stops claiming
    otherwise.
    """
    if not VALIDATION_PATH.exists():
        return None
    try:
        return json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def validation_warning(source: str) -> list[str]:
    """Lines describing how this probability source's +EV picks actually did."""
    v = load_validation()
    if not v:
        return ["  This EV column has not been backtested — run "
                "scripts_dpv1/validate_phase6a.py."]
    s = (v.get("sources") or {}).get(source)
    if not s or s.get("real_roi_pct") is None:
        return []
    lo, hi = s.get("real_roi_ci95", [float("nan")] * 2)
    lines = [
        f"  Backtested on {v['n_races']:,} out-of-sample races: tickets this "
        f"tool labelled +EV",
        f"  using --use {source} forecast "
        f"{s['pred_roi_pct']:+.0f}% ROI and actually returned "
        f"{s['real_roi_pct']:+.1f}% (95% CI "
        f"{lo:+.1f}% to {hi:+.1f}%),",
        f"  against {s['all_real_roi_pct']:+.1f}% for betting every ticket "
        f"indiscriminately.",
    ]
    if hi < 0:
        lines.append("  The +EV label did not identify winning tickets. Treat "
                     "it as a measure of")
        lines.append("  model/market disagreement, not as a recommendation.")
    return lines


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

@dataclass
class Ticket:
    """A named set of ordered combinations, and what it costs to cover them."""

    name: str
    wager: str
    base: float
    combos: list[tuple[int, ...]]
    note: str = ""

    @property
    def n_combos(self) -> int:
        return len(self.combos)

    @property
    def cost(self) -> float:
        return self.base * self.n_combos


def _resolve(programs: list[str], spec: str) -> list[int]:
    """Turn '6,8,9' (program numbers) into field indices."""
    idx = {p.strip().upper(): i for i, p in enumerate(programs)}
    out = []
    for tok in spec.split(","):
        t = tok.strip().upper()
        if not t:
            continue
        if t not in idx:
            raise SystemExit(f"program number {t!r} is not in this field "
                             f"({', '.join(programs)})")
        out.append(idx[t])
    if len(set(out)) != len(out):
        raise SystemExit(f"duplicate horse in {spec!r}")
    return out


def win_ticket(programs: list[str], spec: str, base: float) -> Ticket:
    horses = _resolve(programs, spec)
    if len(horses) != 1:
        raise SystemExit("--win takes exactly one program number")
    return Ticket(name=f"WIN #{programs[horses[0]]}", wager="WIN", base=base,
                  combos=[(horses[0],)])


def box(programs: list[str], spec: str, wager: str, base: float) -> Ticket:
    """All orderings of the named horses — the ticket that ignores order."""
    depth = WAGER_DEPTH[wager]
    horses = _resolve(programs, spec)
    if len(horses) < depth:
        raise SystemExit(f"a {wager.lower()} box needs at least {depth} horses, "
                         f"got {len(horses)}")
    combos = list(itertools.permutations(horses, depth))
    return Ticket(name=f"{wager} box {spec}", wager=wager, base=base,
                  combos=combos)


def key(programs: list[str], spec: str, wager: str, base: float) -> Ticket:
    """A positional ticket: ``"9/6,8/6,8,10"`` = 9 first, 6-8 second, ...

    Each slash-separated group lists the horses allowed in that finishing
    position. Combinations reusing a horse are dropped, which is what makes
    ``"9/6,8/6,8,10"`` cost 4 rather than 6.
    """
    depth = WAGER_DEPTH[wager]
    groups = [g for g in spec.split("/")]
    if len(groups) != depth:
        raise SystemExit(
            f"a {wager.lower()} key needs {depth} groups separated by '/', "
            f"got {len(groups)} in {spec!r}")
    slots = [_resolve(programs, g) for g in groups]
    combos = [c for c in itertools.product(*slots) if len(set(c)) == depth]
    if not combos:
        raise SystemExit(f"{spec!r} produces no valid combinations")
    return Ticket(name=f"{wager} key {spec}", wager=wager, base=base,
                  combos=combos)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass
class TicketEV:
    ticket: Ticket
    p_hit: float
    p_hit_se: float
    ev_gross: float
    cost: float
    priced: bool
    detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    kelly: float = 0.0
    note: str = ""

    @property
    def ev(self) -> float:
        return self.ev_gross - self.cost

    @property
    def roi(self) -> float:
        return self.ev / self.cost if self.cost else float("nan")

    @property
    def mean_payout_if_hit(self) -> float:
        return self.ev_gross / self.p_hit if self.p_hit > 0 else float("nan")


def _combo_probs(sim: Simulation, combos: list[tuple[int, ...]]) -> np.ndarray:
    """Simulated probability of each combination, in one pass.

    Encodes both the sampled orders and the requested combinations into the
    same base-``n`` integer, then counts. Avoids an O(iterations x combos)
    comparison, which for a superfecta box against 10,000 runnings would be
    240,000 tuple tests per ticket.
    """
    depth = len(combos[0])
    keys = sim.key(depth)
    want = np.fromiter((Simulation.encode(c, sim.n) for c in combos),
                       dtype=np.int64, count=len(combos))
    uniq, counts = np.unique(keys, return_counts=True)
    pos = np.searchsorted(uniq, want)
    pos = np.clip(pos, 0, len(uniq) - 1)
    hit = uniq[pos] == want
    return np.where(hit, counts[pos], 0) / sim.n_iter


def _kelly_fraction(returns: np.ndarray, probs: np.ndarray) -> float:
    """Bankroll fraction maximising E[log wealth] for a discrete bet.

    ``returns`` is gross return per dollar staked for each outcome (0 for a
    loss); ``probs`` are the matching probabilities, summing to at most 1 with
    the remainder being the total loss outcome. Solved by golden-section search
    on [0, 1] rather than in closed form, because a box has as many distinct
    payoffs as it has combinations.
    """
    p_lose = max(0.0, 1.0 - probs.sum())
    r = np.concatenate([returns, [0.0]])
    p = np.concatenate([probs, [p_lose]])
    keep = p > 0
    r, p = r[keep], p[keep]

    if (r * p).sum() <= 1.0:      # not +EV, so no stake is optimal
        return 0.0

    def growth(f: float) -> float:
        w = 1.0 + f * (r - 1.0)
        if np.any(w <= 1e-12):
            return -np.inf
        return float(np.sum(p * np.log(w)))

    lo, hi = 0.0, 0.999
    phi = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = growth(a), growth(b)
    for _ in range(200):
        if fa < fb:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = growth(b)
        else:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = growth(a)
        if hi - lo < 1e-9:
            break
    return float(max(0.0, 0.5 * (lo + hi)))


def evaluate(ticket: Ticket, sim: Simulation, pred: Prediction,
             payouts: PayoutModel | None, track: str | None) -> TicketEV:
    """Price one ticket against the simulation and the tote board."""
    p = _combo_probs(sim, ticket.combos)
    p_hit = float(p.sum())
    se = float(np.sqrt(max(p_hit * (1 - p_hit), 0.0) / sim.n_iter))

    odds = pred.card.odds
    programs = pred.card.programs()

    rows = []
    priced = True
    note = ""

    if ticket.wager == "WIN":
        # A win bet needs no payout model: the tote publishes the price.
        if odds is None:
            priced = False
            note = "no odds on this card, so a win price cannot be computed"
            payoff = np.full(len(ticket.combos), np.nan)
        else:
            payoff = np.array([ticket.base * (odds[c[0]] + 1.0)
                               for c in ticket.combos])
    elif payouts is None or odds is None:
        priced = False
        note = ("no odds on this card" if odds is None
                else "no fitted payout model")
        payoff = np.full(len(ticket.combos), np.nan)
    else:
        w_pub = implied_win_probs(odds)
        field_size = pred.card.n
        q_pub = np.array([pl_combo_prob(w_pub, c) for c in ticket.combos])
        payoff = np.array([
            payouts.expected_payoff(ticket.wager, q, ticket.base, track,
                                    field_size)
            for q in q_pub
        ])
        # Flag combinations whose public probability sits outside the band the
        # curve was fitted over. Weighted by model probability, because one
        # extrapolated combination that the model gives no chance to does not
        # make the ticket's price unreliable.
        outside = np.array([
            not payouts.in_fitted_range(ticket.wager, q, track)
            for q in q_pub
        ])
        w_outside = float(p[outside].sum() / p.sum()) if p.sum() > 0 else 0.0
        if w_outside > 0.10:
            note = (f"{w_outside * 100:.0f}% of this ticket's probability sits "
                    f"outside the payout curve's fitted range — price is an "
                    f"extrapolation")

    for c, pc, vc in zip(ticket.combos, p, payoff):
        rows.append({
            "combo": "-".join(programs[i] for i in c),
            "p_model": pc,
            "payout": vc,
            "contrib": pc * vc if priced else np.nan,
        })
    detail = pd.DataFrame(rows).sort_values("p_model", ascending=False)

    ev_gross = float(np.nansum(p * payoff)) if priced else float("nan")

    kelly = 0.0
    if priced and ticket.cost > 0:
        kelly = _kelly_fraction(payoff / ticket.cost, p)

    return TicketEV(ticket=ticket, p_hit=p_hit, p_hit_se=se,
                    ev_gross=ev_gross, cost=ticket.cost, priced=priced,
                    detail=detail, kelly=kelly, note=note)


# ---------------------------------------------------------------------------
# Default menu
# ---------------------------------------------------------------------------

def default_menu(pred: Prediction, sim: Simulation,
                 bases: dict | None = None) -> list[Ticket]:
    """The tickets a handicapper would look at, built from the model's own top
    picks: win on the top horse, exacta box of the top 2 and top 3, trifecta
    box of the top 3 and 4, trifecta key off the top pick, superfecta box of
    the top 4.

    These are the model's *preferred* tickets, so their EV is the optimistic
    end of the range rather than a representative sample of what is available.
    """
    bases = bases or DEFAULT_BASES
    programs = pred.card.programs()
    rank = np.argsort(-sim.position_matrix()[:, 0])
    top = [programs[i] for i in rank]
    n = len(top)
    out: list[Ticket] = []

    def spec(k: int) -> str:
        return ",".join(top[:k])

    out.append(win_ticket(programs, top[0], bases["WIN"]))
    if n >= 2:
        out.append(box(programs, spec(2), "Exacta", bases["Exacta"]))
    if n >= 3:
        out.append(box(programs, spec(3), "Exacta", bases["Exacta"]))
        out.append(box(programs, spec(3), "Trifecta", bases["Trifecta"]))
    if n >= 4:
        out.append(box(programs, spec(4), "Trifecta", bases["Trifecta"]))
        # Standard "key" shape: top pick on top, the next three underneath in
        # either order.
        others = ",".join(top[1:4])
        out.append(key(programs, f"{top[0]}/{others}/{others}", "Trifecta",
                       bases["Trifecta"]))
        out.append(box(programs, spec(4), "Superfecta", bases["Superfecta"]))
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def results_frame(results: list[TicketEV]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "ticket": r.ticket.name,
            "combos": r.ticket.n_combos,
            "cost": r.cost,
            "P(hit)%": r.p_hit * 100,
            "+/-": r.p_hit_se * 100,
            "avg pay": r.mean_payout_if_hit if r.priced else np.nan,
            "E[return]": r.ev_gross if r.priced else np.nan,
            "EV": r.ev if r.priced else np.nan,
            "ROI%": r.roi * 100 if r.priced else np.nan,
            "Kelly%": r.kelly * 100 if r.priced else np.nan,
            "half-K%": r.kelly * 50 if r.priced else np.nan,
        })
    return pd.DataFrame(rows)


def print_results(results: list[TicketEV], pred: Prediction) -> None:
    f = results_frame(results)
    print("\nTicket evaluation")
    print(f.round(3).to_string(index=False))

    unpriced = [r for r in results if not r.priced]
    if unpriced:
        print(f"\n{len(unpriced)} ticket(s) could not be priced: "
              f"{unpriced[0].note}. P(hit) is still valid.")

    flagged = [r for r in results if r.priced and r.note]
    for r in flagged:
        print(f"\n  ! {r.ticket.name}: {r.note}")

    priced = [r for r in results if r.priced]
    pos = [r for r in priced if r.ev > 0]
    print()
    if pos:
        print(f"{len(pos)} of {len(priced)} tickets price positive:")
        for r in sorted(pos, key=lambda r: -r.roi):
            print(f"  + {r.ticket.name:<34} EV {r.ev:+7.2f} on "
                  f"{r.cost:6.2f}   ROI {r.roi * 100:+6.1f}%   "
                  f"Kelly {r.kelly * 100:.2f}% (half {r.kelly * 50:.2f}%)")
        print()
        for line in validation_warning(pred.used_name):
            print(line)
        if pred.used_name != "fundamental":
            print("\n  Also: these were scored with "
                  f"--use {pred.used_name}, which is built partly from the "
                  "same tote")
            print("  board that sets the payout. Re-check with "
                  "--use fundamental.")
    else:
        print("No positive-EV ticket in this set.")
        if priced:
            best = max(priced, key=lambda r: r.roi)
            print(f"  Least bad: {best.ticket.name} at "
                  f"{best.roi * 100:+.1f}% ROI.")
        print("  This is the normal result and not a malfunction. Covering "
              "every combination in")
        print("  a race returns 55-70 cents on the dollar, measured from real "
              "payoffs. A ticket")
        print("  clears only where the model genuinely disagrees with the "
              "crowd — not merely")
        print("  where it likes a horse.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_tickets(args, pred: Prediction, sim: Simulation) -> list[Ticket]:
    programs = pred.card.programs()
    bases = {"WIN": args.win_base, "Exacta": args.exacta_base,
             "Trifecta": args.trifecta_base, "Superfecta": args.superfecta_base}
    tickets: list[Ticket] = []

    for spec in args.win or []:
        tickets.append(win_ticket(programs, spec, bases["WIN"]))
    for spec in args.exabox or []:
        tickets.append(box(programs, spec, "Exacta", bases["Exacta"]))
    for spec in args.exakey or []:
        tickets.append(key(programs, spec, "Exacta", bases["Exacta"]))
    for spec in args.tribox or []:
        tickets.append(box(programs, spec, "Trifecta", bases["Trifecta"]))
    for spec in args.trikey or []:
        tickets.append(key(programs, spec, "Trifecta", bases["Trifecta"]))
    for spec in args.superbox or []:
        tickets.append(box(programs, spec, "Superfecta", bases["Superfecta"]))
    for spec in args.superkey or []:
        tickets.append(key(programs, spec, "Superfecta", bases["Superfecta"]))

    if not tickets:
        tickets = default_menu(pred, sim, bases)
    return tickets


def add_ticket_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group(
        "tickets (repeatable; program numbers, not post positions)")
    g.add_argument("--win", action="append", metavar="P")
    g.add_argument("--exabox", action="append", metavar="P,P[,P]")
    g.add_argument("--exakey", action="append", metavar='"A/B,C"')
    g.add_argument("--tribox", action="append", metavar="P,P,P[,P]")
    g.add_argument("--trikey", action="append", metavar='"A/B,C/B,C,D"')
    g.add_argument("--superbox", action="append", metavar="P,P,P,P")
    g.add_argument("--superkey", action="append", metavar='"A/B,C/B,C,D/..."')
    b = p.add_argument_group("base amounts")
    b.add_argument("--win-base", type=float, default=DEFAULT_BASES["WIN"])
    b.add_argument("--exacta-base", type=float, default=DEFAULT_BASES["Exacta"])
    b.add_argument("--trifecta-base", type=float,
                   default=DEFAULT_BASES["Trifecta"])
    b.add_argument("--superfecta-base", type=float,
                   default=DEFAULT_BASES["Superfecta"])


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Expected value of exotic tickets for one race.")
    add_source_args(p)
    add_ticket_args(p)
    p.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    p.add_argument("--seed", type=int, default=6001)
    p.add_argument("--detail", action="store_true",
                   help="print the per-combination breakdown")
    p.add_argument("--json", help="write results to this path")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    model = load_model(args.model)
    card = build_card(args, model)
    pred = predict_card(card, model, use=args.use)
    sim = simulate_prediction(pred, n_iter=args.iters, seed=args.seed)

    try:
        payouts = PayoutModel.load()
    except FileNotFoundError as exc:
        log.warning("%s", exc)
        payouts = None

    tickets = build_tickets(args, pred, sim)
    results = [evaluate(t, sim, pred, payouts, card.track) for t in tickets]

    print(f"\n{card.label()}  ({card.n} horses)")
    print(f"probability source: {pred.used_name}   "
          f"simulation: {sim.n_iter:,} runnings")
    if payouts:
        print(f"payout curves: fitted to {payouts.source_rows:,} real payoffs "
              f"({payouts.fitted_at[:10]})")
    print_results(results, pred)

    if args.detail:
        for r in results:
            print(f"\n--- {r.ticket.name}  ({r.ticket.n_combos} combos, "
                  f"${r.cost:.2f})")
            d = r.detail.head(12).copy()
            d["p_model"] = (d["p_model"] * 100).round(2)
            print(d.round(2).to_string(index=False))
            if r.ticket.n_combos > 12:
                print(f"    ... {r.ticket.n_combos - 12} more combinations")

    if args.json:
        payload = {
            "race": card.label(),
            "probability_source": pred.used_name,
            "n_iter": sim.n_iter,
            "tickets": json.loads(results_frame(results).to_json(
                orient="records")),
        }
        Path(args.json).write_text(json.dumps(payload, indent=2),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
