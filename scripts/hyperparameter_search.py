"""Grid-search framework for hyperparameter tuning.

Model-agnostic: you supply a ``fit_predict`` callable and a grid; the
framework handles the CV loop, aggregates metrics, and reports the best
configuration per metric.

``fit_predict`` contract
------------------------
    def fit_predict(train_df, val_df, params) -> pd.DataFrame:
        '''Return a predictions DataFrame with entry_id, race_id, y_pred
        aligned to val_df.
        '''

Both DataFrames are slices of your feature table. ``params`` is a plain
dict picked from the grid. The framework doesn't care what you do with
``params`` — it can drive model regularisation, shrinkage k, decay
half-life, whatever.

Example
-------
    from cross_validation import RollingOriginSplitter
    from hyperparameter_search import GridSearch

    def fit_predict(train, val, params):
        model = ConditionalLogit(l2=params["l2"])
        model.fit(train)
        return model.predict(val)

    grid = {"l2": [0.001, 0.01, 0.1, 1.0]}
    gs = GridSearch(
        fit_predict=fit_predict,
        param_grid=grid,
        splitter=RollingOriginSplitter.default_gp_folds(),
        scoring="log_loss_per_race",
        minimize=True,
    )
    report = gs.run(feature_df, y_true=..., final_odds=...)
    print(report.best_params)
    print(report.summary)
"""
from __future__ import annotations

import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from cross_validation import RollingOriginSplitter
from metrics import evaluate


log = logging.getLogger("hyperparameter_search")


FitPredict = Callable[[pd.DataFrame, pd.DataFrame, dict], pd.DataFrame]


@dataclass
class SearchReport:
    """Structured result of a grid search run."""

    param_grid: dict[str, list]
    scoring: str
    minimize: bool
    per_fold: pd.DataFrame           # one row per (fold, param combination)
    summary: pd.DataFrame            # one row per param combination, all metrics avged
    best_params: dict                # winner by ``scoring``
    best_score: float
    elapsed_seconds: float

    def top_k(self, k: int = 5) -> pd.DataFrame:
        col = f"{self.scoring}_mean"
        return self.summary.sort_values(col, ascending=self.minimize).head(k)


class GridSearch:
    """A tiny, model-agnostic grid search over temporal CV folds.

    The framework calls ``fit_predict(train, val, params)`` for every
    (fold, params) combination and aggregates the resulting metrics.

    Parameters
    ----------
    fit_predict
        User-supplied callable. Must return a predictions DataFrame with
        columns ``entry_id, race_id, y_pred`` aligned to the val fold.
    param_grid
        ``{"param_name": [values...]}``. All combinations are tried.
    splitter
        Any object with ``.split(df) -> yield (name, train_idx, val_idx)``.
    scoring
        Metric name (as returned by ``metrics.evaluate``) to pick the winner.
    minimize
        True for loss-type metrics (log-loss, brier); False for hit rates / ROI.
    metrics_to_track
        Optional subset of metrics to aggregate — if None, tracks all.
    date_col
        Column used by the splitter to compute fold membership.
    """

    def __init__(
        self,
        fit_predict: FitPredict,
        param_grid: dict[str, list],
        splitter: RollingOriginSplitter,
        scoring: str = "log_loss_per_race",
        minimize: bool = True,
        metrics_to_track: Iterable[str] | None = None,
        date_col: str = "race_date",
    ):
        if not param_grid:
            raise ValueError("param_grid cannot be empty")
        self.fit_predict = fit_predict
        self.param_grid = param_grid
        self.splitter = splitter
        self.scoring = scoring
        self.minimize = minimize
        self.metrics_to_track = (
            None if metrics_to_track is None else list(metrics_to_track)
        )
        self.date_col = date_col

    def _param_combinations(self) -> list[dict]:
        keys = list(self.param_grid.keys())
        combos = []
        for values in itertools.product(*(self.param_grid[k] for k in keys)):
            combos.append(dict(zip(keys, values)))
        return combos

    def _params_signature(self, params: dict) -> str:
        return "|".join(f"{k}={params[k]}" for k in sorted(params))

    def run(
        self,
        features_df: pd.DataFrame,
        include_kelly: bool = False,
        verbose: bool = True,
    ) -> SearchReport:
        """Execute the grid search.

        ``features_df`` must contain the ``date_col``, ``entry_id``,
        ``race_id``, ``y_true``, ``final_odds``, and whatever raw columns
        your ``fit_predict`` needs.
        """
        combos = self._param_combinations()
        folds = list(self.splitter.split(features_df, date_col=self.date_col))
        if verbose:
            log.info("Running %d param combos × %d folds = %d fits",
                     len(combos), len(folds), len(combos) * len(folds))

        rows = []
        start = time.perf_counter()
        for combo_i, params in enumerate(combos, 1):
            sig = self._params_signature(params)
            for fold_name, tr_idx, vl_idx in folds:
                train_df = features_df.iloc[tr_idx]
                val_df = features_df.iloc[vl_idx]
                if len(train_df) == 0 or len(val_df) == 0:
                    log.warning("skip %s / %s: empty fold", sig, fold_name)
                    continue
                t0 = time.perf_counter()
                preds = self.fit_predict(train_df, val_df, params)
                fit_secs = time.perf_counter() - t0

                # Attach y_true + final_odds for scoring
                scoring_df = preds[["entry_id", "race_id", "y_pred"]].merge(
                    val_df[["entry_id", "y_true", "final_odds"]],
                    on="entry_id", how="left",
                )
                metrics = evaluate(scoring_df, include_kelly=include_kelly)
                if self.metrics_to_track is not None:
                    metrics = {k: v for k, v in metrics.items()
                               if k in self.metrics_to_track}

                row = {"fold": fold_name, **params, **metrics,
                       "fit_seconds": fit_secs, "n_val": len(val_df)}
                rows.append(row)
            if verbose:
                elapsed = time.perf_counter() - start
                log.info("  combo %d/%d done — %s (%.1fs elapsed)",
                         combo_i, len(combos), sig, elapsed)

        elapsed = time.perf_counter() - start

        per_fold = pd.DataFrame(rows)
        # Aggregate: mean + std across folds, per param combination.
        param_cols = list(self.param_grid.keys())
        metric_cols = [c for c in per_fold.columns
                       if c not in ({"fold", "fit_seconds", "n_val"} | set(param_cols))]
        summary = (per_fold.groupby(param_cols, dropna=False)[metric_cols]
                   .agg(["mean", "std"]))
        summary.columns = ["_".join(c) for c in summary.columns]
        summary = summary.reset_index()

        sort_col = f"{self.scoring}_mean"
        if sort_col not in summary.columns:
            raise ValueError(
                f"scoring metric {self.scoring!r} not among tracked metrics"
            )
        best = summary.sort_values(sort_col, ascending=self.minimize).iloc[0]
        best_params = {k: best[k] for k in param_cols}
        best_score = float(best[sort_col])

        return SearchReport(
            param_grid=self.param_grid,
            scoring=self.scoring,
            minimize=self.minimize,
            per_fold=per_fold,
            summary=summary,
            best_params=best_params,
            best_score=best_score,
            elapsed_seconds=elapsed,
        )


# ---------------------------------------------------------------------------
# Self-test with a dummy scoring function
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Demonstrate the grid search with a dummy fit_predict.

    We build a mini synthetic dataset spanning 2019-2026, register a
    fit_predict that returns predictions equal to ``final_odds * scale``
    (so `scale` is the hyperparameter), and confirm the framework picks
    the best value.
    """
    import numpy as np
    rng = np.random.default_rng(0)
    dates = pd.date_range("2019-01-01", "2026-06-30", freq="D")
    rows = []
    for i, d in enumerate(dates):
        # 3 races per day, 6 horses each
        for r in range(3):
            odds = rng.uniform(1, 20, size=6)
            winner = np.argmin(odds)  # favorite wins 100% of synthetic races
            for h in range(6):
                rows.append({
                    "entry_id": len(rows),
                    "race_id": i * 3 + r,
                    "race_date": d,
                    "final_odds": odds[h],
                    "y_true": int(h == winner),
                })
    df = pd.DataFrame(rows)

    def fit_predict(train, val, params):
        # Ignore train (dummy). Emit market implied prob raised to a power.
        scale = params["scale"]
        odds = val["final_odds"].to_numpy(dtype=float)
        p = (1.0 / (odds + 1.0)) ** scale
        return pd.DataFrame({
            "entry_id": val["entry_id"].to_numpy(),
            "race_id": val["race_id"].to_numpy(),
            "y_pred": p,
        })

    gs = GridSearch(
        fit_predict=fit_predict,
        param_grid={"scale": [0.5, 1.0, 2.0, 5.0]},
        splitter=RollingOriginSplitter.default_gp_folds(),
        scoring="log_loss_per_race",
        minimize=True,
    )
    report = gs.run(df, verbose=False)
    print(f"Best params: {report.best_params}, score: {report.best_score:.4f}")
    print(f"Elapsed: {report.elapsed_seconds:.2f}s")
    print("\nTop 3:")
    print(report.top_k(3).to_string(index=False))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    _self_test()
