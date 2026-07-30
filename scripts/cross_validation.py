"""Temporal cross-validation splitters.

Horse-racing data is time-ordered — a model must never see a race from the
future in its training set, or its validation numbers will be optimistic
lies. This module provides splitters that respect chronology.

Two tools:

* :class:`RollingOriginSplitter` — the tuning-time CV. Each fold trains on
  everything before a cutoff date and validates on a windowed slice after.
  Yields ``(train_idx, val_idx)`` pairs of positional NumPy indices.

* :class:`TemporalHoldout` — the ship-day check. Carves the most recent slice
  of the data off as an untouched final test set. You touch it once, at the
  end, to publish honest numbers.

Both operate on a pandas DataFrame with a date column; the splitter never
mutates the input.

Usage
-----
    df = pd.read_sql_query("SELECT ... FROM entry_features_v1 ...", conn)
    df["race_date"] = pd.to_datetime(df["race_date"])

    cv = RollingOriginSplitter.default_gp_folds()
    for fold_name, train_idx, val_idx in cv.split(df):
        train, val = df.iloc[train_idx], df.iloc[val_idx]
        ...

    holdout = TemporalHoldout(cutoff="2026-04-01")
    dev_df, test_df = holdout.split(df)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Iterator

import numpy as np
import pandas as pd


DateLike = str | date | datetime | pd.Timestamp


def _to_ts(value: DateLike) -> pd.Timestamp:
    return pd.Timestamp(value)


@dataclass(frozen=True)
class Fold:
    """One rolling-origin fold. Dates are inclusive of ``train_end`` and
    exclusive of ``val_end`` (the standard [start, end) convention)."""

    name: str
    train_start: pd.Timestamp | None   # None = use earliest available
    train_end: pd.Timestamp             # train uses dates STRICTLY BEFORE this
    val_start: pd.Timestamp             # val uses dates >= this
    val_end: pd.Timestamp               # val uses dates STRICTLY BEFORE this

    def describe(self) -> str:
        ts = self.train_start.date() if self.train_start else "beginning"
        return (
            f"{self.name}: train [{ts} ->{self.train_end.date()}), "
            f"val [{self.val_start.date()} ->{self.val_end.date()})"
        )


class RollingOriginSplitter:
    """Yields temporal train/val fold indices.

    Each fold trains on data BEFORE ``fold.train_end`` and validates on data
    in ``[fold.val_start, fold.val_end)``. There is no overlap between the
    training and validation windows: for horse racing we treat the same-day
    boundary as exclusive on the training side, so a race on
    ``fold.train_end`` will not be seen by the training set.

    Rows with dates outside the union of any fold are silently ignored (this
    is common when the corpus contains pre-training-era data).
    """

    def __init__(self, folds: Iterable[Fold]):
        self._folds = list(folds)
        if not self._folds:
            raise ValueError("at least one fold required")
        for f in self._folds:
            if f.train_start is not None and f.train_start >= f.train_end:
                raise ValueError(f"{f.name}: train_start must precede train_end")
            if f.val_start >= f.val_end:
                raise ValueError(f"{f.name}: val_start must precede val_end")
            if f.val_start < f.train_end:
                raise ValueError(
                    f"{f.name}: val window overlaps training window "
                    f"({f.val_start} < {f.train_end})"
                )

    @property
    def n_folds(self) -> int:
        return len(self._folds)

    def folds(self) -> list[Fold]:
        return list(self._folds)

    def split(
        self, df: pd.DataFrame, date_col: str = "race_date"
    ) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
        """Yield ``(fold_name, train_idx, val_idx)`` for each fold.

        Indices are 0-based positional (usable with ``df.iloc[...]``), not
        DataFrame labels. Both index arrays are sorted ascending.
        """
        dates = pd.to_datetime(df[date_col])
        for fold in self._folds:
            train_mask = dates < fold.train_end
            if fold.train_start is not None:
                train_mask &= dates >= fold.train_start
            val_mask = (dates >= fold.val_start) & (dates < fold.val_end)
            train_idx = np.flatnonzero(train_mask.to_numpy())
            val_idx = np.flatnonzero(val_mask.to_numpy())
            yield fold.name, train_idx, val_idx

    @classmethod
    def default_gp_folds(cls) -> "RollingOriginSplitter":
        """Phase 3D's spec'd four-fold plan for the GP corpus.

        - Fold 1: train pre-2024, val 2024
        - Fold 2: train pre-2025, val 2025
        - Fold 3: train pre-2026, val 2026 Q1 (Jan-Mar)
        - Fold 4: train pre-2026 Q2, val 2026 Q2 (Apr-Jun)
        """
        return cls([
            Fold(
                name="fold1_val2024",
                train_start=None,
                train_end=_to_ts("2024-01-01"),
                val_start=_to_ts("2024-01-01"),
                val_end=_to_ts("2025-01-01"),
            ),
            Fold(
                name="fold2_val2025",
                train_start=None,
                train_end=_to_ts("2025-01-01"),
                val_start=_to_ts("2025-01-01"),
                val_end=_to_ts("2026-01-01"),
            ),
            Fold(
                name="fold3_val2026Q1",
                train_start=None,
                train_end=_to_ts("2026-01-01"),
                val_start=_to_ts("2026-01-01"),
                val_end=_to_ts("2026-04-01"),
            ),
            Fold(
                name="fold4_val2026Q2",
                train_start=None,
                train_end=_to_ts("2026-04-01"),
                val_start=_to_ts("2026-04-01"),
                val_end=_to_ts("2026-07-01"),
            ),
        ])

    def describe(self) -> str:
        return "\n".join(f.describe() for f in self._folds)


@dataclass(frozen=True)
class TemporalHoldout:
    """Carves off the most recent slice of the data as an untouched test set.

    Use this AT MOST ONCE per project. If you evaluate on the holdout while
    tuning, you've silently overfit to it and your final numbers are lies.

    Common pattern:

        holdout = TemporalHoldout(cutoff="2026-04-01")
        dev_df, test_df = holdout.split(df)
        # do all your development on dev_df
        # touch test_df exactly once, on ship day.

    Note: the default GP fold plan ALREADY covers most of the data. If you
    want a strict never-touched holdout, hold out something later than the
    latest fold (e.g. cutoff="2026-06-01" with fold4 val_end at 2026-06-01).
    """

    cutoff: pd.Timestamp

    def __init__(self, cutoff: DateLike):
        object.__setattr__(self, "cutoff", _to_ts(cutoff))

    def split(
        self, df: pd.DataFrame, date_col: str = "race_date"
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return ``(dev_df, test_df)``. Rows on ``cutoff`` go to test.

        Both frames are returned as views/copies of the original — no index
        alignment surprises."""
        dates = pd.to_datetime(df[date_col])
        dev = df[dates < self.cutoff].copy()
        test = df[dates >= self.cutoff].copy()
        return dev, test


# ---------------------------------------------------------------------------
# CLI / self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Verify folds are time-respecting on synthetic data.

    >>> _self_test()
    ok
    """
    # 100 races, one per day, running from 2023-06-01 through 2026-06-08
    dates = pd.date_range("2023-06-01", periods=1100)
    df = pd.DataFrame({"race_date": dates, "row_idx": range(len(dates))})
    cv = RollingOriginSplitter.default_gp_folds()

    for name, tr, vl in cv.split(df):
        max_train = df.iloc[tr]["race_date"].max() if len(tr) else None
        min_val = df.iloc[vl]["race_date"].min() if len(vl) else None
        if max_train is not None and min_val is not None:
            assert max_train < min_val, (
                f"{name}: train max {max_train} >= val min {min_val} — LEAK"
            )
        assert not set(tr) & set(vl), f"{name}: index overlap"

    holdout = TemporalHoldout("2026-04-01")
    dev, test = holdout.split(df)
    assert dev["race_date"].max() < holdout.cutoff
    assert test["race_date"].min() >= holdout.cutoff
    print("ok")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=False)
    print("\nDefault GP CV folds:")
    print(RollingOriginSplitter.default_gp_folds().describe())
    print()
    _self_test()
