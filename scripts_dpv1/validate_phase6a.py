"""Phase 6A validation: do the tickets this toolkit calls +EV actually win?

Everything else in Phase 6A is machinery. This is the test that says whether
the machinery is worth using, and it is the only file here whose result could
reasonably stop Doug from betting.

The design
----------
``dpv1_fold_predictions.csv`` holds 108,386 entries across 14,543 races with
**out-of-sample** predictions — each year's predictions come from a model
trained only on earlier years. So for every one of those races we can run the
full Phase 6A pipeline exactly as a user would (invert P(ITM) to win
probabilities, price the standard ticket menu against the tote board, keep the
ones that price positive) and then look up what the ticket actually returned
from ``exotic_payouts``, which is the real chart payoff.

That closes the loop. Predicted ROI comes from the model and the payout curve;
realised ROI comes from what the track actually paid. If the first is positive
and the second is not, the tool is finding noise, and no amount of internal
consistency elsewhere in the codebase makes up for it.

Three probability sources are backtested, because the interesting question is
comparative:

    fundamental   horses only, independent of the tote
    blend         the shipped model (77% market by fitted weight)
    market        the tote board alone — the control. Selecting tickets with
                  the crowd's own opinion cannot beat the crowd's own prices,
                  so whatever this returns is the baseline that "no edge"
                  looks like. Any real skill has to beat *this*, not zero.

Combination probabilities are computed in closed form rather than by Monte
Carlo. Plackett-Luce has an exact chain-rule expression for an ordered finish,
the simulator samples from precisely that distribution, and over 14,543 races
the sampling noise would otherwise be doing real damage to the estimates. The
agreement between the two is checked directly in ``--check-sim``.

Usage
-----
    python scripts_dpv1/validate_phase6a.py                 # full backtest
    python scripts_dpv1/validate_phase6a.py --races 2000    # quick
    python scripts_dpv1/validate_phase6a.py --check-sim     # MC vs closed form
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dpv1_runtime import (  # noqa: E402
    DEFAULT_DB, invert_harville, normalise_itm,
)
from payout_model import (  # noqa: E402
    PayoutModel, implied_win_probs, pl_combo_prob,
)

log = logging.getLogger("validate_phase6a")

DPV1_DIR = Path(__file__).resolve().parent
FOLD_PREDS = DPV1_DIR / "dpv1_fold_predictions.csv"
OUT_JSON = DPV1_DIR / "phase6a_validation.json"

# MNR's charts call it a Perfecta; it is an exacta.
WAGER_ALIAS = {"Perfecta": "Exacta"}
DEPTH = {"Exacta": 2, "Trifecta": 3, "Superfecta": 4}
BASES = {"Exacta": 1.00, "Trifecta": 0.50, "Superfecta": 0.10}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_races(db: str | Path, max_races: int | None = None) -> tuple[dict, dict]:
    """Out-of-sample predictions per race, plus the real payoffs per race."""
    preds = pd.read_csv(FOLD_PREDS)

    conn = sqlite3.connect(str(db))
    try:
        ent = pd.read_sql_query(
            "SELECT id AS entry_id, program_num FROM entries", conn)
        pay = pd.read_sql_query(
            """
            SELECT race_id, wager_name, base_amount, winning_numbers, payoff
            FROM exotic_payouts
            WHERE qualifier IS NULL AND payoff > 0 AND base_amount > 0
              AND winning_numbers IS NOT NULL
            """, conn)
    finally:
        conn.close()

    preds = preds.merge(ent, on="entry_id", how="left")
    preds["program_num"] = preds["program_num"].astype(str).str.strip().str.upper()
    preds = preds[preds["final_odds"] > 0]

    pay["wager"] = pay["wager_name"].replace(WAGER_ALIAS)
    pay = pay[pay["wager"].isin(DEPTH)]

    payouts: dict = {}
    for rid, g in pay.groupby("race_id"):
        d = {}
        for w, gg in g.groupby("wager"):
            r = gg.iloc[0]
            d[w] = (str(r["winning_numbers"]).strip().upper(),
                    float(r["base_amount"]), float(r["payoff"]))
        payouts[int(rid)] = d

    races: dict = {}
    for rid, g in preds.groupby("race_id"):
        rid = int(rid)
        if rid not in payouts or len(g) < 4:
            continue
        races[rid] = g.reset_index(drop=True)
        if max_races and len(races) >= max_races:
            break
    log.info("%d races with out-of-sample predictions and real payoffs",
             len(races))
    return races, payouts


# ---------------------------------------------------------------------------
# Ticket menu
# ---------------------------------------------------------------------------

def menu(order: list[int]) -> list[tuple[str, str, list[tuple[int, ...]]]]:
    """The same standard tickets ``ticket_ev.default_menu`` builds.

    ``order`` is the field's indices sorted by model win probability, best
    first. Returns ``(name, wager, combos)``.
    """
    out = []
    n = len(order)
    if n >= 2:
        out.append(("Exacta box 2", "Exacta",
                    list(itertools.permutations(order[:2], 2))))
    if n >= 3:
        out.append(("Exacta box 3", "Exacta",
                    list(itertools.permutations(order[:3], 2))))
        out.append(("Trifecta box 3", "Trifecta",
                    list(itertools.permutations(order[:3], 3))))
    if n >= 4:
        out.append(("Trifecta box 4", "Trifecta",
                    list(itertools.permutations(order[:4], 3))))
        key = [c for c in itertools.product(order[:1], order[1:4], order[1:4])
               if len(set(c)) == 3]
        out.append(("Trifecta key 1x3", "Trifecta", key))
        out.append(("Superfecta box 4", "Superfecta",
                    list(itertools.permutations(order[:4], 4))))
    return out


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def backtest(races: dict, payouts: dict, pm: PayoutModel,
             source: str) -> pd.DataFrame:
    """Price and settle every standard ticket in every race."""
    rows = []
    col = {"fundamental": "p_fund", "blend": "y_pred",
           "market": "p_market"}[source]

    for rid, g in races.items():
        n = len(g)
        p_itm = g[col].to_numpy(dtype=float)
        if not np.isfinite(p_itm).all():
            continue
        odds = g["final_odds"].to_numpy(dtype=float)
        programs = list(g["program_num"])
        track = str(g["track"].iloc[0])

        w_model, info = invert_harville(normalise_itm(p_itm))
        if not info["converged"]:
            continue
        w_pub = implied_win_probs(odds)

        order = list(np.argsort(-w_model))
        race_pay = payouts.get(rid, {})

        for name, wager, combos in menu(order):
            if wager not in race_pay:
                continue
            win_nums, act_base, act_payoff = race_pay[wager]
            depth = DEPTH[wager]
            parts = [x.strip().upper() for x in win_nums.split("-")]
            if len(parts) != depth:
                continue
            idx = {p: i for i, p in enumerate(programs)}
            if any(p not in idx for p in parts):
                continue
            actual = tuple(idx[p] for p in parts)

            base = BASES[wager]
            cost = base * len(combos)

            p_hit = 0.0
            ev_gross = 0.0
            for c in combos:
                pc = pl_combo_prob(w_model, c)
                p_hit += pc
                q = pl_combo_prob(w_pub, c)
                ev_gross += pc * pm.expected_payoff(wager, q, base, track, n)

            hit = actual in set(combos)
            # The chart's payoff is quoted on the track's base amount; scale it
            # to the base this ticket was priced at.
            realised = act_payoff * (base / act_base) if hit else 0.0

            rows.append({
                "race_id": rid, "track": track, "field": n,
                "ticket": name, "wager": wager,
                "cost": cost, "p_hit": p_hit,
                "ev_gross": ev_gross, "ev": ev_gross - cost,
                "roi_pred": (ev_gross - cost) / cost,
                "hit": int(hit), "realised": realised,
                "profit": realised - cost,
            })
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Predicted vs realised ROI, split by whether the tool said to bet."""
    rows = []
    for selected in (False, True):
        d = df[df["ev"] > 0] if selected else df
        if d.empty:
            continue
        rows.append({
            "source": label,
            "set": "+EV only" if selected else "all tickets",
            "tickets": len(d),
            "cost": d["cost"].sum(),
            "hit%": 100 * d["hit"].mean(),
            "pred ROI%": 100 * d["ev"].sum() / d["cost"].sum(),
            "REAL ROI%": 100 * d["profit"].sum() / d["cost"].sum(),
        })
    return pd.DataFrame(rows)


def by_ticket(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["ev"] > 0]
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("ticket").agg(
        tickets=("cost", "size"), cost=("cost", "sum"),
        hit_pct=("hit", lambda s: 100 * s.mean()),
        pred_roi=("ev", lambda s: np.nan), )
    g["pred_roi"] = 100 * d.groupby("ticket")["ev"].sum() / d.groupby("ticket")["cost"].sum()
    g["real_roi"] = 100 * d.groupby("ticket")["profit"].sum() / d.groupby("ticket")["cost"].sum()
    return g.reset_index()


def bootstrap_ci(profit: np.ndarray, cost: np.ndarray, n: int = 2000,
                 seed: int = 6001) -> tuple[float, float]:
    """Percentile CI for realised ROI, resampling tickets with replacement.

    Exotic returns are wildly skewed — a handful of superfecta hits carry the
    whole sample — so a naive standard error understates the uncertainty badly.
    """
    rng = np.random.default_rng(seed)
    k = len(profit)
    if k == 0:
        return float("nan"), float("nan")
    out = np.empty(n)
    for i in range(n):
        s = rng.integers(0, k, k)
        out[i] = profit[s].sum() / cost[s].sum()
    return float(np.percentile(out, 2.5) * 100), float(np.percentile(out, 97.5) * 100)


# ---------------------------------------------------------------------------
# Simulator cross-check
# ---------------------------------------------------------------------------

def check_sim(races: dict, n_races: int = 40) -> None:
    """Confirm the Monte Carlo simulator matches the closed-form PL used here."""
    from simulate_race import simulate

    diffs = []
    for rid, g in list(races.items())[:n_races]:
        p_itm = g["p_fund"].to_numpy(dtype=float)
        w, info = invert_harville(normalise_itm(p_itm))
        if not info["converged"]:
            continue
        sim = simulate(w, n_iter=20000, seed=99)
        order = list(np.argsort(-w))
        for _name, _wager, combos in menu(order):
            exact = sum(pl_combo_prob(w, c) for c in combos)
            mc, _se = sim.p_combos(combos)
            diffs.append(abs(mc - exact))
    d = np.array(diffs)
    print(f"Monte Carlo vs closed-form Plackett-Luce over {len(d)} tickets:")
    print(f"  mean |diff| = {d.mean():.5f}   p99 = {np.percentile(d, 99):.5f}"
          f"   max = {d.max():.5f}")
    print("  (20,000 runnings; MC standard error on a p=0.3 ticket is ~0.0032)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--races", type=int, default=None,
                   help="cap the number of races (for a quick run)")
    p.add_argument("--check-sim", action="store_true")
    p.add_argument("--json", default=str(OUT_JSON))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    races, payouts = load_races(args.db, args.races)
    if args.check_sim:
        check_sim(races)
        return 0

    pm = PayoutModel.load()
    report: dict = {"n_races": len(races), "sources": {}}
    summaries, details = [], {}

    for source in ("fundamental", "blend", "market"):
        df = backtest(races, payouts, pm, source)
        details[source] = df
        summaries.append(summarise(df, source))
        sel = df[df["ev"] > 0]
        lo, hi = bootstrap_ci(sel["profit"].to_numpy(), sel["cost"].to_numpy())
        report["sources"][source] = {
            "tickets_all": int(len(df)),
            "tickets_selected": int(len(sel)),
            "selected_cost": float(sel["cost"].sum()),
            "pred_roi_pct": float(100 * sel["ev"].sum() / sel["cost"].sum())
            if len(sel) else None,
            "real_roi_pct": float(100 * sel["profit"].sum() / sel["cost"].sum())
            if len(sel) else None,
            "real_roi_ci95": [lo, hi],
            "all_real_roi_pct": float(100 * df["profit"].sum() / df["cost"].sum()),
        }
        log.info("%s done: %d tickets, %d selected", source, len(df), len(sel))

    print(f"\n{'=' * 78}")
    print(f" PHASE 6A BACKTEST — {len(races):,} out-of-sample races")
    print("=" * 78)
    print("\npred ROI% is what this toolkit forecast. REAL ROI% is what the "
          "track actually paid.\n")
    print(pd.concat(summaries).round(2).to_string(index=False))

    print("\n95% CI on realised ROI of the +EV selections "
          "(bootstrap over tickets):")
    for source, s in report["sources"].items():
        lo, hi = s["real_roi_ci95"]
        print(f"  {source:12s} {s['real_roi_pct']:+7.1f}%   "
              f"[{lo:+.1f}%, {hi:+.1f}%]   on ${s['selected_cost']:,.0f} "
              f"staked over {s['tickets_selected']:,} tickets")

    print("\nBy ticket type, +EV selections only (fundamental):")
    bt = by_ticket(details["fundamental"])
    if not bt.empty:
        print(bt.round(2).to_string(index=False))

    fund = report["sources"]["fundamental"]
    mkt = report["sources"]["market"]
    print(f"\n{'=' * 78}")
    print(" VERDICT")
    print("=" * 78)
    real, pred = fund["real_roi_pct"], fund["pred_roi_pct"]
    lo, hi = fund["real_roi_ci95"]
    print(f"Fundamental-model +EV tickets: forecast {pred:+.1f}% ROI, "
          f"returned {real:+.1f}%.")
    print(f"The control (selecting with the tote board itself) returned "
          f"{mkt['real_roi_pct']:+.1f}%.")
    if hi < 0:
        print("\nThe entire 95% interval is below zero. The +EV label does NOT "
              "identify profitable")
        print("tickets — it identifies places where the model happens to "
              "disagree with the crowd,")
        print("and that disagreement does not pay for itself. Do not bet off "
              "the EV column.")
    elif lo > 0:
        print("\nThe entire 95% interval is above zero on out-of-sample "
              "races. This is a real edge.")
    else:
        print("\nThe interval spans zero: consistent with no edge, and the "
              "sample cannot rule out")
        print("a small one either way. Not a basis for betting.")

    Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
