"""Phase 6A: Monte Carlo race simulator (Plackett-Luce).

Takes the per-horse win probabilities recovered by ``dpv1_runtime`` and turns
them into a distribution over finishing orders, which is the object every
exotic ticket is actually a bet on. A trifecta does not care what P(ITM) is;
it cares about P(this horse first AND that one second AND that one third), and
nothing in the DPv1 artifact answers that question directly.

The model
---------
Plackett-Luce: each horse has a strength ``w_i``; the winner is drawn with
probability proportional to strength, then the runner-up is drawn the same way
from those remaining, and so on. This is the same generative story as the
Harville reduction used to build DPv1's market feature, so the simulator, the
inversion in ``dpv1_runtime`` and the target the model was trained against are
all one model seen from different angles.

Sampling
--------
Not by literal sequential draws — by the **Gumbel-max trick**. Adding i.i.d.
Gumbel(0,1) noise to each ``log w_i`` and sorting descending yields a ranking
distributed exactly Plackett-Luce (Yellott 1977). This is not an approximation
of the sequential procedure; it is the same distribution, and it turns the
whole simulation into one ``argsort`` over an ``(n_iter, n_horses)`` array
rather than a Python loop over four sequential draws per iteration.

Two consequences worth stating plainly. First, 10,000 iterations run in
milliseconds, so there is no reason to economise on them. Second, and less
comfortable: the sampler is exact, which means **every error in the output is
an error in ``w``, not in the simulation.** The Monte Carlo noise is reported
below as a standard error and is generally the smallest source of uncertainty
in anything this tool prints. A P(hit) of 0.4% ± 0.06% is not 0.4% because the
simulator is confident — it is 0.4% because the model says so, and the model's
own calibration error dwarfs the ±0.06%.

What Plackett-Luce does not know
--------------------------------
It has no concept of pace, trip, or the fact that two front-runners in the same
race hurt each other. It assumes each horse's strength is fixed and that
finishing order is a pure sequence of independent draws from it. Real races
have correlations — the speed duel that collapses both leaders and lets a
closer through is a single event that PL models as three unrelated draws. This
is a known limitation of the family and it biases exotic probabilities in ways
that are hard to sign in advance.

Usage
-----
    python scripts_dpv1/simulate_race.py --track CT --date 2026-07-25 --race 5
    python scripts_dpv1/simulate_race.py --race-id 12345 --use fundamental
    python scripts_dpv1/simulate_race.py --file mycard.json --iters 50000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dpv1_runtime import (  # noqa: E402
    DEFAULT_DB, DEFAULT_MODEL, Prediction, RaceCard, harville_itm,
    load_model, load_race_from_db, load_race_from_file, predict_card,
)

log = logging.getLogger("simulate_race")

DEFAULT_ITERS = 10_000
POSITION_NAMES = {1: "WIN", 2: "2nd", 3: "3rd", 4: "4th"}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@dataclass
class Simulation:
    """Result of ``n_iter`` sampled finishing orders.

    ``order`` is ``(n_iter, depth)`` of *horse indices* — row ``t`` is the
    finishing order of iteration ``t``, so ``order[t, 0]`` won that running.
    Everything else here is a summary of it, and ``ticket_ev`` counts against
    ``order`` directly rather than reconstructing probabilities from marginals
    (the marginals do not determine the joint, which is the entire reason this
    file exists).
    """

    order: np.ndarray             # (n_iter, depth) horse indices
    p_win: np.ndarray             # (n,) strengths the sim was driven by
    programs: list[str]
    names: list[str]
    n_iter: int
    seed: int
    depth: int

    @property
    def n(self) -> int:
        return len(self.p_win)

    # -- marginals ----------------------------------------------------------

    def position_matrix(self) -> np.ndarray:
        """``(n, depth)`` array of P(horse i finishes in position k+1)."""
        out = np.zeros((self.n, self.depth))
        for k in range(self.depth):
            counts = np.bincount(self.order[:, k], minlength=self.n)
            out[:, k] = counts / self.n_iter
        return out

    def p_itm(self) -> np.ndarray:
        """P(top 3). Equals the sum of the first three position marginals."""
        d = min(3, self.depth)
        return self.position_matrix()[:, :d].sum(axis=1)

    def se(self, p: np.ndarray | float) -> np.ndarray | float:
        """Monte Carlo standard error of a simulated probability."""
        p = np.asarray(p, dtype=float)
        return np.sqrt(np.clip(p * (1.0 - p), 0.0, None) / self.n_iter)

    # -- joint queries ------------------------------------------------------

    def key(self, depth: int) -> np.ndarray:
        """Encode each iteration's top-``depth`` order as one integer.

        Base-``n`` positional encoding. Lets ``ticket_ev`` test membership of a
        whole ticket with a single vectorised ``np.isin`` instead of comparing
        tuples row by row.
        """
        if depth > self.depth:
            raise ValueError(
                f"simulation only retained {self.depth} positions, "
                f"asked for {depth}")
        k = np.zeros(self.n_iter, dtype=np.int64)
        for j in range(depth):
            k = k * self.n + self.order[:, j]
        return k

    @staticmethod
    def encode(combo, n: int) -> int:
        k = 0
        for idx in combo:
            k = k * n + int(idx)
        return k

    def p_combos(self, combos: list[tuple[int, ...]]) -> tuple[float, float]:
        """P(the finish matches any ordered combo in ``combos``), plus its SE."""
        if not combos:
            return 0.0, 0.0
        depth = len(combos[0])
        if any(len(c) != depth for c in combos):
            raise ValueError("all combos in one query must be the same length")
        want = np.fromiter((self.encode(c, self.n) for c in combos),
                           dtype=np.int64, count=len(combos))
        hit = np.isin(self.key(depth), want)
        p = float(hit.mean())
        return p, float(np.sqrt(max(p * (1 - p), 0.0) / self.n_iter))

    # -- reporting ----------------------------------------------------------

    def frame(self) -> pd.DataFrame:
        pm = self.position_matrix()
        d = {"program": self.programs, "horse": self.names,
             "p_win_model": self.p_win}
        for k in range(self.depth):
            d[f"p_{POSITION_NAMES.get(k + 1, f'{k+1}th')}"] = pm[:, k]
        d["p_ITM"] = self.p_itm()
        return pd.DataFrame(d)

    def position_owners(self) -> pd.DataFrame:
        """Most likely occupant of each finishing position, and how sure.

        "Confidence" here is just the winning marginal — P(the most likely
        horse actually lands in that slot). It is normally low, and that is the
        correct answer rather than a defect: in a competitive nine-horse field
        no horse owns third place with any authority, and a tool that implied
        otherwise would be lying. The margin over the runner-up is reported
        alongside because a 22%-vs-21% call and a 22%-vs-9% call are different
        situations that the same 22% would otherwise hide.
        """
        pm = self.position_matrix()
        rows = []
        for k in range(self.depth):
            col = pm[:, k]
            order = np.argsort(-col)
            i, j = order[0], order[1] if self.n > 1 else order[0]
            rows.append({
                "position": POSITION_NAMES.get(k + 1, f"{k+1}th"),
                "most_likely": f"#{self.programs[i]} {self.names[i]}",
                "confidence": float(col[i]),
                "runner_up": f"#{self.programs[j]} {self.names[j]}",
                "runner_up_p": float(col[j]),
                "margin": float(col[i] - col[j]),
            })
        return pd.DataFrame(rows)


def simulate(p_win: np.ndarray, n_iter: int = DEFAULT_ITERS,
             seed: int = 6001, depth: int = 4, *,
             programs: list[str] | None = None,
             names: list[str] | None = None) -> Simulation:
    """Sample ``n_iter`` finishing orders from a Plackett-Luce field.

    ``depth`` is how many finishing positions to retain. Four is the default
    because a superfecta is the deepest ticket this toolkit prices; retaining
    more costs nothing but is never read.
    """
    w = np.asarray(p_win, dtype=float)
    n = len(w)
    if n == 0:
        raise ValueError("empty field")
    if not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("win probabilities must be finite and positive")
    depth = min(depth, n)

    rng = np.random.default_rng(seed)
    logw = np.log(w / w.sum())

    # Gumbel-max: argsort of (log w + Gumbel) is an exact Plackett-Luce draw.
    g = rng.gumbel(size=(n_iter, n))
    order = np.argsort(-(logw[None, :] + g), axis=1)[:, :depth]

    return Simulation(
        order=order.astype(np.int32), p_win=w / w.sum(),
        programs=programs or [str(i + 1) for i in range(n)],
        names=names or [f"#{i + 1}" for i in range(n)],
        n_iter=n_iter, seed=seed, depth=depth,
    )


def simulate_prediction(pred: Prediction, n_iter: int = DEFAULT_ITERS,
                        seed: int = 6001, depth: int = 4) -> Simulation:
    """Simulate straight from a ``Prediction``, carrying names through."""
    return simulate(pred.p_win, n_iter=n_iter, seed=seed, depth=depth,
                    programs=pred.card.programs(), names=pred.card.names())


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------

def check_against_harville(sim: Simulation) -> dict:
    """Compare simulated P(ITM) to the closed-form Harville value.

    These are the same quantity computed two ways, so a disagreement larger
    than Monte Carlo noise means something is wrong with the sampler or the
    strength vector — not with the model. Reported as a ratio to the standard
    error so it reads as "how many sigma off" rather than as a raw number
    whose scale depends on ``n_iter``.
    """
    sim_itm = sim.p_itm()
    exact = harville_itm(sim.p_win)
    se = np.sqrt(np.clip(exact * (1 - exact), 1e-12, None) / sim.n_iter)
    z = (sim_itm - exact) / se
    return {
        "max_abs_diff": float(np.max(np.abs(sim_itm - exact))),
        "max_abs_z": float(np.max(np.abs(z))),
        "mean_abs_diff": float(np.mean(np.abs(sim_itm - exact))),
        "ok": bool(np.max(np.abs(z)) < 5.0),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def add_card_args(p: argparse.ArgumentParser) -> None:
    """Shared race-selection flags, reused by ticket_ev and handicap_card."""
    src = p.add_argument_group("race source")
    src.add_argument("--race-id", type=int, help="races.id in racing_full.db")
    src.add_argument("--track", help="track code, e.g. CT / GP / MNR")
    src.add_argument("--date", help="race date, YYYY-MM-DD")
    src.add_argument("--race", type=int, help="race number on the card")
    src.add_argument("--file", help="race card as CSV or JSON")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--use", default="auto",
                   choices=["auto", "fundamental", "blend", "market"],
                   help="which probability drives the simulation "
                        "(default: blend when odds are present)")


def card_from_args(args, model) -> RaceCard:
    if args.file:
        return load_race_from_file(model, args.file)
    if args.race_id or (args.track and args.date and args.race):
        return load_race_from_db(model, args.db, race_id=args.race_id,
                                 track=args.track, race_date=args.date,
                                 race_num=args.race)
    raise SystemExit(
        "specify a race: --race-id N, or --track CT --date YYYY-MM-DD "
        "--race N, or --file card.json")


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Monte Carlo finish-position probabilities for one race.")
    add_card_args(p)
    p.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    p.add_argument("--seed", type=int, default=6001)
    p.add_argument("--json", help="write the full result to this path")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    model = load_model(args.model)
    card = card_from_args(args, model)
    pred = predict_card(card, model, use=args.use)
    sim = simulate_prediction(pred, n_iter=args.iters, seed=args.seed)

    print(f"\n{card.label()}  ({card.n} horses)   source: {card.source}")
    print(f"probability source: {pred.used_name}   "
          f"iterations: {sim.n_iter:,}   seed: {sim.seed}")

    f = sim.frame()
    if "finish_pos" in card.frame.columns and card.frame["finish_pos"].notna().any():
        f["actual"] = card.frame["finish_pos"].to_numpy()
    pct = [c for c in f.columns if c.startswith("p_")]
    disp = f.copy()
    for c in pct:
        disp[c] = (disp[c] * 100).round(1)
    print("\nFinish-position probabilities (%)")
    print(disp.sort_values("p_WIN", ascending=False).to_string(index=False))

    print("\nPosition ownership")
    po = sim.position_owners()
    po["confidence"] = (po["confidence"] * 100).round(1)
    po["runner_up_p"] = (po["runner_up_p"] * 100).round(1)
    po["margin"] = (po["margin"] * 100).round(1)
    print(po.to_string(index=False))

    chk = check_against_harville(sim)
    print(f"\nsanity: simulated vs closed-form Harville P(ITM) — "
          f"max |diff|={chk['max_abs_diff']:.4f} "
          f"({chk['max_abs_z']:.1f} sigma) "
          f"{'OK' if chk['ok'] else 'MISMATCH'}")

    if args.json:
        payload = {
            "race": card.label(), "source": card.source,
            "probability_source": pred.used_name,
            "n_iter": sim.n_iter, "seed": sim.seed,
            "horses": sim.frame().to_dict(orient="records"),
            "position_owners": sim.position_owners().to_dict(orient="records"),
            "harville_check": chk,
        }
        Path(args.json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
