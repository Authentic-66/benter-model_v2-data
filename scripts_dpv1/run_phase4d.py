"""Phase 4D — the decisive test.

Doug's 19 rank-1 fundamental features, CT + MNR only, 2022+, against four
strict ship criteria that must **all** clear:

    1. log-loss edge vs market  >= 1.5% on CT+MNR
    2. corr(logit p_f, logit p_m) < 0.55 on CT+MNR
    3. longshot lift            > 1.15x the base ITM rate
    4. positive ROI on ANY exotic ticket structure

Two Phase 4C measurement bugs are corrected here:

* **Longshot detection** is now a ratio rule (``p_model > 1.15 * p_market``)
  scored by **lift over the base ITM rate**, not raw precision. Phase 4C's
  "precision > 30%" bar could be cleared by a filter performing worse than
  random, because the base ITM rate is ~40%.
* **The exacta edge trigger** is measured against a **Platt-calibrated**
  market rather than raw Harville. Against the raw estimate the trigger fired
  0 times in 14,543 races, because an overconfident market always outprices
  the model on its own favourite.

Variants run, all on the same CT+MNR folds:

    rank1_ctmnr     19 rank-1 features, CT+MNR training      <- the test
    full_ctmnr      all available features, CT+MNR training
    rank1_pooled    19 rank-1 features, GP+CT+MNR training, scored on CT+MNR
    market          chalk baseline

Usage
-----
    python scripts_dpv1/run_phase4d.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from prepare_training_dpv1 import (  # noqa: E402
    load_full_frame, split_feature_columns, add_interaction_features,
    INTERACTION_FEATURES, YearFoldSplitter, load_config, rank1_features,
    DEFAULT_DB,
)
import dpv1_metrics as M  # noqa: E402
from train_dpv1 import run_fold  # noqa: E402

log = logging.getLogger("phase4d")

HALF_LIVES_YEARS = [1.0, 1.5, 2.0, 2.5]
L2_VALUES = [0.001, 0.01, 0.1, 1.0]
CIRCUIT = ("CT", "MNR")

SHIP = {
    "log_loss_edge_pct": 1.5,
    "corr_max": 0.55,
    "longshot_lift_min": 1.15,
}


def build_variant(df: pd.DataFrame, fund_cols: list[str], hl: float, l2: float,
                  train_tracks: tuple[str, ...] | None,
                  score_tracks: tuple[str, ...]) -> tuple[pd.DataFrame, list[dict]]:
    """Fold-by-fold out-of-sample predictions.

    ``train_tracks=None`` trains on everything (the pooled variant); scoring is
    always restricted to ``score_tracks`` so every variant is compared on the
    same entries.
    """
    frames, infos = [], []
    for name, tr_idx, vl_idx in YearFoldSplitter().split(df):
        train_df = df.iloc[tr_idx]
        val_df = df.iloc[vl_idx]
        if train_tracks is not None:
            train_df = train_df[train_df["track"].isin(train_tracks)]
        val_df = val_df[val_df["track"].isin(score_tracks)]
        if len(train_df) < 500 or len(val_df) < 100:
            continue
        preds, info = run_fold(train_df, val_df, fund_cols, hl, l2)
        preds["fold"] = name
        frames.append(preds)
        infos.append({"fold": name, "n_train": len(train_df),
                      "n_val": len(val_df), **info})
    return pd.concat(frames, ignore_index=True), infos


def grid_search(df: pd.DataFrame, fund_cols: list[str],
                train_tracks, score_tracks) -> pd.DataFrame:
    rows = []
    for hl_y in HALF_LIVES_YEARS:
        for l2 in L2_VALUES:
            hl = hl_y * 365.25
            preds, infos = build_variant(df, fund_cols, hl, l2,
                                         train_tracks, score_tracks)
            m = M.evaluate_slice(preds, with_wagering=False)
            rows.append({"half_life_days": hl, "half_life_years": hl_y, "l2": l2,
                         "log_loss": m["log_loss"],
                         "log_loss_vs_market_pct": m["log_loss_vs_market_pct"],
                         "corr": m["corr_logit_pf_pm"],
                         "alpha": float(np.mean([i["alpha"] for i in infos])),
                         "beta": float(np.mean([i["beta"] for i in infos]))})
            log.info("  hl=%.1fy l2=%-6g ll=%.5f edge=%+.3f%% corr=%.3f",
                     hl_y, l2, m["log_loss"], m["log_loss_vs_market_pct"],
                     m["corr_logit_pf_pm"])
    return pd.DataFrame(rows).sort_values("log_loss")


def per_fold_table(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fold, g in preds.groupby("fold"):
        m = M.evaluate_slice(g, with_wagering=False)
        rows.append({"fold": fold, "n": len(g),
                     "log_loss": m["log_loss"],
                     "edge_pct": m["log_loss_vs_market_pct"],
                     "corr": m["corr_logit_pf_pm"],
                     "ls115_lift": m.get("ls115_lift")})
    return pd.DataFrame(rows).set_index("fold")


def assess(m: dict) -> dict:
    """Four criteria, all must clear."""
    edge = m["log_loss_vs_market_pct"]
    corr = m["corr_logit_pf_pm"]
    lift = m.get("ls115_lift", float("nan"))
    roi_keys = [k for k in m if k.endswith("_roi") and np.isfinite(m.get(k, np.nan))]
    best_roi_key = max(roi_keys, key=lambda k: m[k]) if roi_keys else None
    best_roi = m[best_roi_key] if best_roi_key else float("nan")
    crit = {
        "1_log_loss_edge": {"value": edge, "threshold": SHIP["log_loss_edge_pct"],
                            "pass": bool(edge >= SHIP["log_loss_edge_pct"])},
        "2_corr": {"value": corr, "threshold": SHIP["corr_max"],
                   "pass": bool(corr < SHIP["corr_max"])},
        "3_longshot_lift": {"value": lift, "threshold": SHIP["longshot_lift_min"],
                            "pass": bool(np.isfinite(lift)
                                         and lift > SHIP["longshot_lift_min"])},
        "4_any_positive_roi": {"value": best_roi, "best_ticket": best_roi_key,
                               "threshold": 0.0,
                               "pass": bool(np.isfinite(best_roi) and best_roi > 0)},
    }
    crit["ALL_PASS"] = all(c["pass"] for c in crit.values() if isinstance(c, dict))
    return crit


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out", default=str(DPV1_DIR / "phase4d_results.json"))
    p.add_argument("--grid-out", default=str(DPV1_DIR / "phase4d_grid.csv"))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    cfg = load_config()
    df = add_interaction_features(load_full_frame(args.db))
    fund_all, market_cols = split_feature_columns(df.columns)
    fund_all = [c for c in fund_all if c not in INTERACTION_FEATURES]
    fund_r1 = rank1_features(cfg, fund_all)
    log.info("corpus 2022+: %d entries | CT+MNR: %d",
             len(df), int(df["track"].isin(CIRCUIT).sum()))
    log.info("features: all=%d  rank1=%d  market=%d",
             len(fund_all), len(fund_r1), len(market_cols))
    log.info("rank-1 set: %s", fund_r1)

    log.info("grid search — rank-1 on CT+MNR")
    grid = grid_search(df, fund_r1, CIRCUIT, CIRCUIT)
    grid.to_csv(args.grid_out, index=False)
    best = grid.iloc[0]
    hl, l2 = float(best["half_life_days"]), float(best["l2"])
    log.info("best: half_life=%.1fy l2=%g", best["half_life_years"], l2)

    log.info("loading payouts…")
    payouts = {w: M.load_payouts(args.db, w)
               for w in ("Trifecta", "Superfecta", "Exacta")}

    variants = {
        "rank1_ctmnr": (fund_r1, CIRCUIT),
        "full_ctmnr": (fund_all, CIRCUIT),
        "rank1_pooled": (fund_r1, None),
    }
    results = {"best_half_life_days": hl, "best_l2": l2,
               "n_rank1_features": len(fund_r1),
               "rank1_features": fund_r1,
               "n_all_features": len(fund_all),
               "ship_thresholds": SHIP}

    preds_store = {}
    for name, (cols, train_tracks) in variants.items():
        log.info("variant: %s", name)
        preds, infos = build_variant(df, cols, hl, l2, train_tracks, CIRCUIT)
        preds_store[name] = preds
        m = M.evaluate_slice(preds, payouts=payouts, with_wagering=True)
        results[name] = {"metrics": m,
                         "per_fold": json.loads(per_fold_table(preds).to_json(orient="index")),
                         "blend": [{k: i[k] for k in ("fold", "alpha", "beta",
                                                      "gamma", "n_train", "n_val")}
                                   for i in infos],
                         "criteria": assess(m)}
        log.info("  edge=%+.3f%% corr=%.3f lift115=%.3f",
                 m["log_loss_vs_market_pct"], m["corr_logit_pf_pm"],
                 m.get("ls115_lift", float("nan")))

    # Chalk baseline on the same entries.
    mk = M.market_baseline(preds_store["rank1_ctmnr"])
    results["market"] = {"metrics": M.evaluate_slice(mk, payouts=payouts,
                                                     with_wagering=True)}

    # Per-track split of the headline variant.
    head = preds_store["rank1_ctmnr"]
    results["rank1_ctmnr_by_track"] = {}
    for t in ("CT", "MNR"):
        sl = head[head["track"] == t]
        results["rank1_ctmnr_by_track"][t] = M.evaluate_slice(
            sl, payouts=payouts, with_wagering=True)

    # Coefficients of the headline model, refit on all CT+MNR data.
    from prepare_training_dpv1 import make_preprocessor
    from prepare_training import time_decay_weights
    from fundamental_model_v2a import FundamentalModelITM
    circ = df[df["track"].isin(CIRCUIT)]
    pre = make_preprocessor().fit(circ, fund_r1)
    X = pre.transform(circ)
    w = time_decay_weights(circ["race_date"], circ["race_date"].max(), hl)
    fm = FundamentalModelITM(l2=l2, max_iter=400).fit(
        X, circ["y_true"].to_numpy(), sample_weight=w,
        feature_names=pre.output_names)
    coefs = sorted(zip(pre.output_names, fm.coef_), key=lambda kv: -abs(kv[1]))
    results["coefficients"] = [{"feature": k, "coef": float(v)} for k, v in coefs]

    head.to_csv(DPV1_DIR / "phase4d_fold_predictions.csv", index=False)
    Path(args.out).write_text(json.dumps(results, indent=2, default=str),
                              encoding="utf-8")
    log.info("wrote %s", args.out)

    # Verdict
    c = results["rank1_ctmnr"]["criteria"]
    print("\n" + "=" * 74)
    print("PHASE 4D SHIP CRITERIA — rank-1 features, CT+MNR")
    print("=" * 74)
    labels = {
        "1_log_loss_edge": "log-loss edge vs market >= 1.5%",
        "2_corr": "corr(logit p_f, logit p_m) < 0.55",
        "3_longshot_lift": "longshot lift > 1.15x base ITM",
        "4_any_positive_roi": "positive ROI on any exotic",
    }
    for k, label in labels.items():
        v = c[k]
        val = v["value"]
        extra = f"  [{v.get('best_ticket')}]" if v.get("best_ticket") else ""
        print(f"  {'PASS' if v['pass'] else 'FAIL'}  {label:<38} "
              f"= {val:>8.4f}{extra}")
    print("-" * 74)
    print(f"  VERDICT: {'ALL CRITERIA CLEAR' if c['ALL_PASS'] else 'FAILED'}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
