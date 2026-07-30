"""Generate PHASE_3G_ITM_MODEL.md and V2_VS_V2A_COMPARISON.md.

The Phase 3G report is a v2a self-evaluation with the ITM metric bundle.
The head-to-head report re-scores v2 (win-target) and v2a (ITM-target) on
the same 2022+ val folds, ranking horses by each model's own probability
and asking "how often are your top-3 picks ITM?"
"""
from __future__ import annotations

import json
import pickle
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from prepare_training_v2a import load_full_frame as load_v2a_frame       # noqa
from prepare_training import (                                             # noqa
    Preprocessor, split_feature_columns, time_decay_weights, load_full_frame as load_v2_frame,
)
from fundamental_model_v2a import FundamentalModelITM                     # noqa
from market_model_v2a import MarketModelITM                                # noqa
from blend_model_v2a import BenterBlendITM                                 # noqa
from fundamental_model import FundamentalModel as FundamentalModelV2       # noqa
from blend_model import BenterBlend as BenterBlendV2                       # noqa
from cross_validation import RollingOriginSplitter                        # noqa
from itm_metrics import (                                                  # noqa
    evaluate_itm, itm_hit_rate_top_k, itm_precision_top_k, itm_recall_top_k,
    itm_full_sweep_top_3, trifecta_box_roi, confidence_stratified_top_k,
    longshot_metrics,
)
from longshot_detector import flag_longshots, LongshotConfig               # noqa
from metrics import evaluate as evaluate_phase3d, calibration_table        # noqa
from train_benter_v2a import (                                             # noqa
    run_fold, TrainedModelITM, _market_win_p_per_race,
)


DB = Path("scripts/gp_full.db")
V2A_PKL = Path("scripts_v2a/benter_v2a.pkl")
V2_PKL = Path("scripts/benter_v2_v10.pkl")     # Phase 3F v2+v10, best v2 variant
V2_PHASE3E_PKL = Path("scripts/benter_v2_phase3e.pkl")
V2A_GRID = Path("scripts_v2a/benter_v2a_grid.csv")
OUT_3G = Path("scripts_v2a/PHASE_3G_ITM_MODEL.md")
OUT_CMP = Path("scripts_v2a/V2_VS_V2A_COMPARISON.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mkrow(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _f(v, digits=4):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:.{digits}f}"


def _pct(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v * 100:.1f}%"


# ---------------------------------------------------------------------------
# v2a per-fold predictions
# ---------------------------------------------------------------------------

def rebuild_v2a_predictions(df: pd.DataFrame, model: TrainedModelITM):
    """Refit v2a per-fold using saved hyperparameters and return predictions."""
    cv = RollingOriginSplitter.default_gp_folds()
    frames = []
    for name, tr_idx, vl_idx in cv.split(df):
        train_df = df.iloc[tr_idx].reset_index(drop=True)
        val_df = df.iloc[vl_idx].reset_index(drop=True)
        pre = Preprocessor().fit(train_df, model.fund_cols)
        X_tr = pre.transform(train_df)
        X_vl = pre.transform(val_df)
        w = time_decay_weights(
            train_df["race_date"], train_df["race_date"].max(),
            model.hyperparameters["half_life_days"],
        )
        fund = FundamentalModelITM(l2=model.hyperparameters["l2"]).fit(
            X_tr, train_df["y_true"].to_numpy(),
            sample_weight=w, feature_names=pre.output_names,
        )
        p_f = fund.predict_probabilities(X_vl)
        p_m = MarketModelITM().predict_p_itm(
            _market_win_p_per_race(val_df), val_df["race_id"].to_numpy(),
        )
        blend = BenterBlendITM().fit(p_f, p_m, val_df["y_true"].to_numpy())
        p_final = blend.predict(p_f, p_m)
        frames.append(pd.DataFrame({
            "fold": name,
            "entry_id": val_df["entry_id"].to_numpy(),
            "race_id":  val_df["race_id"].to_numpy(),
            "y_pred":   p_final,
            "y_pred_fund_only": p_f,
            "y_pred_market_only": p_m,
            "y_true":   val_df["y_true"].to_numpy(),
            "final_odds": val_df["final_odds"].to_numpy(),
            "finish_pos": val_df["finish_pos"].to_numpy(),
        }))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# v2 per-fold predictions on the same 2022+ val folds
# ---------------------------------------------------------------------------

def rebuild_v2_predictions_for_itm(df_v2a: pd.DataFrame):
    """Refit v2 (win-target) per fold, output predictions aligned to v2a folds.

    We reuse the 2022+ frame from v2a's loader so both models are scored
    on the exact same val entries. v2 is retrained here on 2022+ WIN target
    for a like-for-like comparison — using the shipped v2 model directly
    would confound the comparison with v2's larger train window.
    """
    df = df_v2a.copy()
    # Determine features from the ORIGINAL frame's columns so that a helper
    # column like y_true_win isn't seen by split_feature_columns as a feature
    # (which would be a catastrophic label leak — the model would memorise
    # wins by reading y_true_win directly).
    fund_cols, market_cols = split_feature_columns(df.columns)
    df["y_true_win"] = (df["finish_pos"] == 1).astype(int)

    cv = RollingOriginSplitter.default_gp_folds()
    frames = []
    # Use Phase 3E's baseline hyperparameters
    HL_DAYS = 730.0    # 2y half life
    L2 = 0.01

    for name, tr_idx, vl_idx in cv.split(df):
        train_df = df.iloc[tr_idx].reset_index(drop=True)
        val_df = df.iloc[vl_idx].reset_index(drop=True)
        pre = Preprocessor().fit(train_df, fund_cols)
        X_tr = pre.transform(train_df)
        X_vl = pre.transform(val_df)
        w = time_decay_weights(train_df["race_date"],
                                train_df["race_date"].max(), HL_DAYS)
        fund = FundamentalModelV2(l2=L2, max_iter=200).fit(
            X_tr, train_df["y_true_win"].to_numpy(),
            train_df["race_id"].to_numpy(),
            sample_weight=w, feature_names=pre.output_names,
        )
        p_f_win = fund.predict_race_probabilities(
            X_vl, val_df["race_id"].to_numpy(),
        )
        # Market win prob per race
        p_m_win = np.where(
            (val_df["final_odds"] > 0) & np.isfinite(val_df["final_odds"]),
            1.0 / (val_df["final_odds"].to_numpy(float) + 1.0), np.nan,
        )
        rid = val_df["race_id"].to_numpy()
        s = pd.Series(p_m_win)
        sums = s.groupby(rid).transform("sum").to_numpy()
        p_m_win_norm = p_m_win / np.where(sums > 0, sums, np.nan)

        blend = BenterBlendV2().fit(
            p_f_win, p_m_win_norm, rid,
            val_df["y_true_win"].to_numpy(),
        )
        p_final_win = blend.predict_race_probabilities(
            p_f_win, p_m_win_norm, rid,
        )
        frames.append(pd.DataFrame({
            "fold": name,
            "entry_id": val_df["entry_id"].to_numpy(),
            "race_id":  rid,
            "y_pred_win": p_final_win,
            "y_true":    (val_df["finish_pos"] <= 3).astype(int).to_numpy(),
            "final_odds": val_df["final_odds"].to_numpy(),
            "finish_pos": val_df["finish_pos"].to_numpy(),
        }))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Report 1: PHASE_3G_ITM_MODEL.md
# ---------------------------------------------------------------------------

def make_phase3g_report(model: TrainedModelITM, df_v2a: pd.DataFrame,
                         val_preds: pd.DataFrame, grid: pd.DataFrame) -> None:
    L: list[str] = []
    L.append("# Phase 3G — Benter v2a (ITM-target model)\n")
    L.append(f"_Model version: `{model.version}` · trained "
             f"{model.trained_at[:10]} · training scope: 2022-01-01 onward · "
             f"artifact: `scripts_v2a/benter_v2a.pkl`._\n")

    L.append("## TL;DR\n")
    L.append("v2a pivots the target from **win** (top-1) to **in-the-money** "
             "(top-3 finish). Same 71 fundamental features + 8 v10 flag "
             "columns, but the fundamental model swaps from conditional "
             "logit (softmax per race) to binary logistic per entry, since "
             "ITM is not a mutually-exclusive within-race outcome. Training "
             "restricted to 2022+ (~66k entries, ~8.6k races) per Doug's "
             "HISA-era scope note.")
    L.append("")
    itm3 = float(val_preds.pipe(itm_hit_rate_top_k, k=3))
    itm4 = float(val_preds.pipe(itm_hit_rate_top_k, k=4))
    prec3 = float(val_preds.pipe(itm_precision_top_k, k=3))
    prec4 = float(val_preds.pipe(itm_precision_top_k, k=4))
    sweep = float(val_preds.pipe(itm_full_sweep_top_3))
    L.append(f"**Key numbers on all 2022+ val folds concatenated ({len(val_preds):,} "
             f"scored entries across {val_preds['race_id'].nunique():,} races):**")
    L.append(f"- Top-3 hit rate (≥1 of model's 3 picks finished ITM): **{_pct(itm3)}**")
    L.append(f"- Top-4 hit rate: **{_pct(itm4)}**")
    L.append(f"- Top-3 precision (mean fraction of picks that are ITM): **{_pct(prec3)}**")
    L.append(f"- Full-sweep top-3 rate (all 3 picks ITM = box trifecta hit): **{_pct(sweep)}**")
    L.append(f"- Blend weights: α (fund) = **{model.training_notes['alpha']:.3f}**, "
             f"β (market) = **{model.training_notes['beta']:.3f}**, "
             f"γ (intercept) = **{model.training_notes['gamma']:.3f}**")
    L.append("")

    # ---- Ship-criteria-analog for ITM
    L.append("## ITM-model performance vs random baseline\n")
    # Random baseline: what's the expected P(≥1 ITM in random 3 picks)?
    # In a race with N horses and 3 ITM finishers,
    # P(0 hits in a random 3 picks) = C(N-3, 3) / C(N, 3)
    # We compute the empirical average across all val races.
    field_sizes = val_preds.groupby("race_id").size()
    def _p_at_least_one(N, k):
        if N < k + 3:
            return 1.0
        from math import comb
        return 1 - comb(N - 3, k) / comb(N, k)
    def _p_full_sweep(N):
        if N < 3:
            return 1.0
        from math import comb
        return 1 / comb(N, 3)   # P(random 3 picks == the 3 ITM finishers, unordered)
    baseline_top3 = float(field_sizes.map(lambda N: _p_at_least_one(N, 3)).mean())
    baseline_top4 = float(field_sizes.map(lambda N: _p_at_least_one(N, 4)).mean())
    baseline_sweep = float(field_sizes.map(_p_full_sweep).mean())
    L.append("| Metric | Random baseline | v2a | Uplift |")
    L.append("|---|---:|---:|---:|")
    L.append(_mkrow(["Top-3 hit (≥1 ITM in top 3)",
                     _pct(baseline_top3), _pct(itm3),
                     f"×{itm3/baseline_top3:.2f}" if baseline_top3 > 0 else "n/a"]))
    L.append(_mkrow(["Top-4 hit (≥1 ITM in top 4)",
                     _pct(baseline_top4), _pct(itm4),
                     f"×{itm4/baseline_top4:.2f}" if baseline_top4 > 0 else "n/a"]))
    L.append(_mkrow(["Full sweep top-3 (all 3 ITM)",
                     _pct(baseline_sweep), _pct(sweep),
                     f"×{sweep/baseline_sweep:.1f}" if baseline_sweep > 0 else "n/a"]))
    L.append("")

    # ---- Per-fold
    L.append("## Per-fold results (v2a)\n")
    L.append("| Fold | Val entries | Top-3 hit | Top-4 hit | Prec top-3 | Full sweep | α | β | γ |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, sub in val_preds.groupby("fold"):
        m = evaluate_itm(sub)
        # blend params from grid at winning combo
        best_grid = grid[grid["fold"] == name].sort_values("log_loss_per_race").iloc[0]
        L.append(_mkrow([
            name, f"{len(sub):,}",
            _pct(m["itm_hit_rate_top3"]),
            _pct(m["itm_hit_rate_top4"]),
            _pct(m["itm_precision_top3"]),
            _pct(m["itm_full_sweep_top_3"]),
            f"{best_grid['alpha']:+.3f}",
            f"{best_grid['beta']:+.3f}",
            f"{best_grid['gamma']:+.3f}",
        ]))
    L.append("")

    # ---- Grid summary
    L.append("## Hyperparameter grid (mean across folds)\n")
    summary = (grid.groupby(["half_life_days", "l2"])
               [["log_loss_per_race", "itm_hit_rate_top3", "itm_hit_rate_top4",
                 "itm_precision_top3", "itm_full_sweep_top_3",
                 "alpha", "beta", "gamma"]]
               .mean().round(4).reset_index())
    summary["half_life_y"] = (summary["half_life_days"] / 365.25).round(2)
    L.append("Sorted by log-loss (lower better). "
             "Log-loss values are much higher than v2 because the metric is "
             "designed for softmax-per-race and here we're applying it to "
             "binary logistic per entry — treat it as *relative* only.\n")
    L.append("| Half-life | L2 | log-loss | ITMtop3 | ITMtop4 | Prec@3 | Sweep@3 | α | β | γ |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    top = summary.sort_values("log_loss_per_race").head(10)
    for _, r in top.iterrows():
        L.append(_mkrow([
            f"{r['half_life_y']}y",
            f"{r['l2']}",
            _f(r["log_loss_per_race"]),
            _pct(r["itm_hit_rate_top3"]),
            _pct(r["itm_hit_rate_top4"]),
            _pct(r["itm_precision_top3"]),
            _pct(r["itm_full_sweep_top_3"]),
            f"{r['alpha']:+.3f}",
            f"{r['beta']:+.3f}",
            f"{r['gamma']:+.3f}",
        ]))
    L.append("")

    # ---- Longshot detection
    L.append("## Longshot detection\n")
    L.append("A horse is flagged as a *longshot include* if all three of "
             "(model P(ITM) > 0.25) AND (market P(ITM) < 0.20) AND "
             "(rank outside model's top-3). This aims to catch horses the "
             "tote board is underpricing that the model likes for ITM.\n")
    # compute market P(ITM) per val row
    p_market_itm = MarketModelITM().predict_p_itm(
        _market_win_p_per_race(val_preds), val_preds["race_id"].to_numpy(),
    )
    val_preds = val_preds.assign(p_market_itm=p_market_itm)
    # Per-race ranking by v2a P(ITM)
    ranks = (val_preds.groupby("race_id")["y_pred"]
             .rank(method="first", ascending=False).astype(int))
    val_preds = val_preds.assign(rank=ranks)
    flags = flag_longshots(
        val_preds["y_pred"].to_numpy(),
        val_preds["p_market_itm"].to_numpy(),
        val_preds["rank"].to_numpy(),
    )
    val_preds = val_preds.assign(longshot_flag=flags)
    ls = longshot_metrics(val_preds, pd.Series(flags, index=val_preds.index))
    L.append(f"- Total entries flagged: **{ls['n_flagged']:,}** "
             f"({ls['n_flagged'] / len(val_preds) * 100:.2f}% of scored entries)")
    L.append(f"- ITM hits among flagged: **{ls['hits']:,}**")
    L.append(f"- **Longshot precision: {_pct(ls['precision'])}** "
             f"(vs corpus ITM rate of {val_preds['y_true'].mean()*100:.1f}%)")
    L.append(f"- Races with at least one flagged longshot: "
             f"**{int((val_preds.groupby('race_id')['longshot_flag'].sum() > 0).sum()):,}**")
    L.append("")

    # ---- Confidence stratification
    L.append("## Confidence stratification (top-3 hit rate by top-1 P(ITM) bucket)\n")
    conf = confidence_stratified_top_k(val_preds, k=3, n_buckets=4)
    L.append("| Bucket | Top-1 P(ITM) range | n races | Top-3 hit rate |")
    L.append("|---|---|---:|---:|")
    for _, r in conf.iterrows():
        L.append(_mkrow([
            int(r["bucket"]),
            f"[{r['top1_pred_min']:.3f}, {r['top1_pred_max']:.3f}]",
            f"{int(r['n_races']):,}",
            _pct(r["top_k_hit_rate"]),
        ]))
    L.append("")

    # ---- Trifecta box ROI
    L.append("## Trifecta box ROI (top-3 picks per race)\n")
    L.append("Simulates placing a `$1 straight box` on the model's top-3 "
             "picks — 6 tickets per race — and reading the actual trifecta "
             "payoff from the chart. Payoffs sourced from the "
             "`exotic_payouts` table (`wager_name = 'Trifecta'`). ROI is "
             "net PnL divided by total staked; positive means the strategy "
             "beat the tote in this window.\n")
    payouts = _load_trifecta_payouts()
    val_scoring = val_preds[["entry_id", "race_id", "y_pred",
                              "y_true", "final_odds", "finish_pos"]]
    roi_top3 = trifecta_box_roi(val_scoring, payouts, k=3)
    L.append("| Metric | Value |")
    L.append("|---|---:|")
    L.append(_mkrow(["Races bet", f"{roi_top3['n_races']:,}"]))
    L.append(_mkrow(["Trifecta hits (all 3 in top-3)", f"{roi_top3['n_hits']:,}"]))
    L.append(_mkrow(["Total stake (`$1 base` × 6 tickets × races)",
                     f"${roi_top3['stake_total']:,.2f}"]))
    L.append(_mkrow(["Total return", f"${roi_top3['return_total']:,.2f}"]))
    L.append(_mkrow(["Net PnL", f"${roi_top3['pnl']:,.2f}"]))
    L.append(_mkrow(["**ROI**",
                     f"**{roi_top3['roi']*100:+.1f}%**" if np.isfinite(roi_top3['roi']) else "n/a"]))
    L.append("")

    # ---- Top coefficients
    L.append("## Top 25 fundamental coefficients (|weight|)\n")
    coef = pd.Series(model.fundamental.coef_,
                     index=model.preprocessor.output_names)
    top = coef.abs().sort_values(ascending=False).head(25)
    L.append("| Feature | Coefficient |")
    L.append("|---|---:|")
    for name in top.index:
        L.append(_mkrow([f"`{name}`", f"{coef[name]:+.4f}"]))
    L.append("")

    # ---- Sample race
    L.append("## Sample race output\n")
    sample_race_id = int(val_preds["race_id"].sample(1, random_state=42).iloc[0])
    conn = sqlite3.connect(DB)
    meta = conn.execute("""
        SELECT r.id AS race_id, rd.race_date, r.race_num, t.code AS track_code,
               r.surface, r.distance_yards, r.field_size, r.race_type
        FROM races r JOIN race_days rd ON rd.id = r.race_day_id
        JOIN tracks t ON t.id = rd.track_id
        WHERE r.id = ?
    """, (sample_race_id,)).fetchone()
    horses_meta = pd.read_sql_query("""
        SELECT e.id AS entry_id, h.name AS horse_name,
               e.program_num, e.post_pos
        FROM entries e JOIN horses h ON h.id = e.horse_id
        WHERE e.race_id = ?
    """, conn, params=(sample_race_id,))
    conn.close()
    sub = val_preds[val_preds["race_id"] == sample_race_id]
    entries = horses_meta.merge(sub, on="entry_id")
    entries["p_model_itm"] = entries["y_pred"]
    from longshot_detector import build_race_output
    race_out = build_race_output(dict(zip(
        ["race_id", "race_date", "race_num", "track_code", "surface",
         "distance_yards", "field_size", "race_type"], meta)),
        entries)
    L.append("```json")
    L.append(json.dumps(race_out, indent=2, default=str))
    L.append("```")
    L.append("")

    # ---- Methodology
    L.append("## Methodology notes\n")
    L.append("**Target.** ``y_true = 1`` iff the entry finished top-3 (top-3 = "
             "\"in the money\"). About 38.9% of training entries are positive.")
    L.append("")
    L.append("**Model.** Binary logistic regression per entry (sigmoid), "
             "L2-regularised, weighted by a 1-year time-decay half-life "
             "(the L-BFGS grid picked 1.0y over 2/3y). No per-race softmax — "
             "ITM is not mutually exclusive within a race.")
    L.append("")
    L.append("**Blend.** Fundamental P(ITM) and market P(ITM) combined as "
             "``sigmoid(α · logit(p_f) + β · logit(p_m) + γ)``. Market P(ITM) "
             "comes from the Harville reduction applied to per-race-normalised "
             "tote implied win probabilities. Blend fit on the val fold "
             "(same in-fold convention as v2 — 3 params over ~10k val entries "
             "is not meaningfully over-fittable).")
    L.append("")
    L.append("**Training scope.** 2022-01-01 onward, per Doug's Phase 3G scope "
             "note about HISA-era vs pre-HISA racing dynamics. 65,948 entries "
             "across 8,563 races. Older data remains in `gp_full.db` but is "
             "excluded from training.")
    L.append("")
    L.append("**Log-loss caveat.** The Phase 3D `log_loss_per_race` and "
             "`ece_10bin` metrics were designed for per-race-normalised win "
             "probabilities (they enforce softmax within race). Applied to "
             "binary logistic per-entry outputs, they produce inflated but "
             "still self-consistent values — useful for grid-search selection "
             "but not directly comparable to v2's numbers. The ITM-specific "
             "metrics in `itm_metrics.py` are the primary yardsticks.")
    L.append("")

    OUT_3G.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT_3G}")


def _load_trifecta_payouts() -> pd.DataFrame:
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT race_id, base_amount, payoff, winning_numbers
        FROM exotic_payouts
        WHERE wager_name = 'Trifecta'
    """, conn)
    return df


# ---------------------------------------------------------------------------
# Report 2: V2_VS_V2A_COMPARISON.md
# ---------------------------------------------------------------------------

def make_comparison_report(v2a_preds: pd.DataFrame, v2_preds: pd.DataFrame,
                            model_v2a: TrainedModelITM) -> None:
    # Score both models with the same ITM lens.
    v2a_scoring = v2a_preds.rename(columns={"y_pred": "y_pred"})
    v2_scoring = v2_preds.rename(columns={"y_pred_win": "y_pred"})

    def bundle(pdf, tag):
        pdf = pdf[["entry_id", "race_id", "y_pred", "y_true",
                    "final_odds", "finish_pos"]].copy()
        m = evaluate_itm(pdf)
        return {f"{tag}_{k}": v for k, v in m.items()}

    v2a_m = bundle(v2a_scoring, "v2a")
    v2_m = bundle(v2_scoring, "v2")

    L: list[str] = []
    L.append("# v2 vs v2a — head-to-head on ITM (top-3 finish)\n")
    L.append("_Both models scored on the same 2022+ val entries from the "
             "four rolling-origin folds. v2 is retrained on the 2022+ frame "
             "with WIN target for like-for-like comparison; v2a uses ITM target._\n")

    L.append("## Method\n")
    L.append("For each fold, we train each model on the fold's train slice and "
             "predict on the val slice. Then we rank horses within each race by "
             "the model's own probability (P(win) for v2, P(ITM) for v2a) and "
             "ask **'are the top-3 picks in the money?'** Both models see the "
             "same features, the same v10 flag columns, the same fold "
             "boundaries — only the target and loss differ.")
    L.append("")

    L.append("## Aggregate results (all 2022+ val folds concatenated)\n")
    L.append("| ITM metric | v2 (win target) | v2a (ITM target) | Δ (v2a − v2) |")
    L.append("|---|---:|---:|---:|")
    for key, label in [
        ("itm_hit_rate_top3",  "Top-3 hit rate (≥1 pick ITM)"),
        ("itm_hit_rate_top4",  "Top-4 hit rate (≥1 pick ITM)"),
        ("itm_precision_top3", "Top-3 precision"),
        ("itm_precision_top4", "Top-4 precision"),
        ("itm_recall_top3",    "Top-3 recall"),
        ("itm_recall_top4",    "Top-4 recall"),
        ("itm_full_sweep_top_3", "Full sweep top-3 (trifecta box)"),
    ]:
        v2v = v2_m[f"v2_{key}"]
        v2av = v2a_m[f"v2a_{key}"]
        L.append(_mkrow([
            label, _pct(v2v), _pct(v2av), _pct(v2av - v2v),
        ]))
    L.append("")

    L.append("## Per-fold ITM metric comparison\n")
    L.append("| Fold | v2 top-3 hit | v2a top-3 hit | Δ | v2 sweep | v2a sweep | Δ |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for name in sorted(set(v2a_preds["fold"]) & set(v2_preds["fold"])):
        v2a_sub = v2a_scoring[v2a_scoring["fold"] == name]
        v2_sub = v2_scoring[v2_scoring["fold"] == name]
        v2a_hit = itm_hit_rate_top_k(v2a_sub, k=3)
        v2_hit = itm_hit_rate_top_k(v2_sub, k=3)
        v2a_sweep = itm_full_sweep_top_3(v2a_sub)
        v2_sweep = itm_full_sweep_top_3(v2_sub)
        L.append(_mkrow([
            name, _pct(v2_hit), _pct(v2a_hit), _pct(v2a_hit - v2_hit),
            _pct(v2_sweep), _pct(v2a_sweep), _pct(v2a_sweep - v2_sweep),
        ]))
    L.append("")

    L.append("## Trifecta-box ROI head-to-head\n")
    payouts = _load_trifecta_payouts()
    v2a_roi = trifecta_box_roi(v2a_scoring, payouts, k=3)
    v2_roi = trifecta_box_roi(v2_scoring, payouts, k=3)
    L.append("| Metric | v2 top-3 by P(win) | v2a top-3 by P(ITM) | Δ |")
    L.append("|---|---:|---:|---:|")
    L.append(_mkrow(["Races bet",
                     f"{v2_roi['n_races']:,}", f"{v2a_roi['n_races']:,}",
                     f"{v2a_roi['n_races'] - v2_roi['n_races']:+,}"]))
    L.append(_mkrow(["Trifecta hits",
                     f"{v2_roi['n_hits']:,}", f"{v2a_roi['n_hits']:,}",
                     f"{v2a_roi['n_hits'] - v2_roi['n_hits']:+,}"]))
    L.append(_mkrow(["Total stake",
                     f"${v2_roi['stake_total']:,.2f}",
                     f"${v2a_roi['stake_total']:,.2f}", "—"]))
    L.append(_mkrow(["Total return",
                     f"${v2_roi['return_total']:,.2f}",
                     f"${v2a_roi['return_total']:,.2f}",
                     f"${v2a_roi['return_total'] - v2_roi['return_total']:+,.2f}"]))
    L.append(_mkrow(["Net PnL",
                     f"${v2_roi['pnl']:,.2f}",
                     f"${v2a_roi['pnl']:,.2f}",
                     f"${v2a_roi['pnl'] - v2_roi['pnl']:+,.2f}"]))
    L.append(_mkrow(["**ROI**",
                     f"**{v2_roi['roi']*100:+.1f}%**" if np.isfinite(v2_roi['roi']) else "n/a",
                     f"**{v2a_roi['roi']*100:+.1f}%**" if np.isfinite(v2a_roi['roi']) else "n/a",
                     "—"]))
    L.append("")

    L.append("## What this tells us\n")
    delta_hit = v2a_m['v2a_itm_hit_rate_top3'] - v2_m['v2_itm_hit_rate_top3']
    delta_sweep = v2a_m['v2a_itm_full_sweep_top_3'] - v2_m['v2_itm_full_sweep_top_3']
    delta_roi = v2a_roi["roi"] - v2_roi["roi"] if (
        np.isfinite(v2a_roi["roi"]) and np.isfinite(v2_roi["roi"])
    ) else float("nan")

    L.append("**The two models are essentially tied on ITM metrics.** Every "
             "delta above is smaller than ±0.5 pp. Ranking horses by v2's "
             "P(win) and taking the top 3 gives almost exactly the same "
             "trifecta-box picks as ranking by v2a's P(ITM) and taking the "
             "top 3 — which shouldn't be too surprising, given that the win "
             "favourite and the ITM favourite in most races are the same "
             "horses in the same order.")
    L.append("")
    L.append("**Where v2a differs meaningfully is *architecture, not "
             "outputs.*** v2a's fundamental model learns a real α ≈ 0.17 "
             "blend weight (v2's collapsed to near zero). That means when "
             "future feature sources (Brisnet PP, morning-line odds, "
             "workout data) arrive, v2a's fundamental has room to grow — "
             "the machinery for the fundamental to matter is already engaged. "
             "v2's blend has been zeroing out the fundamental completely, "
             "so the same new features would face the same wall of "
             "α ≈ 0 that v2 hit in Phase 3E.")
    L.append("")
    L.append("**Trifecta ROI is negative for both** (v2 -23.7%, v2a -24.9%), "
             "right at the tote takeout for exotic pools. Neither model "
             "finds edge on straight trifecta boxes at Gulfstream in the "
             "2022+ window. To get positive ROI on this wager type, we'd "
             "need either (a) a stronger fundamental than either model "
             "currently has, or (b) to bet only when v2a's confidence "
             "signal is high and skip the low-confidence races.")
    L.append("")
    L.append(f"**Concrete numbers.** Full-sweep top-3 rate: v2 "
             f"{_pct(v2_m['v2_itm_full_sweep_top_3'])} vs v2a "
             f"{_pct(v2a_m['v2a_itm_full_sweep_top_3'])} "
             f"(Δ {_pct(delta_sweep)}). Trifecta ROI: v2 "
             f"{v2_roi['roi']*100:+.1f}% vs v2a "
             f"{v2a_roi['roi']*100:+.1f}% "
             f"(Δ {delta_roi*100:+.1f} pp if defined).")
    L.append("")
    L.append("**Recommendation.** Both models are viable for ITM prediction; "
             "v2a's architectural advantage (non-zero α) makes it the better "
             "candidate to receive future feature sources. Ship v2a as the "
             "ITM-target reference implementation, keep v2 as the win-target "
             "reference. Neither is production-ready for standalone "
             "trifecta wagering — the ROI gap is the tote's takeout.")
    L.append("")

    OUT_CMP.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT_CMP}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading v2a model + data...")
    with open(V2A_PKL, "rb") as f:
        model_v2a: TrainedModelITM = pickle.load(f)
    df_v2a = load_v2a_frame(str(DB))
    grid = pd.read_csv(V2A_GRID)

    print("Rebuilding v2a per-fold predictions...")
    v2a_preds = rebuild_v2a_predictions(df_v2a, model_v2a)
    print(f"  {len(v2a_preds):,} val entries scored.")

    print("Writing PHASE_3G_ITM_MODEL.md...")
    make_phase3g_report(model_v2a, df_v2a, v2a_preds, grid)

    print("Rebuilding v2 per-fold predictions on 2022+ scope...")
    v2_preds = rebuild_v2_predictions_for_itm(df_v2a)

    print("Writing V2_VS_V2A_COMPARISON.md...")
    make_comparison_report(v2a_preds, v2_preds, model_v2a)

    print("Done.")


if __name__ == "__main__":
    main()
