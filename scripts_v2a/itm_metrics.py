"""ITM-specific evaluation metrics for Phase 3G.

Canonical predictions DataFrame (same shape as Phase 3D ``metrics``):

    entry_id, race_id, y_pred (P(ITM) — need not sum to 3 per race),
    y_true (0/1 ITM indicator), final_odds

Additional field used by some metrics:
    finish_pos (integer, 1-based; NaN for DNF/DQ)

Metrics
-------

**Coverage & ranking (top-K)**
    itm_hit_rate_top_k          any-hit rate: fraction of races where the
                                model's top-K picks contain at least 1
                                actual ITM finisher.
    itm_precision_top_k         mean fraction of the model's top-K picks
                                that were themselves ITM. K = 3 or 4.
    itm_recall_top_k            mean fraction of the race's actual ITM
                                finishers that appeared in top-K.
    itm_full_sweep_top_3        fraction of races where ALL top-3 picks
                                finished ITM (i.e., box trifecta hit).

**Longshot precision**
    longshot_precision          of flagged longshots, fraction that
                                actually finished ITM.
    longshot_hit_count          integer count for context.

**Exotic-wager ROI**
    trifecta_box_roi_top3       Box trifecta on model's top-3 picks
                                (costs 6 × $1 tickets per race).
    trifecta_box_roi_top4       Same on top-4 (24 tickets per race).
    superfecta_box_roi_top4     Box superfecta on top-4 (24 × $0.10 = $2.40
                                per race).
    exacta_box_roi_top3         Box exacta on top 2 of top-3 picks.

**Confidence stratification**
    Buckets races by the top-1 P(ITM); reports the ITM hit rate of the
    top-K picks within each bucket to identify where the model is
    confident and correct vs. confident and wrong.

Trifecta/superfecta payouts are looked up in the ``exotic_payouts`` table
by an accompanying loader; the metric functions take payouts as a
DataFrame column so they stay pure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLS = ("race_id", "y_true", "y_pred")


def _validate(df: pd.DataFrame, extra=()) -> None:
    missing = [c for c in list(REQUIRED_COLS) + list(extra) if c not in df.columns]
    if missing:
        raise ValueError(f"predictions_df missing columns: {missing}")


def _ranked_within_race(df: pd.DataFrame, seed: int = 42) -> pd.Series:
    """Return integer per-race rank (1 = highest y_pred) with random tie-break."""
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(0.0, 1e-12, size=len(df))
    yp = df["y_pred"].to_numpy(dtype=float) + jitter
    ranked = (pd.Series(yp, index=df.index)
              .groupby(df["race_id"])
              .rank(method="first", ascending=False))
    return ranked.astype(int)


# ---------------------------------------------------------------------------
# Ranking / coverage
# ---------------------------------------------------------------------------

def itm_hit_rate_top_k(df: pd.DataFrame, k: int = 3) -> float:
    """Fraction of races whose top-K picks contain ≥1 actual ITM finisher."""
    _validate(df)
    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    in_top = df2[df2["rank"] <= k]
    per_race = in_top.groupby("race_id")["y_true"].max()
    return float((per_race > 0).mean())


def itm_precision_top_k(df: pd.DataFrame, k: int = 3) -> float:
    """Mean fraction of top-K picks per race that were ITM."""
    _validate(df)
    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    in_top = df2[df2["rank"] <= k]
    per_race = in_top.groupby("race_id")["y_true"].mean()
    return float(per_race.mean())


def itm_recall_top_k(df: pd.DataFrame, k: int = 3) -> float:
    """Mean fraction of actual ITM finishers per race captured in top-K."""
    _validate(df)
    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    itm_rows = df2[df2["y_true"] == 1]
    total_itm = itm_rows.groupby("race_id")["y_true"].count()
    top_itm = df2[(df2["rank"] <= k) & (df2["y_true"] == 1)]
    captured = top_itm.groupby("race_id")["y_true"].count()
    combined = pd.concat({"cap": captured, "tot": total_itm}, axis=1).fillna(0)
    with np.errstate(invalid="ignore"):
        rate = np.where(combined["tot"] > 0, combined["cap"] / combined["tot"], np.nan)
    return float(np.nanmean(rate))


def itm_full_sweep_top_3(df: pd.DataFrame) -> float:
    """Fraction of races where all 3 top-3 picks finished ITM (trifecta box)."""
    _validate(df)
    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    top3 = df2[df2["rank"] <= 3]
    per_race = top3.groupby("race_id").agg(
        n_top=("y_true", "count"),
        n_itm=("y_true", "sum"),
    )
    swept = (per_race["n_top"] == 3) & (per_race["n_itm"] == 3)
    return float(swept.mean())


# ---------------------------------------------------------------------------
# Longshot precision
# ---------------------------------------------------------------------------

def longshot_metrics(df: pd.DataFrame, longshot_flags: pd.Series) -> dict:
    """Given per-entry longshot flags, compute precision and count.

    ``longshot_flags`` is a boolean series aligned to ``df.index``. See
    ``longshot_detector.py`` for the flag definition.
    """
    _validate(df)
    flagged = df[longshot_flags.reindex(df.index, fill_value=False).astype(bool)]
    if flagged.empty:
        return {"n_flagged": 0, "precision": float("nan"), "hits": 0}
    return {
        "n_flagged": int(len(flagged)),
        "hits": int(flagged["y_true"].sum()),
        "precision": float(flagged["y_true"].mean()),
    }


# ---------------------------------------------------------------------------
# Exotic-wager ROI
# ---------------------------------------------------------------------------

def trifecta_box_roi(
    df: pd.DataFrame,
    payouts_df: pd.DataFrame,
    k: int = 3,
    ticket_cost: float = 1.0,
) -> dict:
    """Box trifecta over top-K picks per race.

    Assumes the ``exotic_payouts`` table (from Phase 3A) is filtered to
    ``wager_name = 'Trifecta'`` with ``base_amount``, ``payoff`` (per that
    base amount), and ``winning_numbers``. We match against model's top-K
    picks by program number.

    ``payouts_df`` columns required:
        race_id, base_amount, payoff, winning_numbers (e.g., '4-6-1'),
        entry_by_pgm (dict from program_num string -> entry_id, per race)

    Returns:
        n_races      races where we placed the wager (K picks resolved)
        n_hits       races where the box won
        stake_total  total stake (K*(K-1)*(K-2) tickets * $1 base)
        return_total sum of gross returns
        pnl          net PnL
        roi          pnl / stake_total
    """
    _validate(df, extra=("finish_pos",))
    if k < 3:
        raise ValueError("trifecta requires k >= 3")
    tickets_per_race = k * (k - 1) * (k - 2)   # ordered box count
    stake_per_race = tickets_per_race * ticket_cost

    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    top_by_race = (df2[df2["rank"] <= k]
                   .groupby("race_id")["entry_id"]
                   .agg(list))

    race_ids = list(top_by_race.index)
    hits = 0
    total_return = 0.0
    n_races = 0
    for race_id in race_ids:
        entries = top_by_race[race_id]
        if len(entries) < k:
            continue
        sub = df2[df2["race_id"] == race_id]
        actual_top3 = (sub.dropna(subset=["finish_pos"])
                          .sort_values("finish_pos")
                          .head(3)["entry_id"].tolist())
        if len(actual_top3) < 3:
            continue
        n_races += 1
        # Box hit if all 3 actual top-3 entries are in our top-K picks
        if set(actual_top3).issubset(set(entries)):
            payout_rows = payouts_df[payouts_df["race_id"] == race_id]
            if payout_rows.empty:
                continue
            # Use $1 base for consistency
            row = payout_rows.iloc[0]
            base = row["base_amount"] if row["base_amount"] and row["base_amount"] > 0 else 1.0
            payoff = row["payoff"] if row["payoff"] else 0.0
            gross_return = (ticket_cost / base) * payoff
            total_return += gross_return
            hits += 1

    stake_total = n_races * stake_per_race
    pnl = total_return - stake_total
    return {
        "n_races": n_races,
        "n_hits": hits,
        "stake_total": stake_total,
        "return_total": total_return,
        "pnl": pnl,
        "roi": (pnl / stake_total) if stake_total > 0 else float("nan"),
    }


# ---------------------------------------------------------------------------
# Confidence stratification
# ---------------------------------------------------------------------------

def confidence_stratified_top_k(
    df: pd.DataFrame, k: int = 3, n_buckets: int = 4,
) -> pd.DataFrame:
    """Bucket races by top-1 P(ITM); report top-K hit rate per bucket."""
    _validate(df)
    ranks = _ranked_within_race(df)
    df2 = df.assign(rank=ranks)
    top1 = (df2[df2["rank"] == 1]
            .set_index("race_id")["y_pred"]
            .rename("top1_pred"))
    df2 = df2.merge(top1, on="race_id")
    df2["bucket"] = pd.qcut(df2["top1_pred"], q=n_buckets, duplicates="drop",
                             labels=False)
    rows = []
    for bucket in sorted(df2["bucket"].dropna().unique()):
        sub = df2[df2["bucket"] == bucket]
        top_k = sub[sub["rank"] <= k]
        per_race = top_k.groupby("race_id")["y_true"].max()
        rows.append({
            "bucket": int(bucket),
            "top1_pred_min": float(sub["top1_pred"].min()),
            "top1_pred_max": float(sub["top1_pred"].max()),
            "n_races": int(per_race.count()),
            "top_k_hit_rate": float((per_race > 0).mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Convenience: full ITM bundle
# ---------------------------------------------------------------------------

def evaluate_itm(df: pd.DataFrame) -> dict[str, float]:
    """Compute the metric bundle we care about for ITM."""
    _validate(df)
    out = {
        "itm_hit_rate_top3": itm_hit_rate_top_k(df, k=3),
        "itm_hit_rate_top4": itm_hit_rate_top_k(df, k=4),
        "itm_precision_top3": itm_precision_top_k(df, k=3),
        "itm_precision_top4": itm_precision_top_k(df, k=4),
        "itm_recall_top3": itm_recall_top_k(df, k=3),
        "itm_recall_top4": itm_recall_top_k(df, k=4),
        "itm_full_sweep_top_3": itm_full_sweep_top_3(df),
    }
    return out
