"""Preprocess entry_features_v1 for the ITM (top-3) target.

Differences vs the v2 counterpart in ``scripts/prepare_training.py``:

* **Target.** ``y_true`` is ``1`` iff ``finish_pos <= 3`` (in-the-money),
  not ``finish_pos == 1``. About 33% of entries are positive vs ~13% in
  v2 — a much denser signal for a binary logistic model.

* **Training scope.** We filter to ``race_date >= '2022-01-01'``. Per
  Doug's Phase 3G scope note, the 2019-2021 corpus predates HISA and
  reflects a different racing environment (Golden Gate open, Aqueduct
  changes, older trainer/jockey generation). Still Benter-scale
  (~8,600 races, ~66k entries).

* **Feature set unchanged.** Same 67 fundamental features + 8 v10 flag
  columns + 6 market features. ``LEAKY_FEATURES`` guard preserved.

Reuses everything else from the v2 module via import so future refactors
propagate in one place.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Reuse Preprocessor, MARKET_FEATURES, split_feature_columns, time_decay_weights
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_training import (  # noqa: E402
    Preprocessor,
    MARKET_FEATURES,
    NON_FEATURE_COLS,
    LEAKY_FEATURES,
    CATEGORICAL_FEATURES,
    split_feature_columns,
    time_decay_weights,
)


log = logging.getLogger("prepare_training_v2a")

# v2a scope: HISA-era only, Doug's decision
TRAIN_DATE_MIN = "2022-01-01"


def load_full_frame(
    db_path: str | Path, date_min: str = TRAIN_DATE_MIN,
) -> pd.DataFrame:
    """Pull every row of ``entry_features_v1`` from the 2022+ window.

    Same shape as ``prepare_training.load_full_frame`` but the label is
    the ITM indicator and the frame is date-filtered.
    """
    conn = sqlite3.connect(str(db_path))
    has_v10 = bool(conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='entry_v10_flags'"
    ).fetchone())
    v10_cols = (
        """, v.v10_sire_bet, v.v10_sire_fade, v.v10_trainer_bet,
              v.v10_trainer_fade, v.v10_jockey_bet, v.v10_jockey_fade,
              v.v10_universal_fade, v.v10_signal_score"""
        if has_v10 else ""
    )
    v10_join = (
        "LEFT JOIN entry_v10_flags v ON v.entry_id = f.entry_id"
        if has_v10 else ""
    )
    df = pd.read_sql_query(
        f"""
        SELECT f.*{v10_cols},
               e.finish_pos, rd.race_date
        FROM entry_features_v1 f
        {v10_join}
        JOIN entries e    ON e.id = f.entry_id
        JOIN races  r     ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE rd.race_date >= ?
        """,
        conn,
        params=(date_min,),
    )
    df["race_date"] = pd.to_datetime(df["race_date"])
    # ITM target: top-3 finish
    df["y_true"] = (df["finish_pos"] <= 3).astype(int)
    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    df = load_full_frame("scripts/gp_full.db")
    log.info("Loaded %d entries across %d races",
             len(df), df["race_id"].nunique())
    log.info("ITM positive rate: %.4f (v2 win rate would be ~0.125)",
             df["y_true"].mean())

    fund_cols, market_cols = split_feature_columns(df.columns)
    log.info("Fundamental cols: %d", len(fund_cols))
    log.info("Market cols:      %d", len(market_cols))
    log.info("v10 fund cols:    %s",
             [c for c in fund_cols if c.startswith("v10_")])

    pre = Preprocessor().fit(df, fund_cols)
    X = pre.transform(df)
    log.info("Design matrix: %s", X.shape)
