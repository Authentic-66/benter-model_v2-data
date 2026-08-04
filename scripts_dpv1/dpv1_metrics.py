"""Metric suite for DPv1 — per-track by construction.

Phase 4C's whole question is whether DPv1 behaves differently on the GP
(efficient) market than on the CT/MNR bullring circuit, so every metric here
takes a slice mask and the driver evaluates each one on GP / CT / MNR /
CT+MNR / overall.

The headline diagnostic
-----------------------
``corr_logit_pf_pm`` — Pearson correlation between ``logit(p_fundamental)``
and ``logit(p_market)``. Phase 4B.1 introduced it after it explained, in one
number, something log-loss could not show at all: repairing the feature
alignment bug made the fundamental model *better* standalone (log-loss 1.9224
→ 1.8653) while making it far more collinear with the market (0.537 → 0.697).
A model whose fundamental correlates ~1.0 with the price has no independent
view, however good its log-loss looks. DPv1's ship criteria include
``corr < 0.60`` on CT+MNR for exactly that reason.

Wagering payouts
----------------
``exotic_payouts`` rows are *per winning combination*, and a dead heat
produces more than one winning combination for the same race (23% of
trifecta races carry two rows — e.g. race 16538 pays ``2-6-7`` at $85.00 and
``6-2-7`` at $50.70). Mountaineer additionally double-records its Perfecta
rows verbatim, so exact duplicates are dropped first.

Payoffs are normalised to a per-$1 basis because the base stake differs by
track and wager (trifecta is $1 at CT/MNR but $0.50 at GP; superfecta $1 or
$0.10). Where a race still has several distinct winning combinations we
report ROI three ways — using the min, mean and max payoff — so no conclusion
rests on which one you pick.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

EPS = 1e-12

# Mountaineer charts the exacta under the name "Perfecta".
WAGER_ALIASES = {"Exacta": ("Exacta", "Perfecta")}


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p) - np.log(1 - p)


# ---------------------------------------------------------------------------
# Statistical metrics
# ---------------------------------------------------------------------------

def binary_log_loss(y: np.ndarray, p: np.ndarray) -> float:
    """Per-entry binary cross-entropy — the natural loss for the ITM target.

    Note this is NOT comparable to the ``log_loss_per_race`` figure quoted in
    Phase 3E/3F/3G: that metric assumes per-race softmax normalisation and is
    inflated when applied to per-entry sigmoids (Phase 3G flagged this).
    """
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    y = np.asarray(y, dtype=float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    return float(((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2).mean())


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def corr_logit(p_f: np.ndarray, p_m: np.ndarray) -> float:
    """The Phase 4B.1 diagnostic. NaN-safe."""
    lf, lm = _logit(p_f), _logit(p_m)
    ok = np.isfinite(lf) & np.isfinite(lm)
    if ok.sum() < 3 or lf[ok].std() == 0 or lm[ok].std() == 0:
        return float("nan")
    return float(np.corrcoef(lf[ok], lm[ok])[0, 1])


def calibration_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        rows.append({"bin": b, "lo": edges[b], "hi": edges[b + 1],
                     "n": int(m.sum()),
                     "avg_pred": float(p[m].mean()) if m.any() else np.nan,
                     "observed": float(y[m].mean()) if m.any() else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ITM selection metrics
# ---------------------------------------------------------------------------

def _rank_within_race(df: pd.DataFrame, col: str = "y_pred") -> pd.Series:
    return df.groupby("race_id")[col].rank(ascending=False, method="first")


def itm_selection_metrics(df: pd.DataFrame) -> dict:
    """Top-k hit / precision / full-sweep, computed per race then averaged.

    ``df`` needs race_id, y_pred, y_true, finish_pos.
    """
    d = df.assign(rank=_rank_within_race(df))
    out: dict[str, float] = {}
    for k in (3, 4):
        picks = d[d["rank"] <= k]
        per_race = picks.groupby("race_id")["y_true"].sum()
        out[f"itm_hit_top{k}"] = float((per_race > 0).mean())
        out[f"itm_precision_top{k}"] = float(
            picks.groupby("race_id")["y_true"].mean().mean())
    top3 = d[d["rank"] <= 3]
    hits3 = top3.groupby("race_id")["y_true"].sum()
    sizes = top3.groupby("race_id")["y_true"].size()
    out["itm_full_sweep_top3"] = float(((hits3 == 3) & (sizes == 3)).mean())
    return out


# ---------------------------------------------------------------------------
# Longshots
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LongshotConfig:
    model_p_min: float = 0.25
    market_p_max: float = 0.20
    min_rank: int = 4


def longshot_flags(df: pd.DataFrame, cfg: LongshotConfig | None = None) -> np.ndarray:
    """Phase 4C's absolute-threshold rule, kept for back-comparison."""
    c = cfg or LongshotConfig()
    rank = _rank_within_race(df).to_numpy()
    return ((df["y_pred"].to_numpy() > c.model_p_min)
            & (df["p_market"].to_numpy() < c.market_p_max)
            & (rank >= c.min_rank))


def longshot_metrics(df: pd.DataFrame, cfg: LongshotConfig | None = None) -> dict:
    """Phase 4C rule, now reported with lift as well as raw precision.

    Phase 4C's ship criterion was "precision > 30%", which is unusable here:
    the ITM base rate is ~40%, so a 30% bar can be cleared by a filter that
    performs *worse than random*. GP's 35.3% was exactly that — 0.90x lift.
    Lift is the meaningful quantity and is now reported alongside.
    """
    flags = longshot_flags(df, cfg)
    base = float(df["y_true"].mean())
    n = int(flags.sum())
    if n == 0:
        return {"longshot_n": 0, "longshot_hits": 0,
                "longshot_precision": float("nan"),
                "longshot_lift": float("nan"),
                "longshot_base_itm_rate": base}
    hits = int(df.loc[flags, "y_true"].sum())
    prec = hits / n
    return {"longshot_n": n, "longshot_hits": hits,
            "longshot_precision": prec,
            "longshot_lift": prec / base if base > 0 else float("nan"),
            "longshot_base_itm_rate": base}


def longshot_ratio_metrics(df: pd.DataFrame, ratio: float = 1.15,
                           market_col: str = "p_market") -> dict:
    """Phase 4D rule: flag where model P(ITM) exceeds market P(ITM) by a ratio.

    ``flag = p_model > ratio * p_market``

    This replaces Phase 4C's absolute thresholds (p_model > 0.25 AND
    p_market < 0.20 AND rank >= 4), which mixed a confidence bar, a price bar
    and a rank bar and fired on only 51 of 108,386 entries. A ratio rule
    scales with field size and price level, so it is comparable across GP's
    8-horse fields and Mountaineer's 7-horse ones.

    Reported as **lift** = flagged ITM rate / base ITM rate. Lift > 1.0 means
    the filter beats picking a horse at random; the Phase 4D ship criterion is
    lift > 1.15.
    """
    p_model = df["y_pred"].to_numpy()
    p_mkt = df[market_col].to_numpy()
    flags = np.isfinite(p_mkt) & (p_model > ratio * p_mkt)
    base = float(df["y_true"].mean())
    n = int(flags.sum())
    out = {"ls_ratio": ratio, "ls_n": n,
           "ls_rate_of_field": n / len(df) if len(df) else float("nan"),
           "ls_base_itm_rate": base}
    if n == 0:
        out.update({"ls_hits": 0, "ls_precision": float("nan"),
                    "ls_lift": float("nan")})
        return out
    hits = int(df.loc[flags, "y_true"].sum())
    prec = hits / n
    out.update({"ls_hits": hits, "ls_precision": prec,
                "ls_lift": prec / base if base > 0 else float("nan")})
    return out


# ---------------------------------------------------------------------------
# Market calibration (Phase 4D)
# ---------------------------------------------------------------------------

def fit_market_calibration(p_market: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Platt scaling of the Harville market estimate: sigmoid(a*logit(p)+b).

    Phase 4C found raw Harville P(ITM) is materially overconfident (ECE 0.033
    against DPv1's 0.011), which broke the exacta edge trigger: the model
    prices its own favourite *below* the raw market on essentially every race,
    so "edge >= 5pp vs market" fired 0 times in 14,543 races. Comparing
    against a calibrated market makes the edge measure what it was meant to.

    Fit on TRAIN-fold data only; apply to validation.
    """
    from scipy.optimize import minimize

    ok = np.isfinite(p_market) & np.isfinite(y)
    lp = _logit(p_market[ok])
    yy = np.asarray(y, dtype=float)[ok]

    def obj(params):
        a, b = params
        s = a * lp + b
        log1p_exp = np.log1p(np.exp(-np.abs(s))) + np.maximum(s, 0.0)
        return float(np.sum(-(yy * s - log1p_exp)))

    res = minimize(obj, x0=np.array([1.0, 0.0]), method="L-BFGS-B",
                   options={"maxiter": 200})
    return float(res.x[0]), float(res.x[1])


def apply_market_calibration(p_market: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a * _logit(p_market) + b)))


# ---------------------------------------------------------------------------
# Wagering
# ---------------------------------------------------------------------------

def load_payouts(db_path: str, wager: str, date_min: str = "2022-01-01") -> pd.DataFrame:
    """Per-race payoff per $1 staked: min / mean / max across winning combos."""
    names = WAGER_ALIASES.get(wager, (wager,))
    placeholders = ",".join("?" * len(names))
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        f"""
        SELECT x.race_id, x.base_amount, x.payoff, x.winning_numbers
        FROM exotic_payouts x
        JOIN races r ON r.id = x.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE x.wager_name IN ({placeholders}) AND rd.race_date >= ?
        """,
        conn, params=(*names, date_min),
    )
    conn.close()
    # MNR records its Perfecta rows twice, verbatim.
    df = df.drop_duplicates(subset=["race_id", "winning_numbers", "payoff"])
    df = df[(df["payoff"] > 0) & (df["base_amount"] > 0)]
    df["per_dollar"] = df["payoff"] / df["base_amount"]
    g = df.groupby("race_id")["per_dollar"]
    return pd.DataFrame({"payoff_min": g.min(), "payoff_mean": g.mean(),
                         "payoff_max": g.max(),
                         "n_combos": g.size()}).reset_index()


def box_roi(df: pd.DataFrame, payouts: pd.DataFrame, k: int, m: int,
            ticket_cost: float = 1.0, payoff_col: str = "payoff_mean",
            restrict_races: set | None = None) -> dict:
    """ROI of a straight box over the model's top-``k`` picks for an ``m``-leg
    exotic (m=2 exacta, 3 trifecta, 4 superfecta).

    A box over k picks buys every ordered permutation: ``k!/(k-m)!`` tickets.
    It wins when the actual top-``m`` finishers are all inside the k picks.
    Races without a resolved top-``m`` or without a payout row are skipped
    rather than counted as losses.
    """
    if k < m:
        raise ValueError("k must be >= m")
    tickets = math.perm(k, m)
    stake_per_race = tickets * ticket_cost

    d = df.assign(rank=_rank_within_race(df))
    if restrict_races is not None:
        d = d[d["race_id"].isin(restrict_races)]

    picks = (d[d["rank"] <= k].groupby("race_id")["entry_id"]
             .agg(frozenset).rename("picks"))
    pick_n = d[d["rank"] <= k].groupby("race_id")["entry_id"].size()
    picks = picks[pick_n >= k]

    fin = d.dropna(subset=["finish_pos"]).sort_values("finish_pos")
    actual = (fin.groupby("race_id").head(m)
              .groupby("race_id")["entry_id"].agg(frozenset).rename("actual"))
    actual_n = fin.groupby("race_id").head(m).groupby("race_id")["entry_id"].size()
    actual = actual[actual_n >= m]

    j = pd.concat([picks, actual], axis=1, join="inner").reset_index()
    j = j.merge(payouts[["race_id", payoff_col]], on="race_id", how="inner")
    if j.empty:
        return {"n_races": 0, "n_hits": 0, "stake": 0.0, "return": 0.0,
                "pnl": 0.0, "roi": float("nan"), "tickets_per_race": tickets}

    hit = np.array([a <= p for p, a in zip(j["picks"], j["actual"])])
    gross = float((j.loc[hit, payoff_col] * ticket_cost).sum())
    stake = float(len(j) * stake_per_race)
    return {"n_races": int(len(j)), "n_hits": int(hit.sum()),
            "stake": stake, "return": gross, "pnl": gross - stake,
            "roi": (gross - stake) / stake if stake > 0 else float("nan"),
            "tickets_per_race": tickets}


def exacta_edge_roi(df: pd.DataFrame, payouts: pd.DataFrame,
                    edge_min: float = 0.05, ticket_cost: float = 1.0,
                    market_col: str = "p_market") -> dict:
    """Exacta box over the top 2 picks, in races where the model claims an edge.

    ``market_col`` should be the **calibrated** market column
    (``p_market_cal``) — see ``fit_market_calibration``. Measured against raw
    Harville this trigger cannot fire, because the blend systematically prices
    its own favourite below an overconfident market.
    """
    d = df.assign(rank=_rank_within_race(df))
    top = d[d["rank"] == 1]
    edge = top["y_pred"].to_numpy() - top[market_col].to_numpy()
    keep = set(top.loc[edge >= edge_min, "race_id"])
    out = box_roi(d, payouts, k=2, m=2, ticket_cost=ticket_cost,
                  restrict_races=keep)
    out["edge_min"] = edge_min
    out["races_qualifying"] = len(keep)
    out["races_total"] = int(top["race_id"].nunique())
    out["trigger_rate"] = (len(keep) / out["races_total"]
                           if out["races_total"] else float("nan"))
    out["market_col"] = market_col
    return out


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

def evaluate_slice(df: pd.DataFrame, payouts: dict[str, pd.DataFrame] | None = None,
                   with_wagering: bool = True) -> dict:
    """Full metric bundle for one slice.

    ``df`` needs: entry_id, race_id, y_pred, p_market, p_fund, y_true,
    finish_pos.
    """
    y = df["y_true"].to_numpy()
    p = df["y_pred"].to_numpy()
    out: dict = {
        "n_entries": int(len(df)),
        "n_races": int(df["race_id"].nunique()),
        "itm_base_rate": float(y.mean()),
        "log_loss": binary_log_loss(y, p),
        "brier": brier_score(y, p),
        "ece": expected_calibration_error(y, p),
        "corr_logit_pf_pm": corr_logit(df["p_fund"].to_numpy(),
                                       df["p_market"].to_numpy()),
        "log_loss_market": binary_log_loss(y, df["p_market"].to_numpy()),
        "log_loss_fund": binary_log_loss(y, df["p_fund"].to_numpy()),
    }
    out["log_loss_vs_market_pct"] = (
        100.0 * (out["log_loss_market"] - out["log_loss"]) / out["log_loss_market"]
    )
    if "p_market_cal" in df.columns:
        out["log_loss_market_cal"] = binary_log_loss(
            y, df["p_market_cal"].to_numpy())
        out["ece_market_cal"] = expected_calibration_error(
            y, df["p_market_cal"].to_numpy())
        out["log_loss_vs_market_cal_pct"] = (
            100.0 * (out["log_loss_market_cal"] - out["log_loss"])
            / out["log_loss_market_cal"])

    out.update(itm_selection_metrics(df))
    out.update(longshot_metrics(df))
    # NB: round(), not int() — int(1.15 * 100) is 114 in binary floating point,
    # which silently produced an ls114_* key and an unfindable ls115_* metric.
    for r in (1.10, 1.15, 1.25):
        tag = f"ls{round(r * 100)}"
        m = longshot_ratio_metrics(df, ratio=r)
        out[f"{tag}_n"] = m["ls_n"]
        out[f"{tag}_precision"] = m["ls_precision"]
        out[f"{tag}_lift"] = m["ls_lift"]
        if "p_market_cal" in df.columns:
            mc = longshot_ratio_metrics(df, ratio=r, market_col="p_market_cal")
            out[f"{tag}cal_n"] = mc["ls_n"]
            out[f"{tag}cal_precision"] = mc["ls_precision"]
            out[f"{tag}cal_lift"] = mc["ls_lift"]

    if with_wagering and payouts:
        for label, (wager, k, m) in {
            "trifecta_box3": ("Trifecta", 3, 3),
            "trifecta_box4": ("Trifecta", 4, 3),
            "superfecta_box4": ("Superfecta", 4, 4),
        }.items():
            pay = payouts.get(wager)
            if pay is None:
                continue
            r = box_roi(df, pay, k=k, m=m)
            out[f"{label}_roi"] = r["roi"]
            out[f"{label}_races"] = r["n_races"]
            out[f"{label}_hits"] = r["n_hits"]
            for variant in ("payoff_min", "payoff_max"):
                rv = box_roi(df, pay, k=k, m=m, payoff_col=variant)
                out[f"{label}_roi_{variant.split('_')[1]}"] = rv["roi"]
        pay_ex = payouts.get("Exacta")
        if pay_ex is not None:
            mcol = "p_market_cal" if "p_market_cal" in df.columns else "p_market"
            for thr in (0.02, 0.05):
                r = exacta_edge_roi(df, pay_ex, edge_min=thr, market_col=mcol)
                tag = f"exacta_edge{int(thr * 100)}"
                out[f"{tag}_roi"] = r["roi"]
                out[f"{tag}_races"] = r["n_races"]
                out[f"{tag}_hits"] = r["n_hits"]
                out[f"{tag}_trigger_rate"] = r["trigger_rate"]
            # Unconditional exacta box over the top 2, as a floor.
            r = box_roi(df, pay_ex, k=2, m=2)
            out["exacta_box2_roi"] = r["roi"]
            out["exacta_box2_races"] = r["n_races"]
            r3 = box_roi(df, pay_ex, k=3, m=2)
            out["exacta_box3_roi"] = r3["roi"]
            out["exacta_box3_races"] = r3["n_races"]
    return out


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def market_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """The chalk strategy: rank by market P(ITM), predict market P(ITM)."""
    return df.assign(y_pred=df["p_market"], p_fund=df["p_market"])


def random_baseline(df: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Uniform-random ranking; predicted probability = the slice ITM rate."""
    rng = np.random.default_rng(seed)
    base = float(df["y_true"].mean())
    return df.assign(y_pred=rng.uniform(size=len(df)),
                     p_fund=np.full(len(df), base))
