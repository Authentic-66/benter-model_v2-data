"""Market model — takeout-corrected implied probabilities from tote odds.

Given tote odds ``o``, the raw implied probability is ``p = 1 / (o + 1)``.
Summed across a race, these probs exceed 1.0 by the track takeout (US
racing is ~15-18%). We renormalise per race to remove the overround, so the
per-race probabilities sum to 1.0 exactly.

This is the Benter model's ``g(o)`` half. It's not learned — it's a direct
transform of the market data. The learning happens in the blend layer.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MarketModel:
    """No-parameter model that returns per-race normalised market probs."""

    name: str = "market_implied"

    def predict_race_probabilities(
        self, final_odds: np.ndarray, race_ids: np.ndarray
    ) -> np.ndarray:
        """Return per-race-normalised implied probabilities.

        NaN or non-positive odds -> per-entry NaN. Their race can still be
        normalised over the remaining valid entries; if the entire race is
        invalid, all entries in that race become NaN.
        """
        odds = np.asarray(final_odds, dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = 1.0 / (odds + 1.0)
        raw = np.where(np.isfinite(raw) & (odds > 0), raw, np.nan)

        raw_series = pd.Series(raw)
        rid_series = pd.Series(race_ids)
        # Per-race sum of the valid slice
        sum_per_race = raw_series.groupby(rid_series).transform("sum").to_numpy()
        sum_per_race = np.where(sum_per_race > 0, sum_per_race, np.nan)
        return raw / sum_per_race

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Baselines-style interface: input has entry_id/race_id/final_odds."""
        p = self.predict_race_probabilities(
            features_df["final_odds"].to_numpy(),
            features_df["race_id"].to_numpy(),
        )
        return pd.DataFrame({
            "entry_id": features_df["entry_id"].to_numpy(),
            "race_id": features_df["race_id"].to_numpy(),
            "y_pred": p,
        })


# ---- Self-test ------------------------------------------------------------

if __name__ == "__main__":
    df = pd.DataFrame({
        "entry_id": [1, 2, 3, 4, 5, 6],
        "race_id":  [1, 1, 1, 2, 2, 2],
        "final_odds": [1.0, 3.0, 9.0, 2.0, 5.0, 20.0],
    })
    p = MarketModel().predict(df)
    p["sum_per_race"] = p.groupby("race_id")["y_pred"].transform("sum")
    print(p.to_string(index=False))
    assert np.allclose(p.groupby("race_id")["y_pred"].sum(), 1.0)
    print("ok — per-race sums are 1.0")
