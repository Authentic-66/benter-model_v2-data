"""Exponential time-decay weighting.

Two use cases:

  1. **Training loss weighting.** When fitting a model on races spanning
     multiple years, recent races should count more than old ones because
     conditions drift (trainer patterns change, jockey pool turnover, track
     surface renewal, etc.). Applied via weighted log-loss.

  2. **Aggregate feature computation.** When computing e.g. a trainer's
     rolling 365-day win rate, a race 300 days ago is less informative than
     one 30 days ago. Decay-weighted counts smooth the transition.

Formula
-------
    weight = 0.5 ** ((today - race_date).days / half_life_days)

At `age = half_life`, weight = 0.5. At `age = 2 * half_life`, weight = 0.25.

Half-life defaults (per Phase 3C spec):
    - training loss weighting:            730 days (2 years)
    - aggregate stats (rolling windows):  180 days

Both are configurable and will be tuned in Phase 3D validation.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

import numpy as np
import pandas as pd


HALF_LIFE_TRAINING = 730     # 2 years — training-loss weighting
HALF_LIFE_AGGREGATE = 180    # 6 months — rolling-stat weighting


def _to_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).date()
    raise TypeError(f"cannot coerce to date: {value!r}")


def decay_weight(race_date, current_date, half_life_days: int) -> float:
    """Exponential decay weight for a single race.

    >>> decay_weight("2024-06-30", "2026-06-30", 730)
    0.5
    >>> round(decay_weight("2022-06-30", "2026-06-30", 730), 3)
    0.25
    >>> decay_weight("2026-06-30", "2026-06-30", 730)
    1.0
    """
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    d1 = _to_date(race_date)
    d2 = _to_date(current_date)
    age_days = max((d2 - d1).days, 0)
    return 0.5 ** (age_days / half_life_days)


def decay_weight_vec(
    race_dates: Iterable, current_date, half_life_days: int
) -> np.ndarray:
    """Vectorized decay weights over a pandas/numpy series of dates."""
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    rd = pd.to_datetime(pd.Series(list(race_dates)))
    cd = pd.Timestamp(_to_date(current_date))
    age_days = (cd - rd).dt.days.clip(lower=0).to_numpy()
    return 0.5 ** (age_days / half_life_days)


def decayed_sum(
    values: Iterable[float],
    race_dates: Iterable,
    current_date,
    half_life_days: int,
) -> float:
    """Sum of `values`, each weighted by decay from `current_date`.

    Common uses:
        - decayed_sum(wins,   dates, today, 180) → decay-weighted wins
        - decayed_sum(starts, dates, today, 180) → decay-weighted starts

    A decay-weighted rate is then decayed_sum(wins) / decayed_sum(starts).

    >>> round(decayed_sum([1, 1, 1], ["2026-06-30", "2024-06-30", "2022-06-30"],
    ...                   "2026-06-30", 730), 3)
    1.75
    """
    weights = decay_weight_vec(race_dates, current_date, half_life_days)
    return float(np.sum(np.asarray(list(values), dtype=float) * weights))


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
    print("\nDemo — trainer 365-day rolling win rate with 180-day decay:")
    dates = ["2026-06-25", "2026-06-01", "2026-05-01", "2026-01-01",
             "2025-08-01", "2025-01-01"]
    wins  = [1, 0, 1, 0, 1, 0]
    today = "2026-06-30"
    ds = decayed_sum([1] * len(dates), dates, today, 180)
    dw = decayed_sum(wins, dates, today, 180)
    print(f"  decay-weighted starts: {ds:.2f}")
    print(f"  decay-weighted wins:   {dw:.2f}")
    print(f"  decay-weighted rate:   {dw / ds:.4f}   "
          f"(vs raw {sum(wins) / len(wins):.4f})")
