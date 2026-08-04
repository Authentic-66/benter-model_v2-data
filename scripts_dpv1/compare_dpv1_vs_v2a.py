"""Head-to-head: DPv1 (3-track) vs Phase 3G v2a (GP-only), on GP entries.

Both models target ITM on 2022+ data, so the honest comparison is on the
**GP slice only** — v2a has never seen CT or MNR.

Two caveats, stated rather than smoothed over:

1. **The fold definitions differ.** v2a uses the Phase 3D rolling-origin
   folds (val 2024 / 2025 / 2026Q1 / 2026Q2); DPv1 folds by calendar year
   (val 2023 / 2024 / 2025 / 2026). To keep it apples-to-apples we intersect
   on entry_id, so both sides are scored on exactly the same entries — the
   ones each model held out.

2. **The feature tables differ.** v2a reads `entry_features_v1` (73 active
   Phase 3C features, rebuilt in Phase 4B.1); DPv1 reads
   `entry_features_dpv1` (Doug's ranked set, minus the eight leaky ones).
   That difference *is* the thing being tested.

Usage
-----
    python scripts_dpv1/compare_dpv1_vs_v2a.py
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

import dpv1_metrics as M  # noqa: E402
from generate_phase3g_reports import (  # noqa: E402
    rebuild_v2a_predictions, load_v2a_frame,
)
from train_benter_v2a import TrainedModelITM  # noqa: E402,F401

log = logging.getLogger("compare_dpv1_vs_v2a")


def v2a_predictions(pkl: str, db: str) -> pd.DataFrame:
    with open(pkl, "rb") as f:
        model = pickle.load(f)
    df = load_v2a_frame(db)
    preds = rebuild_v2a_predictions(df, model)
    return preds.rename(columns={"y_pred_fund_only": "p_fund",
                                 "y_pred_market_only": "p_market"})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dpv1-preds", default=str(DPV1_DIR / "dpv1_fold_predictions.csv"))
    p.add_argument("--v2a-pkl", default=str(REPO / "scripts_v2a" / "benter_v2a_rebuilt.pkl"))
    p.add_argument("--gp-db", default=str(REPO / "scripts" / "gp_full.db"))
    p.add_argument("--full-db", default=str(REPO / "scripts" / "racing_full.db"))
    p.add_argument("--out", default=str(DPV1_DIR / "dpv1_vs_v2a.json"))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    dpv1 = pd.read_csv(args.dpv1_preds)
    dpv1_gp = dpv1[dpv1["track"] == "GP"]
    log.info("DPv1 GP val entries: %d", len(dpv1_gp))

    log.info("rebuilding v2a predictions…")
    v2a = v2a_predictions(args.v2a_pkl, args.gp_db)
    log.info("v2a val entries: %d", len(v2a))

    # gp_full.db and racing_full.db are separate databases, so entry_id is not
    # a shared key. Match on the natural key instead.
    common = _align(dpv1_gp, v2a, args.full_db, args.gp_db)
    log.info("common GP entries scored by both: %d", len(common))

    payouts = {w: M.load_payouts(args.gp_db, w) for w in ("Trifecta", "Superfecta")}

    results = {}
    for label, cols in (("DPv1", ("dpv1_y_pred", "dpv1_p_fund", "dpv1_p_market")),
                        ("v2a", ("v2a_y_pred", "v2a_p_fund", "v2a_p_market"))):
        sl = common.rename(columns={cols[0]: "y_pred", cols[1]: "p_fund",
                                    cols[2]: "p_market"})
        m = M.evaluate_slice(sl, payouts=payouts, with_wagering=True)
        results[label] = m
        log.info("%-5s ll=%.4f corr=%.3f top3=%.4f prec3=%.4f tri_roi=%s",
                 label, m["log_loss"], m["corr_logit_pf_pm"],
                 m["itm_hit_top3"], m["itm_precision_top3"],
                 f"{m.get('trifecta_box3_roi', float('nan')):.4f}")

    keys = ["n_entries", "n_races", "log_loss", "brier", "ece",
            "corr_logit_pf_pm", "log_loss_vs_market_pct",
            "itm_hit_top3", "itm_hit_top4", "itm_precision_top3",
            "itm_full_sweep_top3", "longshot_n", "longshot_precision",
            "trifecta_box3_roi", "superfecta_box4_roi"]
    print(f"\n{'metric':<26} {'DPv1':>14} {'v2a':>14} {'delta':>14}")
    print("-" * 72)
    for k in keys:
        a, b = results["DPv1"].get(k), results["v2a"].get(k)
        if a is None or b is None:
            continue
        print(f"{k:<26} {a:>14.4f} {b:>14.4f} {a - b:>+14.4f}")

    Path(args.out).write_text(json.dumps(results, indent=2, default=str),
                              encoding="utf-8")
    log.info("wrote %s", args.out)
    return 0


def _align(dpv1_gp: pd.DataFrame, v2a: pd.DataFrame, full_db: str,
           gp_db: str) -> pd.DataFrame:
    """Join the two prediction sets on (race_date, race_num, program_num)."""
    import sqlite3
    key_full = pd.read_sql_query("""
        SELECT e.id AS entry_id, rd.race_date, r.race_num, e.program_num
        FROM entries e JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        JOIN tracks t ON t.id = rd.track_id
        WHERE t.code = 'GP'
    """, sqlite3.connect(full_db))
    key_gp = pd.read_sql_query("""
        SELECT e.id AS entry_id, rd.race_date, r.race_num, e.program_num
        FROM entries e JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
    """, sqlite3.connect(gp_db))

    # The DPv1 prediction frame carries its own race_date; drop it so the
    # join supplies the canonical one and no _x/_y suffixes appear.
    a = (dpv1_gp.drop(columns=["race_date"], errors="ignore")
         .merge(key_full, on="entry_id")
         .rename(columns={"y_pred": "dpv1_y_pred", "p_fund": "dpv1_p_fund",
                          "p_market": "dpv1_p_market"}))
    b = (v2a.merge(key_gp, on="entry_id")
         .rename(columns={"y_pred": "v2a_y_pred", "p_fund": "v2a_p_fund",
                          "p_market": "v2a_p_market"}))
    keys = ["race_date", "race_num", "program_num"]
    m = a.merge(b[keys + ["v2a_y_pred", "v2a_p_fund", "v2a_p_market"]],
                on=keys, how="inner")
    # Scoring helpers key on entry_id/race_id from the DPv1 side.
    return m[["entry_id", "race_id", "y_true", "finish_pos", "final_odds",
              "dpv1_y_pred", "dpv1_p_fund", "dpv1_p_market",
              "v2a_y_pred", "v2a_p_fund", "v2a_p_market"]]


if __name__ == "__main__":
    raise SystemExit(main())
