"""Why did the blend weight alpha FALL when the features were corrected?

Phase 4B.1 found that fixing the row-alignment bug *reduced* the fundamental
model's blend weight (v2a: alpha 0.172 -> 0.077). That looks backwards —
correct features should be worth more, not less.

Two competing explanations:

  (A) The corrected features are simply worse predictors.
  (B) The corrected features are BETTER predictors, but of exactly what the
      market already prices. A fundamental that agrees with the market more
      closely is more collinear with it, so the blend needs less weight on
      it to reach the same fit — beta absorbs the contribution instead.

These make opposite predictions that are cheap to check on a single fold:

               |  fundamental standalone log-loss  |  corr(logit p_f, logit p_m)
    (A) worse  |          goes UP (worse)          |         flat or down
    (B) redund.|         goes DOWN (better)        |            goes UP

This script fits the fundamental model on the pre-fix features and on the
post-fix features over the same fold and reports both quantities.

Usage
-----
    python scripts/diagnose_alpha_shift.py --db scripts/gp_full.db
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_training import (  # noqa: E402
    Preprocessor, split_feature_columns, time_decay_weights,
)
from fundamental_model import FundamentalModel  # noqa: E402
from market_model import MarketModel  # noqa: E402
from blend_model import BenterBlend  # noqa: E402

log = logging.getLogger("diagnose_alpha")

HALF_LIFE = 2.5 * 365.25
L2 = 0.001


def load_frame(db: str, table: str) -> pd.DataFrame:
    conn = sqlite3.connect(db)
    df = pd.read_sql_query(f"""
        SELECT f.*, rd.race_date AS race_date, e.finish_pos AS finish_pos
        FROM {table} f
        JOIN entries e ON e.id = f.entry_id
        JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
    """, conn)
    conn.close()
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["y_true"] = (df["finish_pos"] == 1).astype(float)
    df = df.drop(columns=["finish_pos"])
    return df.sort_values(["race_date", "race_id", "entry_id"]).reset_index(drop=True)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def run_side(df: pd.DataFrame, label: str, split_date: str) -> dict:
    fund_cols, _ = split_feature_columns(df.columns)
    tr = df[df["race_date"] < split_date]
    vl = df[df["race_date"] >= split_date]

    pre = Preprocessor().fit(tr, fund_cols)
    X_tr, X_vl = pre.transform(tr), pre.transform(vl)
    w = time_decay_weights(tr["race_date"], tr["race_date"].max(), HALF_LIFE)

    fund = FundamentalModel(l2=L2, max_iter=200, verbose=False)
    fund.fit(X_tr, tr["y_true"].to_numpy(), tr["race_id"].to_numpy(),
             sample_weight=w, feature_names=pre.output_names)

    p_f = fund.predict_race_probabilities(X_vl, vl["race_id"].to_numpy())
    p_m = MarketModel().predict_race_probabilities(
        vl["final_odds"].to_numpy(), vl["race_id"].to_numpy())
    y = vl["y_true"].to_numpy()

    blend = BenterBlend()
    blend.fit(p_f, p_m, vl["race_id"].to_numpy(), y)

    def per_race_ll(p):
        d = pd.DataFrame({"race_id": vl["race_id"].to_numpy(), "p": p, "y": y})
        won = d[d["y"] == 1]
        return float(-np.log(np.clip(won["p"], 1e-12, 1)).mean())

    corr = float(np.corrcoef(logit(p_f), logit(p_m))[0, 1])
    return {
        "label": label,
        "n_features": len(fund_cols),
        "fund_standalone_logloss": per_race_ll(p_f),
        "market_logloss": per_race_ll(p_m),
        "corr_logit_pf_pm": corr,
        "alpha": blend.alpha_,
        "beta": blend.beta_,
        "val_rows": len(vl),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="scripts/gp_full.db")
    p.add_argument("--old-table", default="entry_features_v1_prefix")
    p.add_argument("--new-table", default="entry_features_v1")
    p.add_argument("--split-date", default="2025-01-01")
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING)

    rows = []
    for label, table in (("pre-fix (buggy)", args.old_table),
                         ("post-fix (correct)", args.new_table)):
        df = load_frame(args.db, table)
        rows.append(run_side(df, label, args.split_date))

    print("=" * 78)
    print("Fundamental model: pre-fix vs post-fix features")
    print(f"train < {args.split_date}, validate >= {args.split_date} "
          f"({rows[0]['val_rows']} val entries)")
    print("=" * 78)
    print(f"\n{'quantity':<34} {'pre-fix':>14} {'post-fix':>14} {'delta':>12}")
    print("-" * 76)
    for k in ("fund_standalone_logloss", "corr_logit_pf_pm", "alpha", "beta"):
        o, n = rows[0][k], rows[1][k]
        print(f"{k:<34} {o:>14.4f} {n:>14.4f} {n - o:>+12.4f}")
    print(f"{'market_logloss (reference)':<34} {rows[0]['market_logloss']:>14.4f}")

    d_ll = rows[1]["fund_standalone_logloss"] - rows[0]["fund_standalone_logloss"]
    d_corr = rows[1]["corr_logit_pf_pm"] - rows[0]["corr_logit_pf_pm"]
    print("\nVerdict:")
    if d_ll < 0 and d_corr > 0:
        print("  (B) The corrected fundamental is a BETTER standalone predictor")
        print("      AND more collinear with the market. Alpha fell because the")
        print("      fundamental became more redundant with the price, not worse.")
    elif d_ll > 0:
        print("  (A) The corrected fundamental is a WORSE standalone predictor.")
        print("      That would be surprising — re-check the rebuild.")
    else:
        print("  Mixed / inconclusive — report both numbers plainly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
