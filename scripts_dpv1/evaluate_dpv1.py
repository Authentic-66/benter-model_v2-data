"""Phase 4C evaluation: per-track metrics, baselines, importance, ablations.

Everything is scored on **out-of-sample fold predictions** (rolling-origin by
year), never on the final all-data refit.

Model variants compared, all at the grid's winning hyperparameters:

    full            95 fundamental features (Doug rank 1-2, leak-free)
    +interaction    full + Doug's won_last_out x class_up terms
    rank1_only      the 19 rank-1 fundamental features only
    market          chalk baseline: rank and predict by market P(ITM)
    random          uniform-random ranking

Usage
-----
    python scripts_dpv1/evaluate_dpv1.py --out scripts_dpv1/dpv1_eval.json
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

from prepare_training_dpv1 import (  # noqa: E402
    load_full_frame, split_feature_columns, add_interaction_features,
    INTERACTION_FEATURES, YearFoldSplitter, load_config, rank1_features,
    DEFAULT_DB,
)
import dpv1_metrics as M  # noqa: E402
from train_dpv1 import (  # noqa: E402
    run_fold, TRACK_SLICES, _best_combo, market_p_itm,
    DPv1Model,  # bound here so pickle can resolve the class from __main__
)

log = logging.getLogger("evaluate_dpv1")

WAGERS = ("Trifecta", "Superfecta", "Exacta")


def build_variant(df: pd.DataFrame, fund_cols: list[str], hl: float,
                  l2: float) -> pd.DataFrame:
    frames = []
    for name, tr, vl in YearFoldSplitter().split(df):
        preds, info = run_fold(df.iloc[tr], df.iloc[vl], fund_cols, hl, l2)
        preds["fold"] = name
        preds["alpha"] = info["alpha"]
        preds["beta"] = info["beta"]
        preds["gamma"] = info["gamma"]
        frames.append(preds)
    return pd.concat(frames, ignore_index=True)


def per_track_table(preds: pd.DataFrame, payouts: dict) -> pd.DataFrame:
    rows = []
    for tname, fn in TRACK_SLICES.items():
        sl = preds[fn(preds)]
        if len(sl) < 100:
            continue
        m = M.evaluate_slice(sl, payouts=payouts, with_wagering=True)
        rows.append({"slice": tname, **m})
    return pd.DataFrame(rows).set_index("slice")


def class_change_monotonicity(df: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """Does the model reproduce Doug's DOWN > SAME > UP ordering?"""
    j = preds.merge(
        df[["entry_id", "class_change_from_last", "last_race_won"]],
        on="entry_id", how="left")
    g = (j.dropna(subset=["class_change_from_last"])
         .groupby("class_change_from_last")
         .agg(n=("y_true", "size"), actual_itm=("y_true", "mean"),
              model_pred=("y_pred", "mean"), market_pred=("p_market", "mean"),
              fund_pred=("p_fund", "mean")))
    return g.reindex(["DOWN", "SAME", "UP"])


def interaction_effect(df: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """Doug's specific insight, measured on the val folds."""
    j = preds.merge(
        df[["entry_id", "class_change_from_last", "last_race_won"]],
        on="entry_id", how="left")
    j = j.dropna(subset=["class_change_from_last", "last_race_won"])
    g = (j.groupby(["last_race_won", "class_change_from_last"])
         .agg(n=("y_true", "size"), actual_itm=("y_true", "mean"),
              model_pred=("y_pred", "mean"), fund_pred=("p_fund", "mean")))
    return g


def top_coefficients(model_path: Path, n: int = 25) -> pd.DataFrame:
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    items = list(model.coefficients.items())[:n]
    return pd.DataFrame(items, columns=["feature", "coefficient"])


def coefficient_by_rank(model_path: Path, cfg: dict) -> pd.DataFrame:
    """Mean |coefficient| grouped by Doug's rank — are rank-1s the heaviest?"""
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    rows = []
    for name, coef in model.coefficients.items():
        base = name.split("__")[0]
        spec = cfg["features"].get(base)
        if spec is None:
            continue
        rows.append({"feature": base, "encoded": name, "abs_coef": abs(coef),
                     "doug_rank": spec.get("doug_rank"),
                     "dpv1_addition": bool(spec.get("dpv1_addition"))})
    d = pd.DataFrame(rows)
    by_rank = (d.groupby(d["doug_rank"].fillna(0).astype(int))
               .agg(n_encoded=("abs_coef", "size"),
                    mean_abs_coef=("abs_coef", "mean"),
                    max_abs_coef=("abs_coef", "max")))
    by_rank.index = by_rank.index.map({0: "DPv1 addition", 1: "rank 1", 2: "rank 2"})
    cross = d[d["dpv1_addition"]].nlargest(12, "abs_coef")
    return by_rank, cross


def sample_race_json(df: pd.DataFrame, preds: pd.DataFrame, n_races: int = 3) -> list:
    conn_cols = ["entry_id", "race_id", "track", "race_date", "y_pred",
                 "p_fund", "p_market", "y_true", "finish_pos", "final_odds"]
    out = []
    for track in ("GP", "CT", "MNR", "ELP"):
        sl = preds[preds["track"] == track]
        if sl.empty:
            continue
        # a mid-size field from the most recent fold
        cand = (sl.groupby("race_id").size().loc[lambda s: (s >= 7) & (s <= 9)])
        if cand.empty:
            continue
        rid = int(sl[sl["race_id"].isin(cand.index)]["race_id"].iloc[-1])
        r = sl[sl["race_id"] == rid][conn_cols].copy()
        meta = df[df["race_id"] == rid].iloc[0]
        r = r.sort_values("y_pred", ascending=False)
        r["rank"] = range(1, len(r) + 1)
        r["edge_vs_market"] = r["y_pred"] - r["p_market"]
        flags = M.longshot_flags(sl[sl["race_id"] == rid])
        out.append({
            "race_id": rid,
            "track": track,
            "race_date": str(pd.Timestamp(meta["race_date"]).date()),
            "race_type": meta.get("race_type"),
            "surface": meta.get("surface"),
            "distance_yards": _num(meta.get("distance_yards")),
            "field_size": int(len(r)),
            "longshot_count": int(flags.sum()),
            "horses": [
                {"rank": int(row["rank"]),
                 "program_num": None,
                 "final_odds": _num(row["final_odds"]),
                 "p_model_itm": round(float(row["y_pred"]), 4),
                 "p_fundamental_itm": round(float(row["p_fund"]), 4),
                 "p_market_itm": round(float(row["p_market"]), 4),
                 "edge_vs_market": round(float(row["edge_vs_market"]), 4),
                 "finish_pos": _num(row["finish_pos"]),
                 "was_itm": int(row["y_true"])}
                for _, row in r.iterrows()
            ],
        })
    return out


def _num(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--grid", default=str(DPV1_DIR / "dpv1_grid_results.csv"))
    p.add_argument("--model", default=str(DPV1_DIR / "dpv1.pkl"))
    p.add_argument("--out", default=str(DPV1_DIR / "dpv1_eval.json"))
    p.add_argument("--preds-out", default=str(DPV1_DIR / "dpv1_predictions_sample.json"))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    cfg = load_config()
    df = add_interaction_features(load_full_frame(args.db))
    fund_all, market_cols = split_feature_columns(df.columns)
    fund_full = [c for c in fund_all if c not in INTERACTION_FEATURES]
    fund_r1 = rank1_features(cfg, fund_full)

    grid = pd.read_csv(args.grid)
    hl, l2 = _best_combo(grid)
    log.info("best combo: half_life=%.2fy l2=%g | fund=%d rank1=%d",
             hl / 365.25, l2, len(fund_full), len(fund_r1))

    log.info("loading payout tables…")
    payouts = {w: M.load_payouts(args.db, w) for w in WAGERS}
    for w, t in payouts.items():
        log.info("  %-11s %d races", w, len(t))

    variants: dict[str, pd.DataFrame] = {}
    log.info("variant: full")
    variants["full"] = build_variant(df, fund_full, hl, l2)
    log.info("variant: +interaction")
    variants["+interaction"] = build_variant(df, fund_all, hl, l2)
    log.info("variant: rank1_only")
    variants["rank1_only"] = build_variant(df, fund_r1, hl, l2)
    variants["market"] = M.market_baseline(variants["full"])
    variants["random"] = M.random_baseline(variants["full"])

    results = {"best_half_life_days": hl, "best_l2": l2,
               "n_fundamental_features": len(fund_full),
               "n_rank1_features": len(fund_r1),
               "market_features": market_cols}

    log.info("scoring variants per track…")
    for vname, preds in variants.items():
        tbl = per_track_table(preds, payouts)
        results[vname] = json.loads(tbl.to_json(orient="index"))
        log.info("  %-13s ALL ll=%.4f corr=%.3f top3=%.3f",
                 vname, tbl.loc["ALL", "log_loss"],
                 tbl.loc["ALL", "corr_logit_pf_pm"],
                 tbl.loc["ALL", "itm_hit_top3"])

    full = variants["full"]
    results["blend_by_fold"] = (full.groupby("fold")[["alpha", "beta", "gamma"]]
                                .first().to_dict("index"))
    results["class_change_monotonicity"] = json.loads(
        class_change_monotonicity(df, full).to_json(orient="index"))
    results["interaction_effect"] = json.loads(
        interaction_effect(df, full).reset_index().to_json(orient="records"))

    if Path(args.model).exists():
        results["top_coefficients"] = json.loads(
            top_coefficients(Path(args.model)).to_json(orient="records"))
        by_rank, cross = coefficient_by_rank(Path(args.model), cfg)
        results["coef_by_doug_rank"] = json.loads(by_rank.to_json(orient="index"))
        results["top_cross_track_coefs"] = json.loads(
            cross[["encoded", "abs_coef"]].to_json(orient="records"))

    Path(args.out).write_text(json.dumps(results, indent=2, default=str),
                              encoding="utf-8")
    log.info("wrote %s", args.out)

    samples = sample_race_json(df, full)
    Path(args.preds_out).write_text(json.dumps(samples, indent=2, default=str),
                                    encoding="utf-8")
    log.info("wrote %s (%d races)", args.preds_out, len(samples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
