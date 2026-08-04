"""Phase 5A: does the Brisnet PP feed change DPv1's predictions?

This is a **fitness-of-approach check, not a retraining.** The PP catalogue
covers 220 races; DPv1 trains on 28,105. Nothing here is evidence that a
PP-augmented model is better in general — the question is narrower and
answerable at this sample size:

    Conditional on what DPv1 already predicts from result charts and the tote,
    do the PP features carry any residual information about who finishes in
    the money — and does adding them move the picks?

Method
------
1. **Baseline.** DPv1's own out-of-sample fold predictions for 2026
   (``dpv1_fold_predictions.csv``, ``fold_val2026``: fundamental model trained
   on 2022-2025, never on 2026). Both the blended ``y_pred`` and the
   fundamental-only ``p_fund`` are carried, because "PP beats charts" and
   "PP beats charts + market" are different claims.

2. **Augmented.** An L2-penalised logistic fit on the PP subset with
   ``logit(baseline)`` as a fixed **offset**. The offset means the augmented
   model can only earn its keep by explaining what the baseline got wrong; a
   coefficient vector of zero reproduces the baseline exactly.

3. **Honest evaluation.** Leave-one-race-day-out grouped CV inside the subset,
   so a fitted day never scores itself. Every reported gain is out-of-fold.

4. **Noise floor.** The same procedure on permuted PP rows (shuffled within
   the subset, labels and baseline untouched) — 40 draws. With 1,579 rows and
   ~45 predictors a fitting procedure will find *something*; the permutation
   distribution says how much "something" is worth nothing. A real gain has to
   clear it.

Usage
-----
    python scripts_dpv1/pp_prediction_test.py
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brisnet_pp_parser import PP_FEATURE_COLUMNS  # noqa: E402

log = logging.getLogger("pp_prediction_test")

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
DB = REPO / "scripts" / "racing_full.db"
FOLD_PREDS = DPV1_DIR / "dpv1_fold_predictions.csv"
OUT_JSON = DPV1_DIR / "phase5a_pp_test.json"
OUT_CSV = DPV1_DIR / "phase5a_pp_predictions.csv"

# Excluded from the test: measured under 50% coverage on the matched entries
# (see PHASE_5A_PP_PARSER.md for the per-feature cause). Four of the six are
# also redundant with chart-derived DPv1 features that have full coverage.
LOW_COVERAGE = (
    "pp_best_speed_aw", "pp_best_speed_turf", "pp_class_delta",
    "pp_distance_delta", "pp_last_class", "pp_last_dist",
)
CATEGORICAL = ("pp_running_style",)

L2 = 5.0                 # ridge strength on the augmentation coefficients
N_PERMUTATIONS = 40
RNG_SEED = 20260803

# A "longshot value flag": the model likes a horse the market does not.
LONGSHOT_MIN_ODDS = 8.0
VALUE_RATIO = 1.25


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def load_subset() -> pd.DataFrame:
    conn = sqlite3.connect(DB)
    pp = pd.read_sql_query("SELECT * FROM entry_pp_features", conn)
    conn.close()
    base = pd.read_csv(FOLD_PREDS)
    base = base[base["fold"] == "fold_val2026"]
    df = pp.merge(base, on="entry_id", how="inner", suffixes=("", "_b"))
    df = df.sort_values(["race_date", "race_id", "entry_id"]).reset_index(drop=True)
    log.info("PP entries: %d | with a 2026 out-of-fold DPv1 prediction: %d "
             "(%d races, %d race-days)",
             len(pp), len(df), df["race_id"].nunique(),
             df["race_date"].nunique())
    return df


def design_matrix(df: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray, list[str]]:
    """Median-impute + standardise, with an explicit missing flag per column.

    The flag matters: "Brisnet has no speed figure for this horse" is itself a
    signal (first-time starter, long layoff), and silently imputing it away
    would hide exactly the kind of thing the test is looking for.
    """
    blocks, names = [], []
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
        miss = ~np.isfinite(v)
        med = np.nanmedian(v) if np.isfinite(v).any() else 0.0
        v = np.where(miss, med, v)
        sd = v.std()
        blocks.append((v - v.mean()) / sd if sd > 1e-9 else np.zeros_like(v))
        names.append(c)
        if miss.any() and miss.mean() < 0.999:
            blocks.append(miss.astype(float) - miss.mean())
            names.append(f"{c}__missing")
    for c in CATEGORICAL:
        if c not in df.columns:
            continue
        s = df[c].fillna("NA").astype(str)
        for lvl in sorted(s.unique()):
            if (s == lvl).sum() < 25:
                continue
            d = (s == lvl).astype(float).to_numpy()
            blocks.append(d - d.mean())
            names.append(f"{c}={lvl}")
    return np.column_stack(blocks), names


# ---------------------------------------------------------------------------
# Offset logistic
# ---------------------------------------------------------------------------

def fit_offset_logistic(X: np.ndarray, y: np.ndarray, offset: np.ndarray,
                        l2: float) -> np.ndarray:
    """Ridge logistic with a fixed offset. Returns [intercept, *coefs]."""
    n, k = X.shape

    def nll(w):
        z = offset + w[0] + X @ w[1:]
        # log(1+exp(z)) computed stably
        ll = np.sum(np.logaddexp(0.0, z) - y * z)
        return ll / n + l2 * np.dot(w[1:], w[1:]) / (2 * n)

    def grad(w):
        z = offset + w[0] + X @ w[1:]
        r = 1.0 / (1.0 + np.exp(-z)) - y
        g = np.empty_like(w)
        g[0] = r.sum() / n
        g[1:] = (X.T @ r) / n + l2 * w[1:] / n
        return g

    res = minimize(nll, np.zeros(k + 1), jac=grad, method="L-BFGS-B",
                   options={"maxiter": 500})
    return res.x


def oof_predict(X: np.ndarray, y: np.ndarray, offset: np.ndarray,
                groups: np.ndarray, l2: float) -> np.ndarray:
    """Leave-one-group-out predictions. Groups are race-days."""
    out = np.empty_like(offset)
    for g in np.unique(groups):
        te = groups == g
        tr = ~te
        w = fit_offset_logistic(X[tr], y[tr], offset[tr], l2)
        z = offset[te] + w[0] + X[te] @ w[1:]
        out[te] = 1.0 / (1.0 + np.exp(-z))
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(p)
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks over ties
    s = pd.Series(p)
    ranks = s.rank(method="average").to_numpy()
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    return {"log_loss": log_loss(y, p), "auc": auc(y, p), "brier": brier(y, p)}


def top3_sets(df: pd.DataFrame, col: str) -> dict:
    out = {}
    for rid, g in df.groupby("race_id"):
        out[rid] = set(g.nlargest(min(3, len(g)), col)["entry_id"])
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> dict:
    df = load_subset()
    y = df["y_true"].to_numpy(dtype=float)
    groups = df["race_date"].to_numpy()

    cols = [c for c in PP_FEATURE_COLUMNS
            if c not in LOW_COVERAGE and c not in CATEGORICAL]
    X, names = design_matrix(df, cols)
    log.info("design matrix: %d rows x %d predictors (%d PP features + "
             "missing flags + running style)", *X.shape, len(cols))

    report: dict = {
        "n_entries": int(len(df)),
        "n_races": int(df["race_id"].nunique()),
        "n_race_days": int(df["race_date"].nunique()),
        "by_track": df["track"].value_counts().to_dict(),
        "itm_rate": float(y.mean()),
        "n_predictors": int(X.shape[1]),
        "l2": L2,
        "baselines": {},
    }

    rng = np.random.default_rng(RNG_SEED)
    for base_name, base_col in (("blend", "y_pred"), ("fundamental", "p_fund")):
        p0 = df[base_col].to_numpy(dtype=float)
        off = logit(p0)
        p1 = oof_predict(X, y, off, groups, L2)
        df[f"p_aug_{base_name}"] = p1

        m0, m1 = metrics(y, p0), metrics(y, p1)
        gain = m0["log_loss"] - m1["log_loss"]

        # Compare like with like: the model emits P(ITM), so the market side
        # must be the Harville P(ITM) that train_dpv1 derives from normalised
        # win odds (``p_market`` in the fold predictions), NOT the raw implied
        # win probability 1/(odds+1) — that comparison flags roughly half the
        # field as value and means nothing.
        pm = df["p_market"].to_numpy(dtype=float)
        odds = df["final_odds"].to_numpy(dtype=float)
        longshot = odds >= LONGSHOT_MIN_ODDS

        def flag_shift(p_new: np.ndarray) -> float:
            """ITM rate of newly-flagged minus newly-unflagged longshots.

            Positive = the augmentation moved the value flags toward horses
            that actually hit the board.
            """
            a = (p_new > pm * VALUE_RATIO) & longshot & ~(p0 > pm * VALUE_RATIO)
            r = (p0 > pm * VALUE_RATIO) & longshot & ~(p_new > pm * VALUE_RATIO)
            if a.sum() < 10 or r.sum() < 10:
                return float("nan")
            return float(y[a].mean() - y[r].mean())

        # Noise floor: permute the PP rows, keep y and the baseline in place.
        # The flag differential gets its own null — it is a subgroup statistic
        # chosen after seeing the log-loss result, so it needs one.
        perm_gains, perm_flags = [], []
        for _ in range(N_PERMUTATIONS):
            idx = rng.permutation(len(df))
            pp_perm = oof_predict(X[idx], y, off, groups, L2)
            perm_gains.append(m0["log_loss"] - log_loss(y, pp_perm))
            perm_flags.append(flag_shift(pp_perm))
        perm_gains = np.array(perm_gains)
        perm_flags = np.array(perm_flags, dtype=float)
        p_value = float((perm_gains >= gain).mean())

        obs_flag = flag_shift(p1)
        pf = perm_flags[np.isfinite(perm_flags)]
        flag_p = (float((pf >= obs_flag).mean())
                  if len(pf) and np.isfinite(obs_flag) else None)

        # Does the augmentation discriminate better *within* the longshot band,
        # even though it discriminates worse overall?
        ls_auc0 = auc(y[longshot], p0[longshot])
        ls_auc1 = auc(y[longshot], p1[longshot])

        # How much do the picks actually move?
        t0, t1 = top3_sets(df, base_col), top3_sets(df, f"p_aug_{base_name}")
        changed = sum(1 for r in t0 if t0[r] != t1[r])
        winner_swap = sum(
            1 for rid, g in df.groupby("race_id")
            if g.loc[g[base_col].idxmax(), "entry_id"]
            != g.loc[g[f"p_aug_{base_name}"].idxmax(), "entry_id"])

        ls0 = (p0 > pm * VALUE_RATIO) & longshot
        ls1 = (p1 > pm * VALUE_RATIO) & longshot

        report["baselines"][base_name] = {
            "baseline": m0,
            "augmented_oof": m1,
            "log_loss_gain": float(gain),
            "auc_gain": float(m1["auc"] - m0["auc"]),
            "permutation_null": {
                "n": N_PERMUTATIONS,
                "mean_gain": float(perm_gains.mean()),
                "sd_gain": float(perm_gains.std()),
                "p95_gain": float(np.percentile(perm_gains, 95)),
                "p_value": p_value,
            },
            "picks": {
                "races": int(df["race_id"].nunique()),
                "top3_changed": int(changed),
                "top3_changed_pct": round(changed / df["race_id"].nunique() * 100, 1),
                "top_pick_changed": int(winner_swap),
                "top_pick_changed_pct": round(winner_swap / df["race_id"].nunique() * 100, 1),
                "mean_abs_prob_shift": float(np.mean(np.abs(p1 - p0))),
                "p90_abs_prob_shift": float(np.percentile(np.abs(p1 - p0), 90)),
            },
            "longshot_value_flags": {
                "definition": f"p_model > {VALUE_RATIO}x market P(ITM) AND "
                              f"odds >= {LONGSHOT_MIN_ODDS}",
                "longshot_band_n": int(longshot.sum()),
                "longshot_band_itm_rate": float(y[longshot].mean()),
                "baseline_flagged": int(ls0.sum()),
                "baseline_flagged_itm": float(y[ls0].mean()) if ls0.sum() else None,
                "augmented_flagged": int(ls1.sum()),
                "augmented_flagged_itm": float(y[ls1].mean()) if ls1.sum() else None,
                "added": int((ls1 & ~ls0).sum()),
                "removed": int((ls0 & ~ls1).sum()),
                "added_itm_rate": (float(y[ls1 & ~ls0].mean())
                                   if (ls1 & ~ls0).sum() else None),
                "removed_itm_rate": (float(y[ls0 & ~ls1].mean())
                                     if (ls0 & ~ls1).sum() else None),
                "added_minus_removed_itm": (None if not np.isfinite(obs_flag)
                                            else round(float(obs_flag), 4)),
                "permutation_p_value": flag_p,
                "permutation_mean": (round(float(pf.mean()), 4)
                                     if len(pf) else None),
                "auc_in_longshot_band": {
                    "baseline": ls_auc0, "augmented": ls_auc1,
                    "gain": ls_auc1 - ls_auc0,
                },
            },
        }
        log.info("%-12s baseline ll=%.5f -> augmented ll=%.5f  gain=%+.5f  "
                 "perm p=%.3f  top3 moved %d/%d races",
                 base_name, m0["log_loss"], m1["log_loss"], gain, p_value,
                 changed, df["race_id"].nunique())

    # Which PP features does a full-sample fit lean on? Reported for direction
    # only — these coefficients are in-sample and are NOT evidence of value.
    w = fit_offset_logistic(X, y, logit(df["y_pred"].to_numpy(dtype=float)), L2)
    coefs = sorted(zip(names, w[1:]), key=lambda kv: -abs(kv[1]))
    report["top_coefficients_in_sample"] = [
        {"feature": n, "coef": round(float(c), 4)} for n, c in coefs[:20]]

    # Marginal, model-free view: correlation of each PP feature with the
    # baseline's residual. No fitting, so no overfitting to hide behind.
    resid = y - df["y_pred"].to_numpy(dtype=float)
    marg = []
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce")
        ok = v.notna().to_numpy()
        if ok.sum() < 200 or v[ok].std() < 1e-9:
            continue
        r = float(np.corrcoef(v[ok], resid[ok])[0, 1])
        marg.append({"feature": c, "n": int(ok.sum()),
                     "corr_with_residual": round(r, 4)})
    marg.sort(key=lambda d: -abs(d["corr_with_residual"]))
    report["residual_correlations"] = marg[:20]
    # Under the null, r ~ N(0, 1/sqrt(n)); with ~1500 rows that is ~0.026.
    report["residual_corr_noise_sd"] = round(float(1 / np.sqrt(len(df))), 4)

    keep = ["entry_id", "race_id", "track", "race_date", "race_num", "y_true",
            "finish_pos", "final_odds", "y_pred", "p_fund",
            "p_aug_blend", "p_aug_fundamental", "pp_ml_decimal",
            "pp_prime_power", "pp_best_speed"]
    df[keep].to_csv(OUT_CSV, index=False)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("wrote %s and %s", OUT_JSON.name, OUT_CSV.name)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    r = run()
    print(json.dumps(r, indent=2))
