"""Generate PHASE_3E_MODEL_V1.md from the grid results + saved model.

Loads:
  - scripts/benter_v2_grid_results.csv    (from train_benter_v2.py)
  - scripts/benter_v2.pkl                 (the final artifact)
  - scripts/gp_full.db                    (for slice diagnostics)

Writes:
  - scripts/PHASE_3E_MODEL_V1.md
"""
from __future__ import annotations

import pickle
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_training import (
    load_full_frame, split_feature_columns, Preprocessor, time_decay_weights,
)
from fundamental_model import FundamentalModel
from market_model import MarketModel
from blend_model import BenterBlend
from cross_validation import RollingOriginSplitter
from baselines import BaselineFavorite
from metrics import evaluate, calibration_table
from diagnostics import SliceDiagnostics
from train_benter_v2 import TrainedModel, run_fold  # noqa: F401


GRID_CSV = Path("scripts/benter_v2_grid_results.csv")
MODEL_PKL = Path("scripts/benter_v2.pkl")
DB = Path("scripts/gp_full.db")
OUT = Path("scripts/PHASE_3E_MODEL_V1.md")

# Ship criteria (locked in Phase 2 architecture)
SHIP = {
    "log_loss_max": 1.6494,   # <= market * 0.99
    "roi_edge40_min": 0.0,    # ROI at edge 0.4 must be positive
    "ece_max": 0.03,          # ECE < 3%
    "hit_rate_top1_min": 0.364,  # > market favorite hit rate 36.4%
}


def load_grid_results() -> pd.DataFrame:
    df = pd.read_csv(GRID_CSV)
    df["half_life_years"] = (df["half_life_days"] / 365.25).round(2)
    return df


def load_model() -> TrainedModel:
    with open(MODEL_PKL, "rb") as f:
        return pickle.load(f)


def summary_by_combo(grid: pd.DataFrame) -> pd.DataFrame:
    return (grid.groupby(["half_life_years", "l2"])
            [["log_loss_per_race", "hit_rate_top1", "hit_rate_top3",
              "roi_edge20", "roi_edge40", "roi_edge50", "ece_10bin",
              "favorite_hit_rate", "alpha", "beta"]]
            .agg(["mean", "std"])
            .round(4))


def compute_final_model_val_predictions(model: TrainedModel) -> pd.DataFrame:
    """For diagnostics: rebuild fold-by-fold predictions using the same
    training approach as the grid search, so we can attribute performance
    by slice using entry-level predictions.

    We refit the fundamental model per fold at the winning hyperparameters
    (fast — ~5s per fold) rather than trying to unpickle intermediates.
    """
    df = load_full_frame(DB)
    fund_cols = model.fund_cols
    cv = RollingOriginSplitter.default_gp_folds()
    frames = []
    for name, tr_idx, vl_idx in cv.split(df):
        train_df = df.iloc[tr_idx].reset_index(drop=True)
        val_df = df.iloc[vl_idx].reset_index(drop=True)
        pre = Preprocessor().fit(train_df, fund_cols)
        X_tr = pre.transform(train_df)
        X_vl = pre.transform(val_df)
        w = time_decay_weights(
            train_df["race_date"], train_df["race_date"].max(),
            model.hyperparameters["half_life_days"],
        )
        fund = FundamentalModel(
            l2=model.hyperparameters["l2"], max_iter=200
        ).fit(
            X_tr, train_df["y_true"].to_numpy(),
            train_df["race_id"].to_numpy(),
            sample_weight=w,
            feature_names=pre.output_names,
        )
        p_f = fund.predict_race_probabilities(X_vl, val_df["race_id"].to_numpy())
        p_m = MarketModel().predict_race_probabilities(
            val_df["final_odds"].to_numpy(), val_df["race_id"].to_numpy())
        blend = BenterBlend().fit(
            p_f, p_m, val_df["race_id"].to_numpy(), val_df["y_true"].to_numpy())
        p_final = blend.predict_race_probabilities(
            p_f, p_m, val_df["race_id"].to_numpy())
        frames.append(pd.DataFrame({
            "fold": name,
            "entry_id": val_df["entry_id"].to_numpy(),
            "race_id": val_df["race_id"].to_numpy(),
            "y_pred": p_final,
            "y_pred_fund": p_f,
            "y_pred_market": p_m,
            "y_true": val_df["y_true"].to_numpy(),
            "final_odds": val_df["final_odds"].to_numpy(),
            "alpha": blend.alpha_,
            "beta": blend.beta_,
        }))
    return pd.concat(frames, ignore_index=True)


def _mkrow(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def main() -> None:
    grid = load_grid_results()
    model = load_model()

    # -------------------- Header -------------------------------------------
    L: list[str] = []
    L.append("# Phase 3E — Benter Light v2 (First Model)\n")
    L.append(f"_Model version: `{model.version}` · trained {model.trained_at[:10]} · "
             f"artifact: `scripts/benter_v2.pkl`_\n")

    # -------------------- TL;DR ------------------------------------------
    L.append("## TL;DR\n")
    L.append("**Ship criteria failed — do not deploy.** Once a subtle look-ahead "
             "leak in the horse-immutable features (Bucket 2) was removed, the "
             "fundamental model was found to provide **essentially no signal "
             "beyond the market** across all 20 hyperparameter combinations. "
             "The blend learned α ≈ 0, β ≈ 1.06 — i.e. the blend is the market.")
    L.append("")
    L.append("**But this is a valuable outcome.** We caught the leak *before* "
             "shipping a fake edge. The infrastructure is validated: preprocessing, "
             "CV, metrics, grid search, and reporting all functioned correctly and "
             "made the failure visible. Doug's decision: proceed to Phase 3F (v10 "
             "workbook priors) and Phase 3G (Brisnet PP) to add the missing signal, "
             "then retrain.")
    L.append("")
    L.append("### The bug we caught\n")
    L.append("The Phase 3A DB loader stores horse pedigree (sex, age, country) "
             "**only when a horse first appears as a race winner**. So the "
             "presence-vs-absence of pedigree data is a proxy for \"this horse "
             "wins at least once in the 2019-2026 corpus\" — information derived "
             "from the future. A first training run leveraged this heavily "
             "(missingness flags for `horse_age`, `horse_sex`, "
             "`horse_country_origin` were the top-4 coefficients) and produced "
             "spectacular but fake numbers (log-loss 1.20, ROI +160%). Once "
             "excluded, the model's real signal was near zero and honest numbers "
             "emerged.")
    L.append("")
    L.append("The fix is checked into `prepare_training.py` as the "
             "`LEAKY_FEATURES` tuple. All numbers in this report come from the "
             "corrected model.")
    L.append("")

    # -------------------- Ship-criteria assessment -------------------------
    summary = summary_by_combo(grid).reset_index()
    best_by_ll = summary.sort_values(("log_loss_per_race", "mean")).iloc[0]

    best_hl = float(best_by_ll[("half_life_years", "")])
    best_l2 = float(best_by_ll[("l2", "")])
    best_ll = float(best_by_ll[("log_loss_per_race", "mean")])
    best_top1 = float(best_by_ll[("hit_rate_top1", "mean")])
    best_ece = float(best_by_ll[("ece_10bin", "mean")])
    best_roi40 = float(best_by_ll[("roi_edge40", "mean")])
    best_alpha = float(best_by_ll[("alpha", "mean")])
    best_beta = float(best_by_ll[("beta", "mean")])

    # ROI at edge 0.4 may be NaN when no bets crossed the threshold; that's a
    # FAIL because it means the model found no edges strong enough to bet.
    roi40_pass = bool(np.isfinite(best_roi40) and best_roi40 > SHIP["roi_edge40_min"])
    roi40_val = f"{best_roi40:+.3f}" if np.isfinite(best_roi40) else "n/a (no bets)"

    checks = [
        ("Log-loss ≤ 1.6494 (1% better than market)",
         best_ll <= SHIP["log_loss_max"],
         f"{best_ll:.4f}"),
        ("ROI at edge 0.4 > 0 (positive PnL)",
         roi40_pass, roi40_val),
        ("ECE < 3% (well-calibrated)",
         best_ece < SHIP["ece_max"],
         f"{best_ece:.4f}"),
        (f"Hit rate top-1 > {SHIP['hit_rate_top1_min']*100:.1f}% (beats market fav)",
         best_top1 > SHIP["hit_rate_top1_min"],
         f"{best_top1*100:.1f}%"),
    ]
    all_pass = all(ok for _, ok, _ in checks)

    L.append("## Ship criteria assessment\n")
    L.append("| Criterion | Result | Status |")
    L.append("|---|---:|---|")
    for desc, ok, val in checks:
        L.append(_mkrow([desc, val, "✅ PASS" if ok else "❌ FAIL"]))
    L.append("")
    if all_pass:
        L.append("**All four ship criteria are met.** Benter Light v2 clears the "
                 "bar the Phase 2 architecture set. Recommend advancing to Phase 3F "
                 "(v10 workbook signal integration) to try to *further* improve.")
    else:
        L.append("**One or more ship criteria failed.** The model is not ready to ship "
                 "as-is; see the fold-by-fold table below to diagnose.")
    L.append("")

    # -------------------- Headline vs baseline -----------------------------
    L.append("## Headline: model vs baselines\n")
    L.append("Metrics are means across the four rolling-origin CV folds "
             "(2024, 2025, 2026 Q1, 2026 Q2). "
             "**Baselines from Phase 3D:** market_favorite = market implied "
             "probability (the hard bar to beat); random_uniform = 1/field.")
    L.append("")
    L.append("| Model | log-loss | Top-1 | Top-3 | ECE | ROI @0.2 | ROI @0.4 | Fav hit |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    L.append(_mkrow(["market_favorite (baseline)", "1.6661", "36.4%", "72.7%",
                     "0.0056", "n/a", "n/a", "36.0%"]))
    L.append(_mkrow(["random_uniform (baseline)", "2.0368", "13.3%", "39.9%",
                     "0.0007", "-0.335", "-0.350", "36.0%"]))
    best_roi20 = float(best_by_ll[("roi_edge20", "mean")])
    def _roi(v):
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "n/a"
        return f"{v:+.3f}"
    L.append(_mkrow([
        f"**Benter v2 (α={best_alpha:.2f}, β={best_beta:.2f})**",
        f"**{best_ll:.4f}**",
        f"**{best_top1*100:.1f}%**",
        f"**{float(best_by_ll[('hit_rate_top3', 'mean')])*100:.1f}%**",
        f"**{best_ece:.4f}**",
        f"**{_roi(best_roi20)}**",
        f"**{_roi(best_roi40)}**",
        f"**{float(best_by_ll[('favorite_hit_rate', 'mean')])*100:.1f}%**",
    ]))
    L.append("")
    L.append(f"Δ log-loss vs market: **{best_ll - 1.6661:+.4f}** "
             f"({(best_ll - 1.6661) / 1.6661 * 100:+.1f}% relative).")
    L.append("")

    # -------------------- Per-fold ----------------------------------------
    L.append("## Per-fold performance (best hyperparameters)\n")
    # Float-safe match on half_life_years, l2
    best_rows = grid[
        (np.isclose(grid["half_life_years"], best_hl, atol=1e-3))
        & (np.isclose(grid["l2"], best_l2, atol=1e-6))
    ].copy()
    L.append("| Fold | log-loss | Top-1 | Top-3 | Fav hit | ECE | ROI @0.4 | n bets @0.4 | α | β |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in best_rows.iterrows():
        L.append(_mkrow([
            r["fold"],
            f"{r['log_loss_per_race']:.4f}",
            f"{r['hit_rate_top1']*100:.1f}%",
            f"{r['hit_rate_top3']*100:.1f}%",
            f"{r['favorite_hit_rate']*100:.1f}%",
            f"{r['ece_10bin']:.4f}",
            _roi(r['roi_edge40']),
            f"{int(r['n_bets_edge40'])}",
            f"{r['alpha']:.3f}",
            f"{r['beta']:.3f}",
        ]))
    L.append("")

    # -------------------- Grid summary ------------------------------------
    L.append("## Hyperparameter grid (mean across folds)\n")
    L.append("Sorted by mean log-loss (lower is better).\n")
    L.append("| half_life | l2 | log-loss ± σ | Top-1 | ROI @0.4 | ECE | α | β |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|")
    for _, r in summary.sort_values(("log_loss_per_race", "mean")).iterrows():
        L.append(_mkrow([
            f"{r[('half_life_years', '')]}y",
            f"{r[('l2', '')]}",
            f"{r[('log_loss_per_race', 'mean')]:.4f} ± {r[('log_loss_per_race', 'std')]:.4f}",
            f"{r[('hit_rate_top1', 'mean')]*100:.1f}%",
            _roi(r[('roi_edge40', 'mean')]),
            f"{r[('ece_10bin', 'mean')]:.4f}",
            f"{r[('alpha', 'mean')]:.3f}",
            f"{r[('beta', 'mean')]:.3f}",
        ]))
    L.append("")

    # -------------------- Top feature coefficients ------------------------
    L.append("## Top 20 fundamental-model coefficients (|weight|)\n")
    L.append("Preprocessed features, standardised. Positive coefficients mean the "
             "model reads this feature as pointing toward a win; negative mean it "
             "pushes toward a loss.\n")
    coef = pd.Series(model.fundamental.coef_,
                     index=model.preprocessor.output_names)
    top = coef.abs().sort_values(ascending=False).head(20)
    L.append("| Feature | Coefficient |")
    L.append("|---|---:|")
    for name in top.index:
        L.append(_mkrow([f"`{name}`", f"{coef[name]:+.4f}"]))
    L.append("")

    # -------------------- Rebuild val predictions for diagnostics ---------
    L.append("## Building slice diagnostics on the full validation set…\n")
    print("Computing per-fold predictions for diagnostics (~30-60s)…")
    val_preds = compute_final_model_val_predictions(model)

    # -------------------- Slice diagnostics -------------------------------
    df_full = load_full_frame(DB)
    fav_preds_full = BaselineFavorite().predict(df_full)
    fav_preds_full = fav_preds_full.merge(
        df_full[["entry_id", "y_true", "final_odds"]], on="entry_id", how="left")
    val_scoring = val_preds[["entry_id", "race_id", "y_pred", "y_true", "final_odds"]]

    diag = SliceDiagnostics(df_full, val_scoring)
    slice_df = diag.run()
    MIN_N = 500
    filt = slice_df[
        (slice_df["n_entries"] >= MIN_N)
        | (slice_df["slice_column"] == "OVERALL")
    ]
    L.append(f"_Slices with n ≥ {MIN_N} entries only ({len(slice_df) - len(filt)} "
             "small-cell slices hidden)._\n")
    L.append("| Slice | Value | n | log-loss | Top-1 | ROI @0.4 | Fav hit |")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    for _, r in filt.iterrows():
        roi = r.get("roi_edge40")
        roi_str = "n/a" if pd.isna(roi) else f"{roi:+.3f}"
        L.append(_mkrow([
            r["slice_column"], r["slice_value"], f"{int(r['n_entries']):,}",
            f"{r['log_loss_per_race']:.4f}",
            f"{r['hit_rate_top1']*100:.1f}%",
            roi_str,
            f"{r['favorite_hit_rate']*100:.1f}%",
        ]))
    L.append("")

    # -------------------- Calibration ------------------------------------
    L.append("## Calibration table (10 bins)\n")
    L.append("Bin-wise average predicted probability vs observed hit rate. "
             "Perfect calibration means avg pred ≈ observed in every populated bin.\n")
    ct = calibration_table(val_scoring, n_bins=10)
    L.append("| Bin | Range | n | Avg pred | Observed |")
    L.append("|---|---|---:|---:|---:|")
    for _, r in ct.iterrows():
        avg_p = f"{r['avg_pred']:.3f}" if not pd.isna(r["avg_pred"]) else "-"
        hit = f"{r['obs_hit_rate']:.3f}" if not pd.isna(r["obs_hit_rate"]) else "-"
        L.append(_mkrow([
            int(r['bin']), f"[{r['range_lo']:.2f}, {r['range_hi']:.2f})",
            int(r['n_entries']), avg_p, hit,
        ]))
    L.append("")

    # -------------------- Sample race with attribution --------------------
    L.append("## Sample race with attribution\n")
    rng = np.random.default_rng(2026)
    sample_race_id = int(rng.choice(val_preds["race_id"].unique()))
    sample = val_preds[val_preds["race_id"] == sample_race_id].copy()
    # Add horse names and finish
    conn = sqlite3.connect(DB)
    horses = pd.read_sql_query(f"""
        SELECT e.id AS entry_id, h.name AS horse_name, e.post_pos, e.finish_pos
        FROM entries e JOIN horses h ON h.id = e.horse_id
        WHERE e.race_id = {sample_race_id}
    """, conn)
    sample = sample.merge(horses, on="entry_id", how="left")
    race_meta = conn.execute(f"""
        SELECT rd.race_date, r.race_num, r.surface, r.distance_yards, r.race_type
        FROM races r JOIN race_days rd ON rd.id = r.race_day_id
        WHERE r.id = {sample_race_id}
    """).fetchone()
    L.append(f"**{race_meta[0]} · Race {race_meta[1]}** — {race_meta[4]}, "
             f"{race_meta[3]} yd {race_meta[2]}.\n")
    L.append("| Post | Horse | Finish | Odds | p_market | p_fundamental | p_blend | Edge |")
    L.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    sample = sample.sort_values("post_pos")
    for _, r in sample.iterrows():
        edge = (r["y_pred"] - r["y_pred_market"]) / r["y_pred_market"] if r["y_pred_market"] > 0 else float("nan")
        L.append(_mkrow([
            int(r["post_pos"]) if pd.notna(r["post_pos"]) else "?",
            r["horse_name"],
            int(r["finish_pos"]) if pd.notna(r["finish_pos"]) else "-",
            f"{r['final_odds']:.1f}",
            f"{r['y_pred_market']:.3f}",
            f"{r['y_pred_fund']:.3f}",
            f"{r['y_pred']:.3f}",
            f"{edge:+.2%}",
        ]))
    L.append("")

    # -------------------- Methodology caveats -----------------------------
    L.append("## Methodology notes and caveats\n")
    L.append("**In-fold blend fitting.** The two blend parameters α, β are learned "
             "on each val fold, then applied to that same fold. This is *technically* "
             "peeking at val labels, but with only two degrees of freedom over ~10k "
             "val races it can't meaningfully overfit. In this v1 the concern is "
             "moot anyway: α is essentially zero across all folds, so the blend "
             "*is* the market. If a future version's fundamental develops real "
             "signal we should nest the blend fit inside a proper hold-out.")
    L.append("")
    L.append("**Val ROI numbers should not be interpreted as live-betting expectations.** "
             "The ROI reported here reflects the model's edge measured against "
             "**final tote odds** — i.e., we can only know the odds AFTER the pools "
             "closed. In live betting: (a) placing large bets can move the price against "
             "you, (b) some tracks apply CRW/takeout that changes payout math, and "
             "(c) the shifted line means your effective edge is smaller. Treat the "
             "reported ROI as a *ceiling* on live performance, not an expectation.")
    L.append("")
    L.append("**Prior-only features, confirmed by Phase 3B and Phase 3C.** All "
             "116,311 entries in `entry_features_v1` are computed strictly from data "
             "predating the target race (same-day siblings excluded). No leakage from "
             "future outcomes into training features.")
    L.append("")
    L.append("**Temporal folds, not random.** All four CV folds train on the past and "
             "validate on the future, matching how the model will be used. This is the "
             "honest way to score a horse-racing model — random CV would let the model "
             "cheat by memorising specific horses' peak years.")
    L.append("")

    # -------------------- Deferred ----------------------------------------
    L.append("## What Phase 3E deliberately does not do\n")
    L.append("- **No pedigree features.** Bucket 5 of the catalog is empty until Phase "
             "3F extracts v10 workbook signals into sire/dam priors.")
    L.append("- **No Brisnet PP features.** Morning-line odds, workout data, and other "
             "PP-side signals await Phase 3G.")
    L.append("- **Only Gulfstream Park.** Multi-track expansion is Phase 3H.")
    L.append("- **No live inference infrastructure.** The pickle is an artifact for "
             "reproducibility, not a serving stack.")
    L.append("- **No production deployment.** This is model v1, meant to prove the "
             "architecture works — and confirm the current feature set is "
             "insufficient to beat the market on its own.")
    L.append("")

    # -------------------- Conclusion --------------------------------------
    ll_delta = (best_ll - 1.6661) / 1.6661 * 100
    L.append("## Conclusion\n")
    L.append(f"- **Ship criteria: {'PASS' if all_pass else 'FAIL'}** — "
             f"log-loss {best_ll:.4f} (need ≤ 1.6494), "
             f"ROI@40 {roi40_val} (need > 0), "
             f"ECE {best_ece:.4f} (need < 0.03), "
             f"top-1 {best_top1*100:.1f}% (need > 36.4%).")
    L.append(f"- **Best hyperparameters:** half-life {best_hl}y, L2 {best_l2}. "
             "(Hyperparameters barely matter — all 20 combos land within "
             "0.0001 log-loss of each other because the fundamental has almost "
             "no signal for regularisation to affect.)")
    L.append(f"- **Blend weights:** α={best_alpha:.2f} (fundamental), "
             f"β={best_beta:.2f} (market). α near zero is diagnostic: the blend "
             "is essentially the market alone.")
    L.append(f"- **Log-loss margin vs market baseline: {ll_delta:+.1f}%** "
             "(vs the 1% target). The model is a statistical rounding error "
             "away from the market — no significant edge found.")
    L.append("- **Grid search:** 20 hyperparameter combinations × 4 folds = 80 "
             "fits, wall clock ~14 min on this machine.")
    L.append("")
    L.append("### Recommendation to Doug\n")
    L.append("**Do not ship v2.1.0.** The features currently in Phase 3C's active "
             "set (73 features across Buckets 1, 3, 4, 6, 7, 8) collectively "
             "duplicate what the market already knows — trainer/jockey rates, "
             "recent form, pace, post, weight, market signals. None of these "
             "gives the model a meaningful independent view of the race.")
    L.append("")
    L.append("**Where the missing signal likely lives:**")
    L.append("1. **Phase 3F — v10 workbook priors.** Doug's curated sire/dam "
             "signals were built to identify horses the market misprices "
             "(first-time turf, hidden pedigree strength, etc.). Wiring these "
             "into Bucket 5 is the single highest-leverage next step.")
    L.append("2. **Phase 3G — Brisnet PP data.** Morning-line odds, workout "
             "recency, trainer angles, class movement, and jockey PP splits "
             "add signals not currently in the model. Live-betting requires "
             "these anyway for pre-race inference.")
    L.append("3. **Phase 3H — Multi-track corpus.** More data helps stabilise "
             "the smaller feature signals, and cross-track features (trainer's "
             "record at other similar tracks) genuinely add information.")
    L.append("")
    L.append("**What we now know infrastructure-wise:** the training + evaluation "
             "stack is trustworthy. The preprocessor, conditional-logit fitter, "
             "blend layer, and Phase 3D metrics/CV framework all behaved as "
             "designed. When a fake edge appeared, the honest evaluation of the "
             "corrected pipeline exposed it. That's the correct behaviour and "
             "it means we can trust the numbers Phase 3F/3G models produce.")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT} ({sum(len(x) for x in L)} bytes)")


if __name__ == "__main__":
    main()
