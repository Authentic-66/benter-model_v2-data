"""Slice-based diagnostics — where does the model win, and where does it lose?

Given a predictions_df (from ``evaluate``-friendly shape) plus the raw
features_df, break performance down by:

    race_type          — CLAIMING / ALLOWANCE / STAKES / MAIDEN…
    surface            — Dirt / Turf / AllWeather
    distance_category  — sprint (< 7f), mid (7-8.5f), route (> 8.5f)
    field_size_bucket  — small (<=6), medium (7-9), large (>=10)
    track_condition    — fast / off-track (Sloppy, Muddy, WetFast, Good, Yielding)
    favorite_bucket    — favorite (top-2 odds), midpack (3-5), longshot (6+)

Each slice returns the full metric bundle so we can spot where the model
diverges from average — critical for iteration ("model is great on turf
sprints but terrible on off-turf routes").

The module is model-agnostic — it works on any prediction the metrics
module can score.

Usage
-----
    diag = SliceDiagnostics(features_df, predictions_df)
    report = diag.run()             # one row per (slice_column, slice_value)
    turf = diag.run(slice_by=["surface"])
    print(diag.compare_to_baseline(baseline_preds))
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from metrics import evaluate


log = logging.getLogger("diagnostics")


# Default sets of slices we always want to look at.
DEFAULT_SLICES = (
    "race_type", "surface", "distance_category",
    "field_size_bucket", "track_condition_bucket", "favorite_bucket",
)


def _bucket_distance(yards) -> str | None:
    if pd.isna(yards):
        return None
    f = yards / 220.0
    if f < 7.0:
        return "sprint"
    if f <= 8.5:
        return "mid"
    return "route"


def _bucket_field_size(fs) -> str | None:
    if pd.isna(fs):
        return None
    if fs <= 6:
        return "small"
    if fs <= 9:
        return "medium"
    return "large"


def _bucket_condition(cond) -> str | None:
    if not isinstance(cond, str):
        return None
    if cond in ("Fast", "Firm"):
        return "fast"
    return "off_track"


def _bucket_favorite(odds_rank) -> str | None:
    if pd.isna(odds_rank):
        return None
    r = int(odds_rank)
    if r <= 2:
        return "favorite"
    if r <= 5:
        return "midpack"
    return "longshot"


def enrich_with_slices(features_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``features_df`` with slice columns attached.

    Missing raw columns (distance_yards, surface, ...) leave the slice
    column NaN — the diagnostics group-by silently drops NaN slices.
    """
    out = features_df.copy()
    if "distance_yards" in out.columns:
        out["distance_category"] = out["distance_yards"].map(_bucket_distance)
    if "field_size" in out.columns:
        out["field_size_bucket"] = out["field_size"].map(_bucket_field_size)
    if "track_condition" in out.columns:
        out["track_condition_bucket"] = out["track_condition"].map(_bucket_condition)
    # odds_rank_in_field is already in entry_features_v1
    if "odds_rank_in_field" in out.columns:
        out["favorite_bucket"] = out["odds_rank_in_field"].map(_bucket_favorite)
    return out


@dataclass
class SliceDiagnostics:
    """Slice a set of predictions by common race categories."""

    features_df: pd.DataFrame
    predictions_df: pd.DataFrame       # must have entry_id, race_id, y_pred, y_true, final_odds

    def __post_init__(self):
        need = {"entry_id", "race_id", "y_pred", "y_true", "final_odds"}
        missing = need - set(self.predictions_df.columns)
        if missing:
            raise ValueError(f"predictions_df missing columns: {missing}")
        self._enriched = enrich_with_slices(self.features_df)
        # Left-align enriched slices to predictions
        keep_cols = ["entry_id"] + list(DEFAULT_SLICES)
        keep_cols = [c for c in keep_cols if c in self._enriched.columns]
        self._joined = self.predictions_df.merge(
            self._enriched[keep_cols], on="entry_id", how="left"
        )

    def _score_slice(self, sub: pd.DataFrame) -> dict[str, float]:
        if len(sub) == 0:
            return {"n_entries": 0}
        return {"n_entries": len(sub), **evaluate(sub)}

    def run(
        self,
        slice_by: Iterable[str] = DEFAULT_SLICES,
        include_overall: bool = True,
    ) -> pd.DataFrame:
        """Return one row per (slice_column, slice_value) with metrics.

        Slices whose column isn't in the joined frame are silently skipped;
        NaN slice values are also skipped.
        """
        rows: list[dict] = []
        if include_overall:
            rows.append({"slice_column": "OVERALL", "slice_value": "all",
                         **self._score_slice(self._joined)})
        for col in slice_by:
            if col not in self._joined.columns:
                log.debug("slice column %s missing, skipping", col)
                continue
            for value, sub in self._joined.groupby(col, dropna=True):
                rows.append({"slice_column": col, "slice_value": value,
                             **self._score_slice(sub)})
        df = pd.DataFrame(rows)
        # Reorder columns
        first_cols = ["slice_column", "slice_value", "n_entries"]
        metric_cols = [c for c in df.columns if c not in first_cols]
        return df[first_cols + metric_cols]

    def compare_to_baseline(
        self,
        baseline_predictions_df: pd.DataFrame,
        slice_by: Iterable[str] = DEFAULT_SLICES,
    ) -> pd.DataFrame:
        """Compute delta metrics vs a baseline, per slice.

        Positive ``roi`` delta means the current predictions beat the baseline
        by that much ROI in the slice; positive ``log_loss`` delta means WORSE.
        The returned frame has columns ``metric_name_delta`` alongside the
        raw current and baseline values.
        """
        curr = self.run(slice_by=slice_by).set_index(["slice_column", "slice_value"])
        baseline_diag = SliceDiagnostics(self.features_df, baseline_predictions_df)
        base = baseline_diag.run(slice_by=slice_by).set_index(["slice_column", "slice_value"])
        common_metric_cols = [c for c in curr.columns
                               if c in base.columns and c != "n_entries"]
        out = curr[["n_entries"]].copy()
        for m in common_metric_cols:
            out[f"{m}_curr"] = curr[m]
            out[f"{m}_base"] = base[m]
            out[f"{m}_delta"] = curr[m] - base[m]
        return out.reset_index()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Quick synthetic smoke test."""
    # Reuse the grid-search dummy dataset for coverage
    rng = np.random.default_rng(0)
    rows = []
    for i in range(100):  # 100 races
        surface = rng.choice(["Dirt", "Turf", "AllWeather"])
        cond = "Fast" if surface != "Turf" else rng.choice(["Firm", "Good"])
        dist = int(rng.choice([1210, 1540, 1760, 1870]))
        fs = int(rng.integers(5, 12))
        odds = rng.uniform(1, 20, size=fs)
        winner = int(np.argmin(odds))
        for h in range(fs):
            rows.append({
                "entry_id": len(rows),
                "race_id": i,
                "final_odds": odds[h],
                "y_true": int(h == winner),
                "distance_yards": dist,
                "surface": surface,
                "track_condition": cond,
                "field_size": fs,
                "race_type": rng.choice(["CLAIMING", "ALLOWANCE", "STAKES"]),
                "odds_rank_in_field": h + 1,   # crude
                # Predictions: use market implied prob
                "y_pred": 1.0 / (odds[h] + 1.0),
            })
    df = pd.DataFrame(rows)
    features = df.drop(columns=["y_pred"])
    preds = df[["entry_id", "race_id", "y_pred", "y_true", "final_odds"]]

    diag = SliceDiagnostics(features, preds)
    report = diag.run()
    print("Diagnostic slices:")
    print(report[["slice_column", "slice_value", "n_entries",
                  "log_loss_per_race", "hit_rate_top1", "favorite_hit_rate"]]
          .round(4).to_string(index=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    _self_test()
