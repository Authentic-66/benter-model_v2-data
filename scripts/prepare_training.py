"""Preprocess entry_features_v1 into arrays ready for training.

Design decisions
----------------

* **Market vs fundamental split.** Six market features are held aside
  (they belong to the market model half of the Benter blend). Everything
  else is fed to the fundamental model.

* **Honest NULL handling.** Phase 3C's philosophy was "NULL means unknown,
  never impute lies". For linear models we still need numeric inputs, so:

    - For each column with any NULL values we add a companion binary flag
      ``{col}_missing`` = 1 where the value was NULL. The model can learn
      the missingness signal (e.g., first-time starters have distinctive
      priors) rather than being fooled by an imputed median.
    - After the flag is set, the NULL is filled with the training median
      (fit on train fold only — no leakage).

* **Categorical encoding.** Low-cardinality columns (surface, race_type,
  horse_sex, pace_type_last_race, horse_country_origin,
  track_condition) are one-hot encoded. Unknown categories at
  test time become an all-zero row for that field (silent, safe).

* **Standardisation.** Numeric columns are z-scored using train-fold
  statistics. The market model doesn't need scaling — it uses raw odds.

* **Time-decay training weights.** Each training entry gets weight
  ``0.5 ** ((train_end - race_date).days / half_life_days)``. Half-life is
  a hyperparameter (2y default).

Pipeline is pickle-able so a trained model can carry its preprocessor
forward for inference.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder


log = logging.getLogger("prepare_training")


# ---- What is a market feature? --------------------------------------------

MARKET_FEATURES: tuple[str, ...] = (
    "final_odds",
    "log_final_odds",
    "implied_probability",
    "is_favorite",
    "odds_rank_in_field",
    "odds_ratio_to_favorite",
)

# Categoricals to one-hot encode.
CATEGORICAL_FEATURES: tuple[str, ...] = (
    "surface",
    "track_condition",
    "race_type",
    "horse_sex",
    "horse_country_origin",
    "pace_type_last_race",
)

# Always-excluded columns (identifiers, targets, leaked)
NON_FEATURE_COLS: tuple[str, ...] = (
    "entry_id", "race_id", "horse_id", "trainer_id", "jockey_id",
)

# Horse-immutable features (Bucket 2) have a subtle look-ahead leak: in
# Phase 3A the DB loader only fills pedigree fields (sex, age, country, etc.)
# for horses that appear as a race winner. So ``horse_sex IS NOT NULL`` is
# effectively a proxy for "this horse will win at least once in the observed
# corpus" — information derived from future races. We exclude them from
# training until Phase 3H's multi-track expansion, at which point winner
# coverage rises and the leak becomes negligible.
LEAKY_FEATURES: tuple[str, ...] = (
    "horse_age",
    "horse_sex",
    "horse_country_origin",
    "is_florida_bred",
)


# ---- Data loading ---------------------------------------------------------

def load_full_frame(db_path: str | Path) -> pd.DataFrame:
    """Pull every row of ``entry_features_v1`` plus what we need for labels.

    If the optional ``entry_v10_flags`` table exists (produced by
    ``apply_v10_priors.py``), we join it in so the eight v10 signal
    columns become fundamental features. Absence of that table is not
    an error — the pipeline degrades to the Phase 3E feature set.
    """
    conn = sqlite3.connect(str(db_path))
    has_v10 = bool(conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='entry_v10_flags'"
    ).fetchone())
    if has_v10:
        query = """
            SELECT f.*, v.v10_sire_bet, v.v10_sire_fade,
                   v.v10_trainer_bet, v.v10_trainer_fade,
                   v.v10_jockey_bet, v.v10_jockey_fade,
                   v.v10_universal_fade, v.v10_signal_score,
                   e.finish_pos, rd.race_date
            FROM entry_features_v1 f
            LEFT JOIN entry_v10_flags v ON v.entry_id = f.entry_id
            JOIN entries e   ON e.id  = f.entry_id
            JOIN races  r    ON r.id  = e.race_id
            JOIN race_days rd ON rd.id = r.race_day_id
        """
    else:
        query = """
            SELECT f.*, e.finish_pos, rd.race_date
            FROM entry_features_v1 f
            JOIN entries e   ON e.id  = f.entry_id
            JOIN races  r    ON r.id  = e.race_id
            JOIN race_days rd ON rd.id = r.race_day_id
        """
    df = pd.read_sql_query(query, conn)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["y_true"] = (df["finish_pos"] == 1).astype(int)
    return df


# ---- Preprocessor ---------------------------------------------------------

@dataclass
class Preprocessor:
    """Fit-once, transform-many preprocessing pipeline.

    Fields captured at fit time:
        numeric_cols     : ordered list of numeric feature names
        categorical_cols : the subset of CATEGORICAL_FEATURES present
        medians          : per-numeric median from train fold
        means, stds      : per-numeric standardisation constants
        encoders         : OneHotEncoder objects keyed by column
        missing_cols     : numeric columns that had any NULL in training
        output_names     : the final ordered feature column names
    """

    numeric_cols: list[str] = field(default_factory=list)
    categorical_cols: list[str] = field(default_factory=list)
    medians: dict[str, float] = field(default_factory=dict)
    means: dict[str, float] = field(default_factory=dict)
    stds: dict[str, float] = field(default_factory=dict)
    encoders: dict[str, OneHotEncoder] = field(default_factory=dict)
    missing_cols: list[str] = field(default_factory=list)
    output_names: list[str] = field(default_factory=list)

    def fit(self, df: pd.DataFrame, feature_cols: Iterable[str]) -> "Preprocessor":
        feature_cols = list(feature_cols)
        self.numeric_cols = [
            c for c in feature_cols if c not in CATEGORICAL_FEATURES
            and pd.api.types.is_numeric_dtype(df[c])
        ]
        self.categorical_cols = [c for c in feature_cols if c in CATEGORICAL_FEATURES]

        for col in self.numeric_cols:
            series = df[col].astype(float)
            has_null = series.isna().any()
            if has_null:
                self.missing_cols.append(col)
            median = float(series.median()) if series.notna().any() else 0.0
            self.medians[col] = median
            filled = series.fillna(median)
            self.means[col] = float(filled.mean())
            self.stds[col] = float(filled.std(ddof=0)) or 1.0

        for col in self.categorical_cols:
            enc = OneHotEncoder(
                sparse_output=False,
                handle_unknown="ignore",
                dtype=np.float32,
            )
            # Reshape and treat missing as its own category
            vals = df[col].astype("object").fillna("__MISSING__").to_numpy().reshape(-1, 1)
            enc.fit(vals)
            self.encoders[col] = enc

        # Determine output column order
        output = []
        for col in self.numeric_cols:
            output.append(col)
        for col in self.missing_cols:
            output.append(f"{col}__missing")
        for col in self.categorical_cols:
            for cat in self.encoders[col].categories_[0]:
                output.append(f"{col}__{cat}")
        self.output_names = output
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        blocks = []
        # Numerics: fill NaN with median, standardise
        for col in self.numeric_cols:
            series = df[col].astype(float).fillna(self.medians[col])
            blocks.append(((series - self.means[col]) / self.stds[col]).to_numpy(dtype=np.float32))
        # Missingness flags
        for col in self.missing_cols:
            blocks.append(df[col].isna().astype(np.float32).to_numpy())
        # Categoricals: one-hot
        for col in self.categorical_cols:
            vals = df[col].astype("object").fillna("__MISSING__").to_numpy().reshape(-1, 1)
            blocks.append(self.encoders[col].transform(vals).astype(np.float32))

        X = np.column_stack(blocks) if blocks else np.zeros((len(df), 0), dtype=np.float32)
        return X


# ---- Feature-set split ----------------------------------------------------

def split_feature_columns(all_columns: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return ``(fundamental_cols, market_cols)`` from a feature frame.

    Anything in ``MARKET_FEATURES`` (that also exists) becomes market;
    everything else that's a feature becomes fundamental.

    ``LEAKY_FEATURES`` (horse-immutable pedigree columns whose non-null
    status is derived from future data — see the comment on
    ``LEAKY_FEATURES``) are also excluded.
    """
    all_columns = set(all_columns)
    market = [c for c in MARKET_FEATURES if c in all_columns]
    exclusions = set(NON_FEATURE_COLS) | set(MARKET_FEATURES) | set(LEAKY_FEATURES) | {
        "finish_pos", "race_date", "y_true"
    }
    fundamental = [c for c in all_columns if c not in exclusions]
    fundamental.sort()   # deterministic ordering
    return fundamental, market


# ---- Time-decay training weights ----------------------------------------

def time_decay_weights(
    race_dates: pd.Series,
    reference_date: str | pd.Timestamp,
    half_life_days: float,
) -> np.ndarray:
    """Exponential decay weight per training row.

    An entry ``half_life_days`` old from ``reference_date`` gets weight 0.5.
    Same-day / future rows get weight 1.0 (clamped).
    """
    dates = pd.to_datetime(race_dates)
    ref = pd.Timestamp(reference_date)
    age_days = (ref - dates).dt.days.clip(lower=0).to_numpy()
    return (0.5 ** (age_days / half_life_days)).astype(np.float32)


# ---- CLI demo -------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log.info("loading full frame …")
    df = load_full_frame("scripts/gp_full.db")
    log.info("  %d rows, %d cols", *df.shape)

    fundamental_cols, market_cols = split_feature_columns(df.columns)
    log.info("Fundamental features: %d", len(fundamental_cols))
    log.info("Market features:      %d", len(market_cols))

    # Fit + transform on the whole thing (just a shape check)
    pre = Preprocessor().fit(df, fundamental_cols)
    X = pre.transform(df)
    log.info("Design matrix: %s", X.shape)
    log.info("First 10 output feature names: %s", pre.output_names[:10])
    log.info("Time-decay demo (half-life 730d, ref 2026-04-01):")
    w = time_decay_weights(df["race_date"], "2026-04-01", 730)
    log.info("  weight range [%.3f, %.3f], mean %.3f", w.min(), w.max(), w.mean())
