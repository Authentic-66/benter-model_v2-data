"""Market P(ITM) estimate from tote win odds.

The tote board publishes win odds only. Estimating market P(ITM) from
those requires modelling how the win-probability translates into P(2nd)
and P(3rd). We use the **Harville reduction** (Harville 1973): given
win probabilities ``p_1, ..., p_N`` summing to 1 per race, we treat
finish positions as sequential draws without replacement from a
softmax-shrunk distribution:

    P(i wins)            = p_i
    P(j is 2nd | i wins) = p_j / (1 - p_i)
    P(k is 3rd | i, j)   = p_k / (1 - p_i - p_j)

Then

    P(i ITM) = P(i wins)
             + sum_{j != i} p_j * p_i / (1 - p_j)
             + sum_{j, k distinct, both != i}
                 p_j * (p_k / (1 - p_j)) * (p_i / (1 - p_j - p_k))

Harville is known to be biased for horses at the extremes (over-estimates
favourites' place probabilities) but it's fast, well-understood, and a
standard baseline in the horse-racing literature. Bias-correction
(Henery 1981, Lo and Bacon-Shone 1993) can layer on top later.

Efficient computation per race: vectorised over pairs of leaders.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketModelITM:
    """Estimate per-entry market P(ITM) from per-race win probs."""

    name: str = "market_itm_harville"

    def predict_p_itm(
        self,
        p_win_per_race: np.ndarray,
        race_ids: np.ndarray,
    ) -> np.ndarray:
        """Return per-entry P(ITM) computed via Harville.

        ``p_win_per_race`` should be the tote-implied win probability, per-
        race-normalised so each race sums to 1. NaN inputs are propagated.
        """
        p = np.asarray(p_win_per_race, dtype=float)
        rid = np.asarray(race_ids)
        out = np.full_like(p, np.nan)
        r_series = pd.Series(rid)
        for r, idx in r_series.groupby(rid).groups.items():
            idx = np.asarray(idx.values)
            pv = p[idx]
            if not np.all(np.isfinite(pv)):
                continue
            pv = np.clip(pv, 1e-12, 1 - 1e-12)
            # Harville per horse
            n = len(pv)
            if n < 3:
                # Trivially, in a 2-horse race everyone is ITM
                out[idx] = 1.0
                continue
            itm = pv.copy()   # P(win)
            # Second-place contribution
            # P(i 2nd) = sum_{j != i} p_j * (p_i / (1 - p_j))
            #        = p_i * sum_{j != i} p_j / (1 - p_j)
            base_terms = pv / (1 - pv)
            total_base = base_terms.sum()
            second_contrib = pv * (total_base - base_terms)
            itm += second_contrib
            # Third-place contribution
            # P(i 3rd) = sum_{j != i, k distinct from i and j}
            #             p_j * (p_k / (1 - p_j)) * (p_i / (1 - p_j - p_k))
            # Vectorised: outer loop over j (first-place candidate).
            third_contrib = np.zeros(n)
            for j in range(n):
                pj = pv[j]
                one_minus_pj = 1 - pj
                if one_minus_pj <= 0:
                    continue
                pk = pv.copy()
                pk[j] = 0.0    # can't have k = j
                denom_ik = one_minus_pj - pv   # 1 - p_j - p_k, per k index
                safe_denom = np.where(denom_ik > 0, denom_ik, np.nan)
                per_k = pk / safe_denom
                per_k = np.nan_to_num(per_k, nan=0.0)
                sum_all_k = per_k.sum()
                # For each i, sum over k with k != i and k != j
                partial = sum_all_k - per_k        # excludes k = i
                contribution = pj / one_minus_pj * pv * partial
                contribution[j] = 0.0              # exclude i = j (can't be 1st AND 3rd)
                third_contrib += contribution
            itm += third_contrib
            out[idx] = np.clip(itm, 0.0, 1.0)
        return out

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Entry-level interface matching ``baselines.py`` shape.

        Uses per-race-normalised ``1 / (final_odds + 1)`` as p_win.
        """
        odds = features_df["final_odds"].to_numpy(dtype=float)
        rid = features_df["race_id"].to_numpy()
        raw = np.where((odds > 0) & np.isfinite(odds), 1.0 / (odds + 1.0), np.nan)
        # per-race normalize win probs
        s = pd.Series(raw)
        sums = s.groupby(rid).transform("sum").to_numpy()
        sums = np.where(sums > 0, sums, np.nan)
        p_win = raw / sums
        p_itm = self.predict_p_itm(p_win, rid)
        return pd.DataFrame({
            "entry_id": features_df["entry_id"].to_numpy(),
            "race_id": rid,
            "y_pred": p_itm,
        })


# ---- Self-test ------------------------------------------------------------

if __name__ == "__main__":
    # 8-horse race: 40% favourite, then descending
    df = pd.DataFrame({
        "entry_id": range(8),
        "race_id":  [1] * 8,
        "final_odds": [1.5, 2.5, 4.0, 6.0, 9.0, 15.0, 25.0, 40.0],
    })
    preds = MarketModelITM().predict(df)
    print(preds.to_string(index=False))
    # ITM total across race should be close to 3 (since 3 horses hit ITM)
    print(f"\nSum P(ITM) in race: {preds['y_pred'].sum():.3f} (expect ~3.0)")
    print(f"Favourite P(ITM): {preds['y_pred'].iloc[0]:.3f} (expect ~0.75+)")
