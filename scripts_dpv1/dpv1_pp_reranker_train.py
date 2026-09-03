"""Phase 6D Gap #1: train the PP reranker, a supplementary model over DPv1.

    python scripts_dpv1/dpv1_pp_reranker_train.py train
    python scripts_dpv1/dpv1_pp_reranker_train.py evaluate

Writes ``dpv1_pp_reranker.pkl``. **Never touches ``dpv1.pkl`` or
``train_dpv1.py``** — the base model keeps its role, its evaluation
infrastructure and its live baseline untouched.

What this is
------------
DPv1's history features are keyed on ``horse_id`` against a four-track corpus,
so a horse shipping in from Laurel or Parx arrives with an empty history block
and gets ranked on a near-prior. The Brisnet PP file has that horse's real
record, and ``pp_entries_raw`` now holds it.

Wiring PP into the *base* model was rejected: joinable coverage is 0.86% of the
corpus, so a PP-backed feature would fire on fewer than one training row in a
hundred and a fold-level comparison could never resolve it. Instead this trains
a small second-stage model on exactly the rows where PP exists, and applies it
only to horses that have PP data — which, on a live card handed a PP file, is
all of them.

Two properties make the small sample honest rather than fatal:

* The base model's contribution is its **out-of-sample** fold prediction
  (``dpv1_fold_predictions.csv``), not a refit on rows it trained on. Using the
  shipped model's in-sample logit would let the reranker learn to correct
  memorisation rather than genuine error.
* The reranker is itself cross-validated by **race group**, so the rows it is
  scored on are rows it did not see. Splitting by race rather than by entry
  matters because top-pick ITM is a within-race ranking metric: leaking one
  horse from a race into training tells you about its rivals.

Offset versus free base coefficient
-----------------------------------
Two formulations, both fitted and compared:

* ``offset`` — ``logit_adj = base_logit + w . pp_features``. The base opinion is
  carried at unit weight and PP supplies a pure delta. Degrades exactly to the
  base model when the PP block is neutral.
* ``free`` — ``base_logit`` enters as an ordinary feature with its own
  coefficient, so the model can also learn *how much to trust* the base opinion
  for this population.

``free`` is the more expressive and is the default; ``offset`` is the safer and
is reported alongside, because a coefficient on the base logit materially below
1 would mean the reranker is recalibrating every horse rather than adjusting
the ones PP knows something about.
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

MODEL_OUT = DPV1_DIR / "dpv1_pp_reranker.pkl"
BASE_FOLDS = DPV1_DIR / "dpv1_fold_predictions.csv"
EVAL_OUT = DPV1_DIR / "dpv1_pp_reranker_eval.json"

RUNNING_STYLES = ("e", "ep", "p", "s", "na")
EPS = 1e-6

log = logging.getLogger("pp_reranker")


@dataclass
class PPReranker:
    """Second-stage logistic model over the base model's logit."""
    version: str
    trained_at: str
    mode: str                       # "free" or "offset"
    feature_names: list[str]
    coef: np.ndarray
    intercept: float
    training_notes: dict = field(default_factory=dict)

    def adjust_logit(self, base_logit, X) -> np.ndarray:
        """Return the reranked logit. Base is carried, never discarded."""
        delta = np.asarray(X, dtype=float) @ self.coef + self.intercept
        if self.mode == "offset":
            return np.asarray(base_logit, dtype=float) + delta
        return delta      # "free" already carries base_logit inside X


def load_reranker(path: str | Path = MODEL_OUT) -> "PPReranker":
    """Unpickle the reranker, installing the ``__main__`` shim it needs.

    The artifact is written by this file run as a script, so ``PPReranker`` is
    pickled as ``__main__.PPReranker`` and unpickling from anywhere else raises
    AttributeError. Same property as ``dpv1.pkl`` -- see ``dpv1_runtime.load_model``.
    Whatever wires this into the runner should import *this* function rather
    than calling ``pickle.load`` directly.
    """
    import __main__
    if not hasattr(__main__, "PPReranker"):
        __main__.PPReranker = PPReranker
    with open(Path(path), "rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def load_dataset(db: str = str(DEFAULT_DB),
                 base_folds: Path = BASE_FOLDS) -> pd.DataFrame:
    """Rows where PP data, a corpus entry and an out-of-sample base logit meet."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query("""
            SELECT e.id AS entry_id, t.code AS track, rd.race_date, r.race_num,
                   e.program_num, e.finish_pos, e.finish_status,
                   f.career_starts        AS corpus_starts,
                   p.pp_career_starts, p.pp_days_off, p.pp_races_in_60d,
                   p.pp_running_style, p.pp_best_speed, p.pp_avg_speed_last3
            FROM entries e
            JOIN races r      ON r.id  = e.race_id
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id  = rd.track_id
            JOIN pp_entries_raw p
                   ON p.track = t.code AND p.race_date = rd.race_date
                  AND p.race_num = r.race_num
                  AND UPPER(TRIM(p.program_num)) = UPPER(TRIM(e.program_num))
            LEFT JOIN entry_features_dpv1 f ON f.entry_id = e.id
        """, conn)
    finally:
        conn.close()

    folds = pd.read_csv(base_folds,
                        usecols=["entry_id", "race_id", "y_true", "p_fund", "fold"])
    df = df.merge(folds, on="entry_id", how="inner")
    df["base_logit"] = logit(df["p_fund"])
    return df


def build_features(df: pd.DataFrame, mode: str,
                   style_spec: str = "explicit-na",
                   impute: dict | None = None) -> tuple[pd.DataFrame, list[str]]:
    """PP feature block. Live cards have full PP coverage, so the only
    missingness handled here is *within* the PP file itself."""
    corpus = pd.to_numeric(df["corpus_starts"], errors="coerce").fillna(0.0)
    pp = pd.to_numeric(df["pp_career_starts"], errors="coerce").fillna(0.0)

    X = pd.DataFrame(index=df.index)
    # The headline signal: starts PP knows about that the corpus does not.
    X["career_starts_delta"] = pp - corpus
    X["is_shipper"] = ((corpus == 0) & (pp > 0)).astype(float)
    X["is_first_timer"] = ((corpus == 0) & (pp == 0)).astype(float)
    X["pp_career_starts"] = pp
    X["pp_days_off"] = pd.to_numeric(df["pp_days_off"], errors="coerce").fillna(0.0)
    X["pp_races_in_60d"] = pd.to_numeric(df["pp_races_in_60d"],
                                         errors="coerce").fillna(0.0)

    # pp_best_speed is the one genuinely sparse input, and it is missing
    # precisely for lightly raced horses -- so the indicator is signal, not
    # bookkeeping. Kept explicit rather than imputed silently.
    spd = pd.to_numeric(df["pp_best_speed"], errors="coerce")
    X["pp_best_speed__missing"] = spd.isna().astype(float)
    fill = spd.median() if impute is None else impute.get("pp_best_speed", spd.median())
    X["pp_best_speed"] = spd.fillna(fill).astype(float)

    style = df["pp_running_style"].fillna("na").astype(str).str.lower()
    if style_spec == "reference-na":
        # Original encoding: "na" is the omitted reference level, so every
        # style coefficient is measured against "no style could be determined".
        for s in RUNNING_STYLES[:-1]:
            X[f"running_style__{s}"] = (style == s).astype(float)
    elif style_spec == "explicit-na":
        # "na" almost always means "too little history to classify", which is a
        # fact about data availability rather than about running style. Give it
        # its own indicator and contrast the real styles against "e", so the
        # availability signal cannot hide inside the style contrasts.
        X["running_style_unknown"] = (style == "na").astype(float)
        for s in ("ep", "p", "s"):
            X[f"running_style__{s}"] = (style == s).astype(float)
    elif style_spec != "drop":
        raise ValueError(f"unknown style_spec {style_spec!r}")

    if mode == "free":
        X.insert(0, "base_logit", df["base_logit"].to_numpy())
    return X, list(X.columns)


# ---------------------------------------------------------------------------
# Fit / evaluate
# ---------------------------------------------------------------------------

def fit_offset_logistic(X, y, offset, C: float = 1.0):
    """L2-penalised logistic fit with ``offset`` carried at unit weight.

    ``logit(p) = offset + X @ w + b``, maximising the penalised likelihood in
    ``w`` and ``b`` only. sklearn has no offset term and statsmodels is not
    installed here, so this is a direct L-BFGS fit.

    This matters, and an earlier version got it wrong: fitting ``X @ w``
    against ``y`` on its own and then *adding* ``offset`` at prediction time is
    not an offset model. It is an equal-weight ensemble of two full predictors,
    it double-counts the signal, and it shows up as a large negative intercept
    compensating for the doubled scale.
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
        # log(1+exp(z)) computed stably
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


def cross_val_predict(df: pd.DataFrame, mode: str, C: float, n_splits: int = 5,
                      style_spec: str = "explicit-na"):
    """Out-of-fold reranked logits, grouped by race.

    Grouping by race is not optional: top-pick ITM is a within-race ranking
    metric, so leaking one horse of a race into training leaks information
    about its rivals' relative standing.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    X, names = build_features(df, mode, style_spec)
    y = df["y_true"].to_numpy()
    base = df["base_logit"].to_numpy()
    groups = df["race_id"].to_numpy()

    out = np.zeros(len(df), dtype=float)
    gkf = GroupKFold(n_splits=n_splits)
    for tr, va in gkf.split(X, y, groups):
        if mode == "offset":
            # True offset fit: base_logit is carried at unit weight during
            # fitting, so w explains only what the base opinion does not.
            w, b = fit_offset_logistic(X.iloc[tr], y[tr], base[tr], C)
            out[va] = base[va] + X.iloc[va].to_numpy() @ w + b
        else:
            mdl = LogisticRegression(C=C, max_iter=2000)
            mdl.fit(X.iloc[tr], y[tr])
            out[va] = (X.iloc[va].to_numpy() @ mdl.coef_.ravel()
                       + mdl.intercept_[0])
    return out, names


def top_pick_itm(df: pd.DataFrame, score_col: str) -> tuple[int, int, dict]:
    """Top-pick ITM by race, plus the per-race hit map for a paired test."""
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


# ---------------------------------------------------------------------------

def cmd_train(args) -> int:
    df = load_dataset(args.db, Path(args.base_folds))
    log.info("dataset: %d rows, %d races, ITM base rate %.4f",
             len(df), df["race_id"].nunique(), df["y_true"].mean())

    X, names = build_features(df, args.mode, args.style_spec)
    y = df["y_true"].to_numpy()
    if args.mode == "offset":
        coef, intercept = fit_offset_logistic(
            X, y, df["base_logit"].to_numpy(), args.C)
    else:
        from sklearn.linear_model import LogisticRegression
        mdl = LogisticRegression(C=args.C, max_iter=2000).fit(X, y)
        coef, intercept = mdl.coef_.ravel().copy(), float(mdl.intercept_[0])

    model = PPReranker(
        version=args.version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        mode=args.mode,
        feature_names=names,
        coef=coef,
        intercept=intercept,
        training_notes={
            "n_rows": int(len(df)), "n_races": int(df["race_id"].nunique()),
            "itm_rate": float(y.mean()), "C": args.C,
            "base_model_source": Path(args.base_folds).name,
            "base_logit_is_out_of_sample": True,
            "tracks": sorted(df["track"].unique().tolist()),
            "date_range": [df["race_date"].min(), df["race_date"].max()],
            "style_spec": args.style_spec,
            # Inference has no training set to take a median from, so the
            # constant travels with the artifact. Without this a live card
            # would impute against its own field and silently use a different
            # scale from the one the coefficients were fitted on.
            "impute": {"pp_best_speed": float(
                pd.to_numeric(df["pp_best_speed"], errors="coerce").median())},
        },
    )
    with open(args.out, "wb") as f:
        pickle.dump(model, f)
    log.info("wrote %s (mode=%s, %d features)", args.out, args.mode, len(names))

    print(f"\n{'feature':<28}{'coef':>10}")
    for n, cf in sorted(zip(names, model.coef), key=lambda kv: -abs(kv[1])):
        print(f"  {n:<26}{cf:>+10.4f}")
    print(f"  {'(intercept)':<26}{model.intercept:>+10.4f}")
    return 0


def cmd_evaluate(args) -> int:
    df = load_dataset(args.db, Path(args.base_folds))
    n_races = df["race_id"].nunique()
    print("=" * 74)
    print(" PP RERANKER -- standalone cross-validated evaluation")
    print("=" * 74)
    print(f" rows {len(df):,}   races {n_races:,}   "
          f"ITM base rate {df['y_true'].mean():.4f}")
    print(f" tracks {sorted(df['track'].unique())}   "
          f"{df['race_date'].min()} .. {df['race_date'].max()}")
    print(f" base logit source: {Path(args.base_folds).name} (OUT-OF-SAMPLE)")
    print(f" reranker CV: GroupKFold by race, {args.folds} folds")

    b_n, b_d, b_map = top_pick_itm(df, "base_logit")
    print(f"\n{'model':<26}{'top-pick ITM':>16}{'delta':>10}{'p (McNemar)':>14}")
    print(f"  {'base (DPv1 alone)':<24}{b_n:>7}/{b_d:<5} "
          f"{100*b_n/b_d:5.1f}%{'':>10}{'--':>14}")

    results = {"n_rows": int(len(df)), "n_races": int(n_races),
               "base": {"itm_n": b_n, "itm_d": b_d, "itm": b_n / b_d},
               "variants": {}}
    for mode in ("free", "offset"):
        adj, names = cross_val_predict(df, mode, args.C, args.folds)
        col = f"_adj_{mode}"
        df[col] = adj
        n, d, m = top_pick_itm(df, col)
        b01, b10, p = mcnemar(b_map, m)
        delta = 100 * (n / d - b_n / b_d)
        sig = "" if p >= 0.05 else "  <-- significant"
        print(f"  {'reranked (' + mode + ')':<24}{n:>7}/{d:<5} "
              f"{100*n/d:5.1f}%{delta:>+9.1f}pp{p:>14.3f}{sig}")
        results["variants"][mode] = {
            "itm_n": n, "itm_d": d, "itm": n / d, "delta_pp": delta,
            "mcnemar_b01": b01, "mcnemar_b10": b10, "p": p}

    print(f"\n  discordant races (free):   "
          f"{results['variants']['free']['mcnemar_b01']} gained / "
          f"{results['variants']['free']['mcnemar_b10']} lost")
    print(f"  discordant races (offset): "
          f"{results['variants']['offset']['mcnemar_b01']} gained / "
          f"{results['variants']['offset']['mcnemar_b10']} lost")

    # How much does the reranker actually move things, and for whom?
    X, _ = build_features(df, "offset")
    shipper = X["is_shipper"].to_numpy().astype(bool)
    first = X["is_first_timer"].to_numpy().astype(bool)
    for mode in ("free", "offset"):
        shift = df[f"_adj_{mode}"].to_numpy() - df["base_logit"].to_numpy()
        print(f"\n  logit shift ({mode}): overall mean |shift| {np.abs(shift).mean():.3f}"
              f"   shippers {np.abs(shift[shipper]).mean():.3f}"
              f"   first-timers {np.abs(shift[first]).mean():.3f}"
              f"   others {np.abs(shift[~shipper & ~first]).mean():.3f}")

    Path(args.eval_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.eval_out}")
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("train", "evaluate"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(DEFAULT_DB))
        s.add_argument("--C", type=float, default=1.0)
        s.add_argument("--mode", default="offset", choices=("free", "offset"))
        s.add_argument("--version", default="pp-reranker-1.0",
                       help="version string carried on the artifact")
        s.add_argument("--folds", type=int, default=5)
        s.add_argument("--style-spec", default="explicit-na",
                       choices=("reference-na", "explicit-na", "drop"))
        s.add_argument("--out", default=str(MODEL_OUT))
        s.add_argument("--eval-out", default=str(EVAL_OUT))
        s.add_argument("--base-folds", default=str(BASE_FOLDS),
                       help="fold-prediction file supplying the OUT-OF-SAMPLE "
                            "base logit")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return (cmd_train if args.cmd == "train" else cmd_evaluate)(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
