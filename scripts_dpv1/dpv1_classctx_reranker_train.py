"""Phase 6D Gap #11 Path B: class-context as a reranker over DPv1.

    python scripts_dpv1/dpv1_classctx_reranker_train.py evaluate
    python scripts_dpv1/dpv1_classctx_reranker_train.py train

Writes ``dpv1_classctx_reranker.pkl``. **Never touches ``dpv1.pkl``,
``dpv1_pp_reranker.pkl`` or ``train_dpv1.py``.**

What this is, and how it differs from Path A
--------------------------------------------
Path A (shipped as evidence in `847944f`, config ``dpv1.5.2``) put the
class-context block **inside** the base model and retrained. This is the same
feature block fitted as a **second-stage correction on top of the current live
base**, ``dpv1.pkl`` / ``dpv1.2.0-4track``, in the architecture
``pp-reranker-1.0`` uses.

The comparison is the point. If the reranker recovers most of Path A's gain,
the class-context signal is architecture-independent and can ship without
retraining or restarting the live baseline window. If it does not, that is
evidence the gain needs the base model's own coefficients to be refitted
jointly, and Path A is the only route.

**One structural difference from the PP reranker, and it matters.** The PP
reranker exists because PP data joins to only 0.86% of the corpus, so a base
feature could never be resolved; it applies to a small, well-defined
subpopulation. Class-context features are present for **almost every row**
(``class_context_missing`` is 1 for 39.6%, but that is itself a modelled
state, not an absence of data). So this reranker is a correction applied to
the whole field, which is much closer to "refit the model" than the PP case
is. It is still a strictly weaker device than Path A, because the base model's
95 existing coefficients stay frozen at values fitted without the class block.
Expect it to recover part, not all, of Path A's gain; the question is how
much.

Honesty properties, carried over from the PP reranker
-----------------------------------------------------
* The base contribution is the base model's **out-of-sample** fold prediction
  (``dpv1_fold_predictions.csv``, written with ``dpv1.pkl`` on 2026-08-22),
  never a refit on rows it trained on.
* The reranker is cross-validated by **race group**, so scored rows are rows it
  did not see. Splitting by race and not by entry matters because top-pick ITM
  is a within-race ranking metric.
* A **leave-one-year-out** pass is reported alongside the 5-fold GroupKFold.
  GroupKFold shuffles races across time; LOYO does not, and it is the
  discipline Step 3's base-model comparison was held to. Where the two
  disagree, believe LOYO.

Offset versus free base coefficient
-----------------------------------
Both are fitted, exactly as in the PP reranker:

* ``offset`` — ``logit_adj = base_logit + w . class_features``. The base
  opinion is carried at unit weight; the block supplies a pure delta.
* ``free`` — ``base_logit`` is an ordinary feature with its own coefficient,
  so the model can also learn how much to trust the base for this population.

A free coefficient materially below 1 means the reranker is recalibrating
every horse rather than adjusting the ones the class block knows about — which
for a whole-field reranker is the failure mode to watch for.
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import DEFAULT_DB  # noqa: E402

MODEL_OUT = DPV1_DIR / "dpv1_classctx_reranker.pkl"
BASE_FOLDS = DPV1_DIR / "dpv1_fold_predictions.csv"
EVAL_OUT = DPV1_DIR / "dpv1_classctx_reranker_eval.json"

EPS = 1e-6

# The Step 3 shipped block (config dpv1.5.2). Kept byte-for-byte in step with
# new_features/class_context_features.FEATURES minus the trimmed _x_last_down.
NUMERIC_FEATURES = [
    "avg_class_recent",
    "class_drop_signed",
    "class_context_missing",
    "low_finish_variance",
    "lowvar_x_dropping",
    "lowvar_x_rising",
    "lowvar_same_x_mean_finish",
    "last_class_move_clipped",
    "class_drop_signed_x_last_up",
]
CATEGORICAL_FEATURES = {
    # column -> levels; the first is the dropped reference level
    "class_direction": ("SAME", "DROPPING", "RISING", "NO_HISTORY"),
    "last_class_direction_fine": ("SAME", "UP", "DOWN", "NO_LAST"),
}

log = logging.getLogger("classctx_reranker")


@dataclass
class ClassCtxReranker:
    """Second-stage logistic model over the base model's logit."""
    version: str
    trained_at: str
    mode: str                       # "free" or "offset"
    base_version: str
    feature_names: list[str]
    coef: np.ndarray
    intercept: float
    impute: dict = field(default_factory=dict)
    training_notes: dict = field(default_factory=dict)

    def adjust_logit(self, base_logit, X) -> np.ndarray:
        """Return the reranked logit. Base is carried, never discarded."""
        delta = np.asarray(X, dtype=float) @ self.coef + self.intercept
        if self.mode == "offset":
            return np.asarray(base_logit, dtype=float) + delta
        return delta      # "free" already carries base_logit inside X


def load_reranker(path: str | Path = MODEL_OUT) -> "ClassCtxReranker":
    """Unpickle the reranker, installing the ``__main__`` shim it needs.

    Same property as ``dpv1.pkl`` and ``dpv1_pp_reranker.pkl`` — the artifact
    is written by this file run as a script, so the class is pickled as
    ``__main__.ClassCtxReranker``.
    """
    import __main__
    if not hasattr(__main__, "ClassCtxReranker"):
        __main__.ClassCtxReranker = ClassCtxReranker
    with open(Path(path), "rb") as f:
        return pickle.load(f)


def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def load_dataset(db: str = str(DEFAULT_DB),
                 base_folds: Path = BASE_FOLDS) -> pd.DataFrame:
    """Base out-of-sample logits joined to the class-context block."""
    cols = ", ".join(f"f.{c}" for c in NUMERIC_FEATURES + list(CATEGORICAL_FEATURES))
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        feat = pd.read_sql_query(
            f"SELECT f.entry_id, {cols}, f.class_score_change_from_last, "
            f"r.race_type "
            f"FROM entry_features_dpv1 f "
            f"JOIN entries e ON e.id = f.entry_id "
            f"JOIN races r   ON r.id = e.race_id", conn)
    finally:
        conn.close()
    folds = pd.read_csv(base_folds, usecols=["entry_id", "race_id", "track",
                                             "race_date", "y_true", "finish_pos",
                                             "p_fund", "fold"])
    df = folds.merge(feat, on="entry_id", how="inner")
    df["base_logit"] = logit(df["p_fund"])
    df["year"] = pd.to_datetime(df["race_date"]).dt.year
    return df


def build_features(df: pd.DataFrame, mode: str,
                   impute: dict | None = None) -> tuple[pd.DataFrame, list[str], dict]:
    """Class-context block, one-hot for the two categoricals.

    Missingness: the numeric columns are NULL only where today's own
    ``class_score`` is NULL (28 rows of 222,362). Those are median-imputed from
    the training data and the medians are stored on the artifact, so scoring a
    live card cannot silently use a different fill.
    """
    out = pd.DataFrame(index=df.index)
    imp = dict(impute) if impute else {}
    for c in NUMERIC_FEATURES:
        s = pd.to_numeric(df[c], errors="coerce")
        if c not in imp:
            imp[c] = float(s.median()) if s.notna().any() else 0.0
        out[c] = s.fillna(imp[c]).astype(float)
    for c, levels in CATEGORICAL_FEATURES.items():
        v = df[c].astype("object")
        for lev in levels[1:]:          # levels[0] is the reference
            out[f"{c}__{lev}"] = (v == lev).astype(float)
    if mode == "free":
        out["base_logit"] = df["base_logit"].astype(float)
    return out, list(out.columns), imp


def fit_offset_logistic(X, y, offset, C: float = 1.0):
    """L2-penalised logistic fit with ``offset`` carried at unit weight.

    ``logit(p) = offset + X @ w + b``, maximising the penalised likelihood in
    ``w`` and ``b`` only. Lifted from ``dpv1_pp_reranker_train`` deliberately —
    including its warning: fitting ``X @ w`` alone and adding the offset at
    prediction time is NOT an offset model, it double-counts the signal.
    """
    from scipy.optimize import minimize
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    offset = np.asarray(offset, dtype=float)
    n, k = X.shape
    lam = 1.0 / (C * max(n, 1))

    def nll(theta):
        w, b = theta[:k], theta[k]
        z = offset + X @ w + b
        ll = np.sum(y * z - np.logaddexp(0.0, z))
        return -ll / n + lam * np.dot(w, w)

    def grad(theta):
        w, b = theta[:k], theta[k]
        z = offset + X @ w + b
        r = 1.0 / (1.0 + np.exp(-z)) - y
        g = np.empty(k + 1)
        g[:k] = X.T @ r / n + 2 * lam * w
        g[k] = r.sum() / n
        return g

    res = minimize(nll, np.zeros(k + 1), jac=grad, method="L-BFGS-B")
    return res.x[:k], float(res.x[k])


def _fit_predict(Xtr, ytr, btr, Xva, bva, mode: str, C: float) -> np.ndarray:
    from sklearn.linear_model import LogisticRegression
    if mode == "offset":
        w, b = fit_offset_logistic(Xtr, ytr, btr, C)
        return bva + np.asarray(Xva, dtype=float) @ w + b
    mdl = LogisticRegression(C=C, max_iter=3000)
    mdl.fit(Xtr, ytr)
    return np.asarray(Xva, dtype=float) @ mdl.coef_.ravel() + mdl.intercept_[0]


def cross_val_predict(df: pd.DataFrame, mode: str, C: float,
                      n_splits: int = 5, scheme: str = "race"):
    """Out-of-fold reranked logits.

    ``scheme='race'`` is GroupKFold by race, matching the PP reranker.
    ``scheme='year'`` is leave-one-year-out, which does not shuffle races
    across time and is the more conservative read.
    """
    from sklearn.model_selection import GroupKFold
    X, names, _ = build_features(df, mode)
    y = df["y_true"].to_numpy()
    base = df["base_logit"].to_numpy()
    out = np.zeros(len(df), dtype=float)

    if scheme == "year":
        for yr in sorted(df["year"].unique()):
            va = (df["year"] == yr).to_numpy()
            tr = ~va
            out[va] = _fit_predict(X[tr], y[tr], base[tr], X[va], base[va], mode, C)
        return out, names

    groups = df["race_id"].to_numpy()
    for tr, va in GroupKFold(n_splits=n_splits).split(X, y, groups):
        out[va] = _fit_predict(X.iloc[tr], y[tr], base[tr],
                               X.iloc[va], base[va], mode, C)
    return out, names


def top_pick_itm(df: pd.DataFrame, score_col: str) -> tuple[int, int, dict]:
    d = df.sort_values(["race_id", score_col], ascending=[True, False])
    top = d.groupby("race_id").head(1)
    return (int(top["y_true"].sum()), int(len(top)),
            dict(zip(top["race_id"], top["y_true"].astype(bool))))


def mcnemar(a: dict, b: dict) -> tuple[int, int, float]:
    from math import comb
    ids = sorted(set(a) & set(b))
    b01 = sum(1 for r in ids if not a[r] and b[r])
    b10 = sum(1 for r in ids if a[r] and not b[r])
    n = b01 + b10
    if n == 0:
        return b01, b10, 1.0
    k = min(b01, b10)
    return b01, b10, min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def _logloss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _paired_ll(df, y, p_base, p_new, label):
    """Race-clustered z on the log-loss difference, as in the Path A compare."""
    import math
    lb, ln = _logloss(y, p_base), _logloss(y, p_new)
    diff = pd.Series(ln - lb).groupby(df["race_id"].to_numpy()).sum()
    se = math.sqrt((diff ** 2).sum()) / len(df)
    d = ln.mean() - lb.mean()
    return dict(label=label, n=int(len(df)), ll_base=float(lb.mean()),
                ll_new=float(ln.mean()), delta=float(d),
                z=float(d / se) if se else float("nan"),
                resid_base=float(100 * (y - p_base).mean()),
                resid_new=float(100 * (y - p_new).mean()))


def cmd_evaluate(args) -> int:
    df = load_dataset(args.db)
    print(f" rows {len(df)}, races {df.race_id.nunique()}, "
          f"{df.race_date.min()} .. {df.race_date.max()}")
    print(f" base: dpv1.pkl out-of-fold predictions (dpv1.2.0-4track)")
    y = df["y_true"].to_numpy()
    df["p_base"] = df["p_fund"]
    base_hits, n_races, base_map = top_pick_itm(df, "p_base")
    print(f"\n base top-pick ITM {100*base_hits/n_races:.3f}%  ({base_hits}/{n_races})")

    results = {}
    for scheme in ("race", "year"):
        for mode in ("offset", "free"):
            z, names = cross_val_predict(df, mode, args.C, args.folds, scheme)
            col = f"p_{scheme}_{mode}"
            df[col] = 1.0 / (1.0 + np.exp(-z))
            hits, _, hit_map = top_pick_itm(df, col)
            g, l, p = mcnemar(base_map, hit_map)
            ll = _paired_ll(df, y, df["p_base"].to_numpy(), df[col].to_numpy(), "ALL")
            results[f"{scheme}/{mode}"] = dict(
                itm=100 * hits / n_races, delta=100 * (hits - base_hits) / n_races,
                gain=g, loss=l, p=p, logloss_delta=ll["delta"], z=ll["z"])
            print(f"\n --- CV by {scheme}, mode={mode} ---")
            print(f"   top-pick ITM {100*hits/n_races:.3f}%  "
                  f"delta {100*(hits-base_hits)/n_races:+.3f}pp  "
                  f"({g} vs {l}, McNemar p={p:.4f})")
            print(f"   log-loss {ll['ll_base']:.5f} -> {ll['ll_new']:.5f}  "
                  f"delta {ll['delta']:+.5f} (z {ll['z']:+.2f})")

    # the headline pair, mirroring how Path A was reported
    best = "year/free" if args.headline == "year" else "race/free"
    col = f"p_{best.split('/')[0]}_{best.split('/')[1]}"
    print(f"\n=== CLASS-DIRECTION RESIDUALS ({best}) ===")
    has = df[df.class_context_missing == 0]
    for name, m in (("BELOW (< -1)", has.class_drop_signed < -1),
                    ("LEVEL", has.class_drop_signed.abs() <= 1),
                    ("ABOVE (> +1)", has.class_drop_signed > 1)):
        d = has[m]
        print(f"   {name:<14} n {len(d):6d}   base {100*(d.y_true-d.p_base).mean():+5.2f}pp"
              f"   reranked {100*(d.y_true-d[col]).mean():+5.2f}pp")
    print(f"\n=== DEADBAND GRADIENT ({best}) ===")
    d2 = df[df.class_score_change_from_last.abs() < 3].copy()
    d2["L"] = d2.class_score_change_from_last.round().astype(int)
    for L, g in d2.groupby("L"):
        print(f"   move {L:+d}  n {len(g):6d}   base {100*(g.y_true-g.p_base).mean():+6.2f}pp"
              f"   reranked {100*(g.y_true-g[col]).mean():+6.2f}pp")

    if args.json:
        EVAL_OUT.write_text(json.dumps(results, indent=2))
        print(f"\n wrote {EVAL_OUT.name}")
    return 0


def cmd_train(args) -> int:
    df = load_dataset(args.db)
    X, names, imp = build_features(df, args.mode)
    y = df["y_true"].to_numpy()
    base = df["base_logit"].to_numpy()
    if args.mode == "offset":
        w, b = fit_offset_logistic(X, y, base, args.C)
    else:
        from sklearn.linear_model import LogisticRegression
        mdl = LogisticRegression(C=args.C, max_iter=3000).fit(X, y)
        w, b = mdl.coef_.ravel(), float(mdl.intercept_[0])
    art = ClassCtxReranker(
        version=args.version, trained_at=datetime.now(timezone.utc).isoformat(),
        mode=args.mode, base_version="dpv1.2.0-4track", feature_names=names,
        coef=np.asarray(w, dtype=float), intercept=b, impute=imp,
        training_notes=dict(rows=int(len(df)), races=int(df.race_id.nunique()),
                            C=args.C, base_folds=BASE_FOLDS.name))
    with open(MODEL_OUT, "wb") as f:
        pickle.dump(art, f)
    print(f" wrote {MODEL_OUT.name}  ({args.mode}, {len(names)} features)")
    for n_, c_ in sorted(zip(names, w), key=lambda t: -abs(t[1])):
        print(f"   {n_:<38} {c_:+.4f}")
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("evaluate")
    pe.add_argument("--db", default=str(DEFAULT_DB))
    pe.add_argument("--C", type=float, default=1.0)
    pe.add_argument("--folds", type=int, default=5)
    pe.add_argument("--headline", default="year", choices=("year", "race"))
    pe.add_argument("--json", action="store_true")
    pe.set_defaults(func=cmd_evaluate)
    pt = sub.add_parser("train")
    pt.add_argument("--db", default=str(DEFAULT_DB))
    pt.add_argument("--C", type=float, default=1.0)
    pt.add_argument("--mode", default="free", choices=("free", "offset"))
    pt.add_argument("--version", default="classctx-reranker-0.1")
    pt.set_defaults(func=cmd_train)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
