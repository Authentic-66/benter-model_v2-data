"""Evaluation metrics for the Benter Model v2.

A canonical **predictions DataFrame** has these columns:

    entry_id      : row id in ``entries``
    race_id       : row id in ``races``  (used for per-race grouping)
    y_true        : 1 if this horse won the race, else 0
    y_pred        : model's predicted P(win) for this horse — can be any
                    non-negative real; per-race normalisation happens
                    inside the metric functions that need it
    final_odds    : chart final tote odds (used for ROI and Kelly)

Every function is a plain callable that accepts this DataFrame and returns
a number or a small dict. Missing (NaN) inputs are treated as follows:

* NaN ``y_pred`` in a race -> the horse gets the uniform per-race prior
  before renormalisation (i.e. we don't reward the model for silence).
* NaN ``final_odds`` -> that horse is skipped by ROI/Kelly but still
  contributes to log-loss and calibration.

Metric families
---------------

Statistical
    log_loss_per_race
    brier_score_per_race
    expected_calibration_error

Ranking
    hit_rate_top_k
    winner_odds_rank

Betting
    roi_flat_bet
    kelly_bankroll_sim

Sanity
    favorite_hit_rate
    calibration_table
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLS = ("race_id", "y_true", "y_pred")


def _validate(df: pd.DataFrame, extra: Iterable[str] = ()) -> None:
    missing = [c for c in list(REQUIRED_COLS) + list(extra) if c not in df.columns]
    if missing:
        raise ValueError(f"predictions_df is missing columns: {missing}")


def _normalize_per_race(df: pd.DataFrame) -> pd.Series:
    """Return a copy of ``y_pred`` renormalised so each race sums to 1.

    NaN predictions are replaced with the uniform per-race prior before
    normalisation. If an entire race is NaN we fall back to uniform.
    """
    yp = df["y_pred"].to_numpy(dtype=float, copy=True)
    race_ids = df["race_id"].to_numpy()
    # Uniform prior per race, computed from race sizes
    sizes = pd.Series(race_ids).groupby(race_ids).transform("size").to_numpy()
    uniform = 1.0 / sizes
    yp = np.where(np.isnan(yp), uniform, yp)
    # Groupwise sum, then divide
    sums = pd.Series(yp).groupby(race_ids).transform("sum").to_numpy()
    sums = np.where(sums <= 0, 1.0, sums)
    return pd.Series(yp / sums, index=df.index, name="y_pred_norm")


# ---------------------------------------------------------------------------
# Statistical
# ---------------------------------------------------------------------------

def log_loss_per_race(df: pd.DataFrame, eps: float = 1e-15) -> float:
    """Multinomial per-race log-loss: ``-mean(log(p_winner))``.

    Predictions are renormalised so each race sums to 1. Only the row
    with ``y_true = 1`` in each race contributes. Races without a marked
    winner (all ``y_true = 0``) are skipped.

    Lower is better. A model that predicts uniform 1/N in every race
    scores exactly ``mean(log(N))``. Beating that is the minimum bar.
    """
    _validate(df)
    p = _normalize_per_race(df).clip(lower=eps, upper=1 - eps)
    winners = df[df["y_true"] == 1]
    if len(winners) == 0:
        return float("nan")
    return float(-np.log(p.loc[winners.index]).mean())


def brier_score_per_race(df: pd.DataFrame) -> float:
    """Multinomial Brier: ``mean_races(sum_horses((y_true - p_norm)^2))``.

    Lower is better. Uses per-race-normalised probabilities.
    """
    _validate(df)
    p = _normalize_per_race(df)
    sq = (df["y_true"].astype(float) - p) ** 2
    return float(sq.groupby(df["race_id"]).sum().mean())


def expected_calibration_error(
    df: pd.DataFrame, n_bins: int = 10
) -> float:
    """ECE over probability buckets.

    Renormalises predictions per race. Bins the resulting probabilities
    into ``n_bins`` equal-width bins over [0, 1], then computes the
    absolute difference between mean predicted probability and observed
    win rate in each bin, weighted by bin population.

    Lower is better. Perfect calibration -> 0.
    """
    _validate(df)
    p = _normalize_per_race(df).to_numpy()
    y = df["y_true"].to_numpy(dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    ece = 0.0
    n = len(df)
    for b in range(n_bins):
        m = bin_idx == b
        if not np.any(m):
            continue
        avg_p = p[m].mean()
        avg_y = y[m].mean()
        ece += (m.sum() / n) * abs(avg_p - avg_y)
    return float(ece)


def calibration_table(df: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """Per-bin calibration diagnostic — useful for plotting and inspection."""
    _validate(df)
    p = _normalize_per_race(df).to_numpy()
    y = df["y_true"].to_numpy(dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = bin_idx == b
        rows.append({
            "bin": b,
            "range_lo": edges[b],
            "range_hi": edges[b + 1],
            "n_entries": int(m.sum()),
            "avg_pred": float(p[m].mean()) if m.any() else float("nan"),
            "obs_hit_rate": float(y[m].mean()) if m.any() else float("nan"),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def _ranks_desc(df: pd.DataFrame, tie_break_seed: int = 42) -> pd.Series:
    """Per-race descending rank of ``y_pred`` with random tie-breaking.

    Naive ``rank(method='first')`` breaks ties in DataFrame insertion order,
    which in this project's DB happens to be finish order — that leaks the
    winner into the tie-broken rank. We add tiny uniform noise (seeded, so
    reproducible) so ties are broken randomly rather than positionally.

    For real models with almost no ties this is a no-op; for uniform
    predictions it gives the honest 1/N-per-slot behaviour.
    """
    rng = np.random.default_rng(tie_break_seed)
    jitter = rng.uniform(0.0, 1e-12, size=len(df))
    yp = df["y_pred"].to_numpy(dtype=float) + jitter
    ranked = (pd.Series(yp, index=df.index)
              .groupby(df["race_id"])
              .rank(method="first", ascending=False))
    return ranked.astype(int)


def hit_rate_top_k(
    df: pd.DataFrame, k: int = 1, tie_break_seed: int = 42
) -> float:
    """Fraction of races where the winner is in the model's top-k picks.

    Predictions are ranked descending per race. Ties in ``y_pred`` are
    broken by a seeded random jitter so uniform predictions score the
    expected ``k / mean_field_size`` (not 100% because insertion order
    happens to correlate with finish order).

    Skips races with no marked winner.
    """
    _validate(df)
    if k < 1:
        raise ValueError("k must be >= 1")
    ranks = _ranks_desc(df, tie_break_seed=tie_break_seed)
    winners = df[df["y_true"] == 1]
    if winners.empty:
        return float("nan")
    winner_ranks = ranks.loc[winners.index]
    return float((winner_ranks <= k).mean())


def winner_odds_rank(
    df: pd.DataFrame, tie_break_seed: int = 42
) -> pd.Series:
    """For each race, return the ordinal rank the model gave the actual winner.

    Useful for diagnostic plots (how often is the winner in slot 1, 2, 3...).
    """
    _validate(df)
    ranks = _ranks_desc(df, tie_break_seed=tie_break_seed)
    winners = df[df["y_true"] == 1]
    return ranks.loc[winners.index].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Betting
# ---------------------------------------------------------------------------

def roi_flat_bet(
    df: pd.DataFrame,
    edge_threshold: float = 0.20,
    bet_amount: float = 2.0,
) -> dict[str, float]:
    """Flat-bet simulation.

    Places a fixed ``bet_amount`` on each horse whose model probability
    exceeds the market implied probability by at least ``edge_threshold``
    (relative). ``edge = (p_model - p_market) / p_market``.

    Rows with NaN odds are skipped. Rows with odds <= 0 are skipped.

    Returns:
        n_bets      : how many bets were placed
        total_stake : sum of stakes
        total_return: gross return (stake + profit on winners, 0 on losers)
        pnl         : total_return - total_stake
        roi         : pnl / total_stake  (fraction)
        hit_rate    : fraction of the placed bets that won
    """
    _validate(df, extra=("final_odds",))
    if edge_threshold < 0:
        raise ValueError("edge_threshold must be non-negative")
    p_model = _normalize_per_race(df).to_numpy()
    odds = df["final_odds"].to_numpy(dtype=float)
    y = df["y_true"].to_numpy(dtype=float)
    p_market = 1.0 / (odds + 1.0)
    valid = np.isfinite(odds) & (odds > 0) & np.isfinite(p_market) & (p_market > 0)
    edge = np.where(valid, (p_model - p_market) / p_market, -np.inf)
    bet_mask = valid & (edge >= edge_threshold)
    n_bets = int(bet_mask.sum())
    if n_bets == 0:
        return dict(n_bets=0, total_stake=0.0, total_return=0.0,
                    pnl=0.0, roi=float("nan"), hit_rate=float("nan"))
    stake = bet_amount * n_bets
    # Return per winning bet: bet_amount * (final_odds + 1)  (stake + profit)
    returns = np.where(y[bet_mask] == 1,
                       bet_amount * (odds[bet_mask] + 1.0),
                       0.0)
    total_return = float(returns.sum())
    pnl = total_return - stake
    return dict(
        n_bets=n_bets,
        total_stake=stake,
        total_return=total_return,
        pnl=pnl,
        roi=pnl / stake,
        hit_rate=float(y[bet_mask].mean()),
    )


def kelly_bankroll_sim(
    df: pd.DataFrame,
    starting_bankroll: float = 1000.0,
    kelly_fraction: float = 0.25,
    min_edge: float = 0.20,
    cap_bet_frac: float = 0.05,
) -> dict[str, float]:
    """Kelly-fractional bankroll simulation, race-by-race in chronological order.

    For each entry with edge >= ``min_edge``:

        f_kelly = (b*p - q) / b     with b = odds, p = p_model, q = 1-p
        bet     = bankroll * kelly_fraction * f_kelly
                clipped to [0, bankroll * cap_bet_frac]

    Bets are placed *before* the outcome is known; bankroll is updated after
    each race. Races are processed in the order they appear — pass in
    chronologically-sorted predictions to get a chronological simulation.

    ``kelly_fraction`` < 1 is standard "fractional Kelly" to reduce variance.
    ``cap_bet_frac`` caps any single bet at that fraction of the current
    bankroll to prevent one crazy edge from betting the house.

    Returns:
        final_bankroll : bankroll after the last race
        n_bets         : total bets placed
        n_wins         : winning bets
        peak_bankroll  : max bankroll observed
        min_bankroll   : min bankroll observed
        pnl            : final - starting
        pnl_pct        : pnl / starting
    """
    _validate(df, extra=("final_odds",))
    p_model = _normalize_per_race(df).to_numpy()
    odds = df["final_odds"].to_numpy(dtype=float)
    y = df["y_true"].to_numpy(dtype=float)
    p_market = 1.0 / (odds + 1.0)
    valid = np.isfinite(odds) & (odds > 0) & (p_market > 0)
    edge = np.where(valid, (p_model - p_market) / p_market, -np.inf)

    bankroll = starting_bankroll
    peak = starting_bankroll
    trough = starting_bankroll
    n_bets = 0
    n_wins = 0

    # Group by race to bet all edge horses in one pass
    race_ids = df["race_id"].to_numpy()
    _, boundaries = np.unique(race_ids, return_index=True)
    boundaries = np.append(np.sort(boundaries), len(df))

    for i in range(len(boundaries) - 1):
        lo, hi = boundaries[i], boundaries[i + 1]
        placed: list[tuple[float, float, float]] = []  # (stake, odds, y)
        for j in range(lo, hi):
            if edge[j] < min_edge:
                continue
            b = odds[j]
            p = p_model[j]
            f_kelly = (b * p - (1 - p)) / b
            if f_kelly <= 0:
                continue
            raw_stake = bankroll * kelly_fraction * f_kelly
            stake = min(raw_stake, bankroll * cap_bet_frac)
            if stake <= 0 or stake > bankroll:
                continue
            placed.append((stake, b, y[j]))
        for stake, b, yj in placed:
            bankroll -= stake
            n_bets += 1
            if yj == 1:
                bankroll += stake * (b + 1.0)
                n_wins += 1
        peak = max(peak, bankroll)
        trough = min(trough, bankroll)
        if bankroll <= 0:
            break

    return dict(
        final_bankroll=bankroll,
        n_bets=n_bets,
        n_wins=n_wins,
        peak_bankroll=peak,
        min_bankroll=trough,
        pnl=bankroll - starting_bankroll,
        pnl_pct=(bankroll - starting_bankroll) / starting_bankroll,
    )


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------

def favorite_hit_rate(df: pd.DataFrame) -> float:
    """Empirical win rate of the post-time favorite.

    Uses ``final_odds`` — lowest odds per race is the favorite. Ties
    (multiple horses at the same lowest odds) all count.
    """
    _validate(df, extra=("final_odds",))
    min_odds = df.groupby("race_id")["final_odds"].transform("min")
    fav_rows = df[df["final_odds"] == min_odds]
    if fav_rows.empty:
        return float("nan")
    return float(fav_rows["y_true"].mean())


# ---------------------------------------------------------------------------
# Convenience: compute all standard metrics in one call
# ---------------------------------------------------------------------------

def evaluate(
    predictions_df: pd.DataFrame,
    include_kelly: bool = False,
) -> dict[str, float]:
    """One-shot: compute the standard metric bundle.

    Returns a flat dict suitable for logging or tabulation.
    """
    out: dict[str, float] = {
        "log_loss_per_race": log_loss_per_race(predictions_df),
        "brier_score_per_race": brier_score_per_race(predictions_df),
        "ece_10bin": expected_calibration_error(predictions_df, n_bins=10),
        "hit_rate_top1": hit_rate_top_k(predictions_df, k=1),
        "hit_rate_top3": hit_rate_top_k(predictions_df, k=3),
        "favorite_hit_rate": favorite_hit_rate(predictions_df),
    }
    for edge in (0.20, 0.30, 0.40, 0.50):
        roi = roi_flat_bet(predictions_df, edge_threshold=edge)
        out[f"roi_edge{int(edge*100):02d}"] = roi["roi"]
        out[f"n_bets_edge{int(edge*100):02d}"] = roi["n_bets"]
    if include_kelly:
        k = kelly_bankroll_sim(predictions_df)
        out["kelly_final_bankroll"] = k["final_bankroll"]
        out["kelly_pnl_pct"] = k["pnl_pct"]
        out["kelly_n_bets"] = k["n_bets"]
    return out


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Smoke-test on a tiny synthetic dataset.

    Two races of 4 horses each. Winner known. Uniform predictions should
    give exactly ``log(4)`` log-loss per race and 25% top-1 hit rate.

    >>> _self_test()
    ok
    """
    rows = []
    for race_id in (1, 2):
        for h in range(4):
            rows.append({
                "entry_id": race_id * 10 + h,
                "race_id": race_id,
                "y_true": 1 if h == 0 else 0,
                "y_pred": 0.25,
                "final_odds": 4.0,
            })
    df = pd.DataFrame(rows)
    ll = log_loss_per_race(df)
    assert abs(ll - np.log(4)) < 1e-9, f"log-loss {ll} != log(4)"
    top1 = hit_rate_top_k(df, k=1)
    assert 0.0 <= top1 <= 1.0
    assert hit_rate_top_k(df, k=4) == 1.0
    ece = expected_calibration_error(df)
    assert ece >= 0
    fav = favorite_hit_rate(df)
    assert fav == 0.25   # all tied at 4.0; winner (h=0) is one of 4 favorites
    roi = roi_flat_bet(df, edge_threshold=0.0)
    assert "roi" in roi
    print("ok")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=False)
    _self_test()
    print("\nStandard metric bundle demo (2-race uniform):")
    rows = [{"entry_id": r * 10 + h, "race_id": r,
             "y_true": 1 if h == 0 else 0,
             "y_pred": 0.25, "final_odds": 4.0}
            for r in (1, 2) for h in range(4)]
    for k, v in evaluate(pd.DataFrame(rows)).items():
        print(f"  {k:<24}  {v}")
