"""Bayesian shrinkage for rate features.

The core problem: a trainer with 2 wins from 3 starts is not a 66.7% win-rate
trainer — we don't have enough evidence. Empirical Bayes ("shrinkage")
combines the sample rate with a prior belief to produce a stable estimate.

Formula
-------
    shrunk = (numerator + k * prior_rate) / (denominator + k)

Where:
    numerator     — event count (e.g. wins, in-the-money finishes)
    denominator   — trial count (e.g. starts)
    prior_rate    — population base rate (e.g. overall 12% win rate)
    k             — "prior sample size", how much the prior counts

Intuition: at denominator=0, result is exactly prior_rate. As denominator
grows, the sample rate dominates. At denominator=k, the estimate is the
average of prior and sample.

Default k values (per Doug's Phase 3C spec):
  - trainer_overall:      20
  - trainer_at_track:     30
  - trainer_at_surface:   25
  - trainer_at_distance:  30
  - jockey_overall:       20
  - jockey_at_track:      30
  - trainer_jockey_combo: 25
  - horse_career:         15
  - speed_par_time:       50

These are starting points to be tuned during Phase 3D validation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


DEFAULT_K = {
    "trainer_overall": 20,
    "trainer_at_track": 30,
    "trainer_at_surface": 25,
    "trainer_at_distance": 30,
    "trainer_jockey_combo": 25,
    "jockey_overall": 20,
    "jockey_at_track": 30,
    "jockey_at_surface": 25,
    "jockey_at_distance": 30,
    "horse_career": 15,
    "speed_par_time": 50,
}


def shrink_rate(
    numerator: float | int | None,
    denominator: float | int | None,
    prior_rate: float,
    k: float,
) -> float | None:
    """Return the shrunk rate estimate.

    Returns None if `denominator` is None or NaN — we prefer NULL over a
    made-up value when no trials have been observed at all. Note: a
    denominator of 0 (trainer has done N races BUT not in this cell) still
    yields the prior, which is the correct "no evidence" answer for that
    cell.

    Args:
        numerator: event count (wins). If None, treated as 0.
        denominator: trial count (starts). None → returns None (unknown).
        prior_rate: population base rate in [0, 1].
        k: prior weight in the same units as denominator.

    Examples:
        >>> round(shrink_rate(2, 3, prior_rate=0.12, k=20), 4)
        0.1913
        >>> shrink_rate(0, 0, prior_rate=0.12, k=20)
        0.12
        >>> shrink_rate(None, None, prior_rate=0.12, k=20)  # unknown
    """
    if denominator is None or (isinstance(denominator, float) and np.isnan(denominator)):
        return None
    if numerator is None or (isinstance(numerator, float) and np.isnan(numerator)):
        numerator = 0
    if not (0.0 <= prior_rate <= 1.0):
        raise ValueError(f"prior_rate must be in [0,1], got {prior_rate}")
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    return (float(numerator) + k * prior_rate) / (float(denominator) + k)


def shrink_rate_vec(
    numerator: np.ndarray,
    denominator: np.ndarray,
    prior_rate: float | np.ndarray,
    k: float,
) -> np.ndarray:
    """Vectorized shrinkage — pandas/numpy friendly. NaN denominators → NaN.

    NaN in denominator means "unknown", so we preserve NaN. Zero denominator
    is a valid state ("no trials in cell") and produces the prior_rate.
    """
    num = np.where(np.isnan(numerator), 0.0, numerator).astype(float)
    den = denominator.astype(float)
    with np.errstate(invalid="ignore"):
        result = (num + k * np.asarray(prior_rate, dtype=float)) / (den + k)
    return np.where(np.isnan(den), np.nan, result)


@dataclass(frozen=True)
class ShrinkageSpec:
    """Named shrinkage configuration for readability at call sites."""

    name: str
    prior_rate: float
    k: float

    def shrink(self, numerator, denominator):
        return shrink_rate(numerator, denominator, self.prior_rate, self.k)

    def shrink_vec(self, numerator, denominator):
        return shrink_rate_vec(numerator, denominator, self.prior_rate, self.k)


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
    # Quick sanity demo
    print("\nDemo:")
    for wins, starts in [(0, 0), (0, 3), (1, 3), (5, 20), (20, 100), (100, 500)]:
        print(f"  wins={wins:>3}, starts={starts:>3}: "
              f"raw={wins/max(starts,1):.3f}  "
              f"shrunk_k20_prior0.12={shrink_rate(wins, starts, 0.12, 20):.3f}")
