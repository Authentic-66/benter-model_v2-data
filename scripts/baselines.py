"""Baseline predictors for Phase 3D.

Every baseline exposes the same tiny API::

    class MyBaseline:
        name: str
        def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
            '''Return a predictions_df with y_pred column.'''

The predictions_df returned always contains at minimum
``entry_id, race_id, y_pred`` — the caller merges ``y_true`` and ``final_odds``
from the source data before scoring.

Baselines
---------

* :class:`BaselineFavorite` — assigns the market implied probability to each
  horse; the model IS the market. This is the "beat the crowd" bar.
* :class:`BaselineRandom` — uniform 1/field_size. This is the "beat coin
  flip" bar; anything worse than this is broken.
* :class:`BaselineOldModel` — reads a CSV of predictions from the previous
  version of Doug's PP-based workbook. Stubbed for now; Doug plugs in a
  file path once he exports the old model's predictions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd


class Predictor(Protocol):
    """Every baseline / model exposes this shape."""

    name: str

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        ...


REQUIRED_INPUT = ("entry_id", "race_id")


def _validate_input(df: pd.DataFrame, extra: tuple[str, ...] = ()) -> None:
    missing = [c for c in REQUIRED_INPUT + extra if c not in df.columns]
    if missing:
        raise ValueError(f"features_df missing columns: {missing}")


# ---------------------------------------------------------------------------
# Market Favorite
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselineFavorite:
    """Predict market implied probability.

    Given tote odds ``o`` (e.g. 2.20), the pre-takeout implied probability
    is ``1 / (o + 1)``. Per-race normalisation is done inside the metrics
    module, so this baseline emits raw implied probs and lets the scoring
    layer handle the renormalisation.

    This baseline is what any fundamental model must beat. If the model
    can't outperform the market on the metrics we care about, it isn't
    finding new information.
    """

    name: str = "market_favorite"

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        _validate_input(features_df, extra=("final_odds",))
        odds = features_df["final_odds"].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            p = 1.0 / (odds + 1.0)
        p = np.where(np.isfinite(p) & (odds > 0), p, np.nan)
        return pd.DataFrame({
            "entry_id": features_df["entry_id"].to_numpy(),
            "race_id": features_df["race_id"].to_numpy(),
            "y_pred": p,
        })


# ---------------------------------------------------------------------------
# Random / uniform
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselineRandom:
    """Uniform 1/field_size — a proper coin-flip baseline for horse racing.

    Beating this on log-loss is trivial for any model with any signal at all;
    it defines the floor.
    """

    name: str = "random_uniform"

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        _validate_input(features_df)
        sizes = (features_df.groupby("race_id")["entry_id"]
                            .transform("count").to_numpy(dtype=float))
        return pd.DataFrame({
            "entry_id": features_df["entry_id"].to_numpy(),
            "race_id": features_df["race_id"].to_numpy(),
            "y_pred": 1.0 / sizes,
        })


# ---------------------------------------------------------------------------
# Old workbook model (stub)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselineOldModel:
    """Load predictions from Doug's previous PP-based workbook.

    The old model lives in ``Previous Versions of Benter Model/`` as an
    Excel workbook. Extracting its predictions is a manual step Doug will
    do (or Phase 3F will automate). Until then, provide a CSV with columns:

        entry_id, y_pred

    at construction time. Missing entries return NaN.

    Usage::

        old = BaselineOldModel(predictions_csv="old_model_preds.csv")
        preds = old.predict(features_df)
    """

    name: str = "old_workbook_model"
    predictions_csv: str | None = None

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        _validate_input(features_df)
        if self.predictions_csv is None or not Path(self.predictions_csv).exists():
            # Stub mode — emit NaN so evaluation shows "not available"
            # rather than crashing the caller.
            return pd.DataFrame({
                "entry_id": features_df["entry_id"].to_numpy(),
                "race_id": features_df["race_id"].to_numpy(),
                "y_pred": np.full(len(features_df), np.nan),
            })
        preds = pd.read_csv(self.predictions_csv, usecols=["entry_id", "y_pred"])
        merged = features_df[list(REQUIRED_INPUT)].merge(
            preds, on="entry_id", how="left"
        )
        return merged


# ---------------------------------------------------------------------------
# Combine features with actuals to produce a scoring-ready DataFrame
# ---------------------------------------------------------------------------

def build_scoring_frame(
    features_df: pd.DataFrame,
    predictor: Predictor,
    y_true: pd.Series | None = None,
    final_odds: pd.Series | None = None,
) -> pd.DataFrame:
    """Combine a predictor's output with actuals into a scoring frame.

    ``features_df`` must have entry_id + race_id + final_odds (for BaselineFavorite).
    If ``y_true`` / ``final_odds`` are omitted we try to pull them from
    ``features_df`` (they're in entry_features_v1).
    """
    preds = predictor.predict(features_df)
    frame = preds.merge(features_df[["entry_id"]], on="entry_id", how="left")

    if y_true is None:
        if "y_true" not in features_df.columns:
            raise ValueError(
                "features_df must include 'y_true' or you must pass it explicitly"
            )
        y_true = features_df["y_true"]
    if final_odds is None:
        if "final_odds" not in features_df.columns:
            raise ValueError(
                "features_df must include 'final_odds' or you must pass it explicitly"
            )
        final_odds = features_df["final_odds"]

    # Align by entry_id
    idx = features_df.set_index("entry_id")
    frame = frame.set_index("entry_id")
    frame["y_true"] = idx.loc[frame.index, "y_true"] if "y_true" in idx.columns else y_true.values
    frame["final_odds"] = idx.loc[frame.index, "final_odds"] if "final_odds" in idx.columns else final_odds.values
    return frame.reset_index()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Tiny demo
    df = pd.DataFrame({
        "entry_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "race_id":  [1, 1, 1, 1, 2, 2, 2, 2],
        "final_odds": [1.5, 3.0, 6.0, 12.0, 2.0, 4.0, 9.0, 20.0],
        "y_true":     [1, 0, 0, 0, 0, 1, 0, 0],
    })
    for cls in (BaselineFavorite, BaselineRandom, BaselineOldModel):
        b = cls()
        print(f"\n{b.name}:")
        print(b.predict(df).to_string(index=False))
