"""Phase 6A: what an exotic ticket pays, fitted to 88,000 real payoffs.

An EV calculation needs two numbers per combination: the probability it comes
in, and the dollars it returns if it does. The first comes from the simulator.
This file supplies the second — and supplies it from data rather than from a
plausible-sounding constant, because the difference turns out to be large.

The mechanism
-------------
Exotic pools are parimutuel. Every dollar bet on a trifecta goes into one pot,
the track removes its takeout, and whatever is left is split among the tickets
holding the winning combination. So the payoff on combination ``c`` is

    payoff(c) = base * (1 - takeout) / share(c)

where ``share(c)`` is the fraction of the pool backing ``c``. Nobody publishes
``share(c)`` — the tote board shows win odds only. But the win odds tell you
what the crowd thinks, and what the crowd thinks is very close to where the
crowd's exotic money goes. So estimate the public's probability of the
combination by running the tote-implied win probabilities through the same
Plackett-Luce chain the simulator uses:

    q(c) = w_i * w_j/(1 - w_i) * w_k/(1 - w_i - w_j) * ...

and treat ``share(c) ≈ q(c)``. That is the standard construction, and if it
were exactly right then ``log(payoff/base) = log(1 - takeout) - log q``: a
straight line in ``-log q`` with slope exactly 1.

What the data says
------------------
It is not exactly right, and the way it fails is systematic. Fitting

    log(payoff / base) = a + b * (-log q)

over every settled exacta, trifecta and superfecta in ``racing_full.db`` gives
slopes well below 1 (roughly 0.78-0.88, tightening as the ticket gets deeper)
with R² from 0.85 to 0.93. A slope under 1 means the crowd's exotic money is
*less* concentrated on likely combinations than its win betting implies: some
of it chases longshot combinations, some is spread across boxes and keys that
cover combinations the bettor has no particular opinion about. Consequently
favourite-heavy combinations pay **more** than the naive formula predicts and
longshot combinations pay **less** — which matters enormously here, since the
whole point of a model is to find combinations it rates differently from the
crowd, and those are exactly the ones the naive formula misprices worst.

A slope under 1 has a second consequence that is easy to miss: it makes the
curve's overall scale depend on how many combinations the race has. Checked
against reality — the mean of ``actual payoff / (n_combos * base)`` over real
races, which is the true return to covering every combination — the two-term
fit came out high in small fields and low in large ones (for superfectas,
0.95 predicted against 0.63 actual in six-horse fields, and 0.45 against 0.57
in eleven-horse fields). So field size enters explicitly:

    log(payoff / base) = a + b * (-log q) + c * log(n_combos)

with ``n_combos = perm(field_size, depth)``. It earns its place: superfecta R²
goes from 0.847 to 0.872 and trifecta from 0.875 to 0.887, and ``c`` comes out
firmly positive (0.26 for superfectas, 0.20 for trifectas).

Worth recording what this correction is *not*. The natural sanity check on a
parimutuel pool is that covering every combination must return exactly
``1 - takeout``, around 0.78. That check is wrong, and assuming it led to
diagnosing a bias that was not there. It holds only when the crowd's exotic
pool shares match the win-odds-implied probabilities, and they demonstrably do
not — that is the whole content of ``b < 1``. Measured directly from real
payoffs, covering every combination returns 0.55-0.70 depending on wager and
field size, comfortably below ``1 - takeout``, because the money is spread
across combinations in a way that penalises anyone forced to buy all of them.
The fit is checked against that measured number, not against the identity.

Fitting per (wager type, track) rather than globally is a further improvement:
the three tracks have different takeout rates and different bettor mixes.

Log space, and the correction it requires
-----------------------------------------
The fit is in logs because payoffs are lognormal-ish and span four orders of
magnitude. But EV needs ``E[payoff]``, and ``exp(E[log payoff])`` is not
``E[payoff]`` — it is systematically too small by roughly ``exp(sigma^2 / 2)``,
which at the fitted residual spread is not a rounding error but a factor of
two or more. This file applies **Duan's smearing estimator**: the mean of
``exp(residual)`` over the fitted sample, multiplied onto the exponentiated
prediction. It is nonparametric, so it does not assume the residuals are
actually normal, which they are not.

    E[payoff | c wins] = base * exp(a) * q(c)^(-b) * n_combos^c * smear

Honest limits
-------------
1. Payoffs are observed only for combinations that *won*. The regression is
   therefore fit on a selected sample. The relationship being modelled is
   mechanical (pool share sets payoff regardless of outcome) so the selection
   is on the outcome rather than on the response given ``q``, but residual
   correlation between "was likelier than q suggests" and "paid less than the
   fit predicts" would bias EV upward. Treat these EVs as optimistic.
2. Your own bet is not in the pool. On a small pool at CT or MNR, a serious
   bet moves the payoff against itself; none of this models that.
3. ``q`` is built from *final* odds. Betting happens before they are final.

Usage
-----
    python scripts_dpv1/payout_model.py fit          # calibrate + write JSON
    python scripts_dpv1/payout_model.py report       # show the fit + validation
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dpv1_runtime import DEFAULT_DB  # noqa: E402

log = logging.getLogger("payout_model")

DPV1_DIR = Path(__file__).resolve().parent
COEF_PATH = DPV1_DIR / "dpv1_payout_model.json"

# Wager names as they appear in exotic_payouts.wager_name, mapped to the
# number of horses that have to be named in order.
WAGER_DEPTH = {
    "Exacta": 2,
    "Perfecta": 2,      # same bet, different track's naming
    "Trifecta": 3,
    "Superfecta": 4,
}

# Minimum rows before a (wager, track) cell gets its own coefficients rather
# than falling back to the pooled all-track fit.
MIN_CELL_ROWS = 400


def n_combos(field_size: int, depth: int) -> int:
    """Number of distinct ordered combinations a race offers for this wager."""
    return int(math.perm(int(field_size), int(depth)))


# ---------------------------------------------------------------------------
# Public probability of an ordered combination
# ---------------------------------------------------------------------------

def pl_combo_prob(w: np.ndarray, combo) -> float:
    """Plackett-Luce probability of an exact ordered finish prefix.

    ``w`` are win probabilities summing to 1; ``combo`` is a tuple of indices
    in finishing order. This is the same chain rule the simulator samples from,
    evaluated in closed form.
    """
    remaining = 1.0
    p = 1.0
    for idx in combo:
        wi = w[idx]
        if remaining <= 1e-12 or wi <= 0:
            return 0.0
        p *= wi / remaining
        remaining -= wi
    return float(p)


def implied_win_probs(odds: np.ndarray) -> np.ndarray:
    """Tote win odds -> normalised implied win probabilities."""
    o = np.asarray(odds, dtype=float)
    raw = 1.0 / (o + 1.0)
    return raw / raw.sum()


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------

@dataclass
class PayoutModel:
    """Fitted log-linear payout curves, keyed by ``(wager, track)``."""

    coefficients: dict          # "Trifecta|CT" -> {a, b, c, smear, n, r2, ...}
    fallback: dict              # "Trifecta" -> same, pooled over tracks
    # "Superfecta" -> {"6": 0.87, ...}: residual field-size correction. The
    # log-linear n_combos term removes most of the field-size drift but not
    # all of it — superfectas in five- and six-horse fields were still coming
    # out 15-27% high after it. Rather than reach for a more elaborate
    # functional form on a curve that is already empirical, this is the
    # measured actual/predicted ratio per field size, applied directly. Each
    # entry rests on hundreds to thousands of races.
    field_adjust: dict = field(default_factory=dict)
    fitted_at: str = ""
    source_rows: int = 0

    # -- lookup ------------------------------------------------------------

    def _spec(self, wager: str, track: str | None) -> dict | None:
        if track:
            hit = self.coefficients.get(f"{wager}|{track}")
            if hit:
                return hit
        return self.fallback.get(wager)

    def expected_payoff(self, wager: str, q: float, base: float,
                        track: str | None = None,
                        field_size: int | None = None) -> float:
        """E[payoff on a ``base``-dollar ticket | this combination wins].

        ``q`` is the public's probability of the combination, from
        ``pl_combo_prob`` on tote-implied win probabilities. ``field_size`` is
        the number of runners; it sets the ``n_combos`` term. Omitting it falls
        back to the cell's median field size, which is a guess — pass it.

        The final division by ``bias`` is a measured correction, not a fudge.
        Smearing fixes the log-to-level conversion on average over the residual
        distribution, but it is still applied to a curve fitted by least
        squares in logs, which does not constrain the mean in levels. Checked
        against the fitting sample, the result came out 2-4% high for every
        wager type. ``bias`` is that ratio, computed per cell at fit time, and
        dividing by it makes the curve mean-unbiased on the data it was fit to.
        Given the selection caveat in the module docstring pushes the same
        direction, erring low here is the right way to be wrong.
        """
        spec = self._spec(wager, track)
        if spec is None:
            raise KeyError(f"no payout curve for {wager!r}")
        q = float(np.clip(q, 1e-9, 1.0))
        n_comb = (n_combos(field_size, WAGER_DEPTH[wager])
                  if field_size else spec["median_n_combos"])
        raw = (base * np.exp(spec["a"]) * q ** (-spec["b"])
               * n_comb ** spec["c"] * spec["smear"])
        adj = 1.0
        if field_size:
            adj = self.field_adjust.get(wager, {}).get(str(int(field_size)), 1.0)
        return float(raw * adj / spec.get("bias", 1.0))

    def in_fitted_range(self, wager: str, q: float,
                        track: str | None = None) -> bool:
        """Is this combination inside the band of ``q`` the curve was fit on?

        Outside it the curve is extrapolating a log-linear form past its
        evidence, which is where it went most wrong in testing (favourite-heavy
        combinations in small fields). ``ticket_ev`` uses this to mark a price
        as unreliable rather than printing it as though it were sound.
        """
        spec = self._spec(wager, track)
        if spec is None:
            return False
        return bool(spec["q_lo"] <= q <= spec["q_hi"])

    def describe(self, wager: str, track: str | None = None) -> str:
        spec = self._spec(wager, track)
        if spec is None:
            return f"{wager}: no curve"
        return (f"{wager}@{spec['track']}: a={spec['a']:+.3f} b={spec['b']:.3f} "
                f"smear={spec['smear']:.2f} R2={spec['r2']:.3f} n={spec['n']}")

    # -- persistence -------------------------------------------------------

    def save(self, path: str | Path = COEF_PATH) -> None:
        Path(path).write_text(json.dumps({
            "fitted_at": self.fitted_at,
            "source_rows": self.source_rows,
            "coefficients": self.coefficients,
            "fallback": self.fallback,
            "field_adjust": self.field_adjust,
        }, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path = COEF_PATH) -> "PayoutModel":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"{p} not found — run:  python scripts_dpv1/payout_model.py fit")
        blob = json.loads(p.read_text(encoding="utf-8"))
        return cls(coefficients=blob["coefficients"], fallback=blob["fallback"],
                   field_adjust=blob.get("field_adjust", {}),
                   fitted_at=blob.get("fitted_at", ""),
                   source_rows=blob.get("source_rows", 0))


def _collect(db: str | Path) -> pd.DataFrame:
    """Join every settled exotic payoff to its race's tote-implied ``q``."""
    conn = sqlite3.connect(str(db))
    try:
        entries = pd.read_sql_query(
            """
            SELECT e.race_id, e.program_num, e.final_odds, t.code AS track
            FROM entries e
            JOIN races r      ON r.id = e.race_id
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            WHERE e.final_odds > 0
            """, conn)
        payouts = pd.read_sql_query(
            """
            SELECT race_id, wager_name, base_amount, winning_numbers,
                   payoff, pool
            FROM exotic_payouts
            WHERE qualifier IS NULL AND payoff > 0 AND base_amount > 0
              AND winning_numbers IS NOT NULL
            """, conn)
    finally:
        conn.close()

    entries["program_num"] = entries["program_num"].astype(str).str.strip().str.upper()
    entries["w"] = 1.0 / (entries["final_odds"] + 1.0)
    entries["w"] = entries["w"] / entries.groupby("race_id")["w"].transform("sum")

    wmap = {(r, p): w for r, p, w in
            zip(entries["race_id"], entries["program_num"], entries["w"])}
    tmap = dict(zip(entries["race_id"], entries["track"]))
    nmap = entries.groupby("race_id").size().to_dict()

    payouts = payouts[payouts["wager_name"].isin(WAGER_DEPTH)].copy()

    rows = []
    for rid, wager, base, nums, pay, pool in payouts.itertuples(index=False):
        depth = WAGER_DEPTH[wager]
        parts = [x.strip().upper() for x in str(nums).split("-")]
        if len(parts) != depth:
            continue
        field = nmap.get(rid, 0)
        if field < depth:
            continue
        remaining, q = 1.0, 1.0
        ok = True
        for prog in parts:
            w = wmap.get((rid, prog))
            if w is None or remaining <= 1e-9:
                ok = False
                break
            q *= w / remaining
            remaining -= w
        if not ok or not (q > 0):
            continue
        rows.append((rid, wager, tmap.get(rid), float(base), float(pay),
                     float(pool) if pool else np.nan, q, int(field),
                     n_combos(field, depth)))

    df = pd.DataFrame(rows, columns=["race_id", "wager", "track", "base",
                                     "payoff", "pool", "q", "field_size",
                                     "n_combos"])
    df["ly"] = np.log(df["payoff"] / df["base"])
    df["nlq"] = -np.log(df["q"])
    df["lnc"] = np.log(df["n_combos"])
    return df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["ly", "nlq", "lnc"])


def _fit_cell(d: pd.DataFrame, wager: str, track: str) -> dict:
    """OLS of ``log(payoff/base)`` on ``-log q`` and ``log n_combos``."""
    X = np.column_stack([np.ones(len(d)), d["nlq"].to_numpy(),
                         d["lnc"].to_numpy()])
    y = d["ly"].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    smear = float(np.mean(np.exp(resid)))
    # Level-space bias of the smeared curve on its own fitting sample. See
    # PayoutModel.expected_payoff for why this is applied rather than reported.
    pred = (d["base"].to_numpy() * np.exp(beta[0])
            * d["q"].to_numpy() ** (-beta[1])
            * d["n_combos"].to_numpy() ** beta[2] * smear)
    bias = float(pred.mean() / d["payoff"].to_numpy().mean())

    return {
        "wager": wager, "track": track,
        "a": float(beta[0]), "b": float(beta[1]), "c": float(beta[2]),
        # Duan smearing: E[exp(resid)], the nonparametric log-to-level fix.
        "smear": smear,
        "bias": bias,
        "resid_sd": float(resid.std(ddof=3)),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "n": int(len(d)),
        # Trust region for in_fitted_range: the central 99% of observed q.
        "q_lo": float(d["q"].quantile(0.005)),
        "q_hi": float(d["q"].quantile(0.995)),
        "median_n_combos": float(d["n_combos"].median()),
        "median_payoff": float(d["payoff"].median()),
        "median_base": float(d["base"].median()),
    }


def fit(db: str | Path = DEFAULT_DB) -> tuple[PayoutModel, pd.DataFrame]:
    data = _collect(db)
    log.info("collected %d settled exotic payoffs with usable odds", len(data))

    coefficients: dict = {}
    fallback: dict = {}
    for wager, dw in data.groupby("wager"):
        fallback[wager] = _fit_cell(dw, wager, "ALL")
        for track, dt in dw.groupby("track"):
            if len(dt) < MIN_CELL_ROWS:
                continue
            coefficients[f"{wager}|{track}"] = _fit_cell(dt, wager, track)

    model = PayoutModel(coefficients=coefficients, fallback=fallback,
                        fitted_at=pd.Timestamp.now("UTC").isoformat(),
                        source_rows=int(len(data)))

    # Second pass: measure what the curve still gets wrong by field size, and
    # store the correction. Done after the main fit because it corrects that
    # fit's output, and only where there is enough data to measure it.
    MIN_FIELD_ROWS = 300
    adjust: dict = {}
    for (wager, fs), g in data.groupby(["wager", "field_size"]):
        if len(g) < MIN_FIELD_ROWS:
            continue
        pred = np.array([
            model.expected_payoff(wager, q, base, track, fs)
            for q, base, track in zip(g["q"], g["base"], g["track"])
        ])
        ratio = float(g["payoff"].to_numpy().mean() / pred.mean())
        adjust.setdefault(wager, {})[str(int(fs))] = ratio
    model.field_adjust = adjust
    log.info("field-size corrections fitted for %s",
             {k: len(v) for k, v in adjust.items()})
    return model, data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(model: PayoutModel, data: pd.DataFrame, n_bins: int = 8
             ) -> pd.DataFrame:
    """Predicted vs realised mean payoff, in bins of public probability.

    The fit is in log space, so a good R² there says little about whether the
    *level* is right — and the level is the only thing EV cares about. This
    checks the thing that matters: inside each band of ``q``, does the mean
    predicted payoff match the mean payoff that actually occurred?
    """
    rows = []
    for wager, dw in data.groupby("wager"):
        d = dw.copy()
        d["pred"] = [
            model.expected_payoff(wager, q, base, track, fs)
            for q, base, track, fs in zip(d["q"], d["base"], d["track"],
                                          d["field_size"])
        ]
        d["bin"] = pd.qcut(d["nlq"], n_bins, duplicates="drop")
        for b, g in d.groupby("bin", observed=True):
            rows.append({
                "wager": wager,
                "q_range": f"{np.exp(-b.right):.5f}-{np.exp(-b.left):.5f}",
                "n": len(g),
                "mean_actual": float(g["payoff"].mean()),
                "mean_pred": float(g["pred"].mean()),
                "ratio": float(g["pred"].mean() / g["payoff"].mean()),
                "median_actual": float(g["payoff"].median()),
            })
    return pd.DataFrame(rows)


def validate_by_field_size(model: PayoutModel, data: pd.DataFrame
                           ) -> pd.DataFrame:
    """Return to covering every combination, predicted vs actually observed.

    This is the check that caught the field-size bias the two-term fit had.
    ``actual`` is the real payoff divided by what it would have cost to cover
    the whole race; ``pred`` is the same with the fitted curve substituted for
    the realised payoff. Both are averaged over races, so they are directly
    comparable, and neither assumes anything about takeout.
    """
    rows = []
    for (wager, fs), g in data.groupby(["wager", "field_size"]):
        if len(g) < 100 or not (5 <= fs <= 14):
            continue
        pred = np.array([
            model.expected_payoff(wager, q, base, track, fs)
            for q, base, track in zip(g["q"], g["base"], g["track"])
        ])
        denom = g["n_combos"].to_numpy() * g["base"].to_numpy()
        rows.append({
            "wager": wager, "field": int(fs), "races": len(g),
            "actual": float((g["payoff"].to_numpy() / denom).mean()),
            "pred": float((pred / denom).mean()),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["ratio"] = df["pred"] / df["actual"]
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("fit", "report"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(DEFAULT_DB))
        s.add_argument("--out", default=str(COEF_PATH))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    model, data = fit(args.db)
    model.save(args.out)
    print(f"wrote {args.out}  ({model.source_rows:,} payoffs)")

    print("\nFitted curves   "
          "log(payoff/base) = a + b * (-log q) + c * log(n_combos)")
    print("b < 1 means the crowd's exotic money is less concentrated than its "
          "win betting implies.\n")
    rows = list(model.fallback.values()) + list(model.coefficients.values())
    t = pd.DataFrame(rows)[["wager", "track", "n", "a", "b", "c", "smear",
                            "bias", "resid_sd", "r2", "median_payoff"]]
    t = t.sort_values(["wager", "track"])
    print(t.round(4).to_string(index=False))

    if args.cmd == "report":
        print("\nValidation 1: predicted vs realised mean payoff, by public "
              "probability band")
        print("ratio = predicted / actual. 1.00 is perfect; the fit is "
              "unbiased if these scatter around 1.\n")
        v = validate(model, data)
        print(v.round(3).to_string(index=False))
        for wager, g in v.groupby("wager"):
            tot_p = (g["mean_pred"] * g["n"]).sum() / g["n"].sum()
            tot_a = (g["mean_actual"] * g["n"]).sum() / g["n"].sum()
            print(f"  {wager:12s} overall predicted mean {tot_p:8.2f} vs "
                  f"actual {tot_a:8.2f}   ratio {tot_p / tot_a:.3f}")

        print("\nValidation 2: return to covering every combination, by field "
              "size")
        print("Measured against real payoffs, so it assumes nothing about "
              "takeout.\n")
        fv = validate_by_field_size(model, data)
        print(fv.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
