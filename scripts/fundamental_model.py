"""Conditional-logit fundamental model.

Objective (weighted, L2-regularised):

    L(w) = sum_r w_r * (-log P(winner_r | race_r; w)) + lambda * ||w||^2

where the per-race choice probability is a softmax over horses:

    P(i | race_r; w) = exp(x_i . w) / sum_j in race_r exp(x_j . w).

Minimised with scipy L-BFGS-B using an analytical gradient. This is what
Benter used in his 1994 paper and remains the workhorse for horse-race
handicapping.

Notes
-----
* No intercept term — a global bias vanishes in per-race softmax anyway.
* Missing feature values must be dealt with upstream (see
  ``prepare_training.Preprocessor``); this fitter assumes a dense design
  matrix.
* Per-entry sample weights come from ``time_decay_weights``. Every horse in
  a given race receives the same weight (they share a race_date).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp


log = logging.getLogger("fundamental_model")


@dataclass
class FundamentalModel:
    """Conditional-logit fitter, sklearn-ish interface."""

    l2: float = 0.01
    max_iter: int = 200
    tol: float = 1e-6
    verbose: bool = False

    # Fitted state
    coef_: np.ndarray = field(default_factory=lambda: np.empty(0))
    feature_names_: list[str] = field(default_factory=list)
    n_iter_: int = 0
    final_loss_: float = float("nan")
    fit_seconds_: float = float("nan")

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        race_ids: np.ndarray,
        sample_weight: np.ndarray | None = None,
        feature_names: list[str] | None = None,
    ) -> "FundamentalModel":
        """Fit the model.

        Parameters
        ----------
        X
            ``(n_entries, n_features)`` dense design matrix, standardised.
        y
            Winner indicator (0/1) per entry.
        race_ids
            Race-membership integer per entry. Contiguity within race is not
            required — we build a race->entries index internally.
        sample_weight
            Per-entry weight (typically time-decay). ``None`` means uniform.
        feature_names
            Column names for interpretability. Kept as-is on the model.
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        race_ids = np.asarray(race_ids)
        n, d = X.shape
        if sample_weight is None:
            sample_weight = np.ones(n, dtype=np.float64)
        sample_weight = np.asarray(sample_weight, dtype=np.float64)

        # Precompute per-race winner mask and "contributing race" mask.
        # A race contributes only if it has exactly one marked winner.
        y_series = pd.Series(y)
        race_id_series = pd.Series(race_ids)
        wins_per_race = y_series.groupby(race_id_series).transform("sum").to_numpy()
        contributes = (wins_per_race == 1.0)
        if not contributes.any():
            raise ValueError("no races with a marked winner — nothing to fit")
        # Zero out sample weights for entries in non-contributing races so
        # they exert no force on the gradient.
        effective_weight = np.where(contributes, sample_weight, 0.0)

        def loss_and_grad(w: np.ndarray) -> tuple[float, np.ndarray]:
            s = X @ w  # (n,)
            # Per-race stable softmax via pandas grouping (vectorized).
            s_series = pd.Series(s)
            max_per_race = s_series.groupby(race_id_series).transform("max").to_numpy()
            exp_shift = np.exp(s - max_per_race)
            sum_per_race = (pd.Series(exp_shift)
                            .groupby(race_id_series)
                            .transform("sum").to_numpy())
            sum_per_race = np.where(sum_per_race > 0, sum_per_race, 1.0)
            p = exp_shift / sum_per_race
            log_sum_per_race = max_per_race + np.log(sum_per_race)

            # Loss = sum_r w_r * (log_sum_exp_r - s_winner_r).
            # We track this per-entry using y==1 mask to pick out winners.
            winner_mask = (y == 1) & contributes
            per_winner_loss = log_sum_per_race[winner_mask] - s[winner_mask]
            total_loss = float(np.sum(effective_weight[winner_mask] * per_winner_loss))

            # Gradient = X.T @ (effective_weight * (p - y))
            residual = effective_weight * (p - y)
            grad = X.T @ residual

            # L2 regularisation
            total_loss += 0.5 * self.l2 * float(np.dot(w, w))
            grad = grad + self.l2 * w
            return total_loss, grad

        w0 = np.zeros(d)
        t0 = time.perf_counter()
        result = minimize(
            loss_and_grad,
            w0,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": self.max_iter, "ftol": self.tol},
        )
        self.fit_seconds_ = time.perf_counter() - t0
        self.coef_ = result.x
        self.n_iter_ = result.nit
        self.final_loss_ = float(result.fun)
        self.feature_names_ = feature_names or [f"f{i}" for i in range(d)]
        if self.verbose:
            log.info(
                "L-BFGS converged in %d iters, final loss %.4f, %.1fs",
                self.n_iter_, self.final_loss_, self.fit_seconds_,
            )
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Raw linear score s = X @ w (pre-softmax)."""
        return np.asarray(X, dtype=np.float64) @ self.coef_

    def predict_race_probabilities(
        self, X: np.ndarray, race_ids: np.ndarray
    ) -> np.ndarray:
        """Per-race softmax probabilities. Sums to 1 within each race."""
        s = self.decision_function(X)
        return _softmax_per_race(s, race_ids)


# ---- Helpers --------------------------------------------------------------

def _softmax_per_race(scores: np.ndarray, race_ids: np.ndarray) -> np.ndarray:
    """Efficient per-race softmax using pandas grouping."""
    scores = np.asarray(scores, dtype=np.float64)
    s_series = pd.Series(scores)
    r_series = pd.Series(race_ids)
    # Stable softmax: subtract per-race max first
    max_per_race = s_series.groupby(r_series).transform("max")
    exp_shift = np.exp(scores - max_per_race.to_numpy())
    exp_series = pd.Series(exp_shift)
    sum_per_race = exp_series.groupby(r_series).transform("sum").to_numpy()
    sum_per_race = np.where(sum_per_race <= 0, 1.0, sum_per_race)
    return exp_shift / sum_per_race


# ---- Self-test ------------------------------------------------------------

def _self_test() -> None:
    """Toy dataset: 500 races of 6 horses each. Winner has feature 1.0,
    losers have feature 0.0. Model should recover a large positive weight
    on that feature and give near-perfect predictions.
    """
    rng = np.random.default_rng(0)
    n_races = 500
    field_size = 6
    n = n_races * field_size
    race_ids = np.repeat(np.arange(n_races), field_size)
    y = np.zeros(n, dtype=int)
    for r in range(n_races):
        y[r * field_size + rng.integers(field_size)] = 1
    X = np.column_stack([
        y.astype(float),                       # perfect predictor
        rng.normal(size=n),                    # noise
    ])
    model = FundamentalModel(l2=0.001, verbose=False).fit(X, y, race_ids)
    p = model.predict_race_probabilities(X, race_ids)
    # Every race should have the winner with the highest prob
    correct = 0
    for r in range(n_races):
        idx = np.where(race_ids == r)[0]
        pred_winner = idx[np.argmax(p[idx])]
        actual_winner = idx[np.argmax(y[idx])]
        if pred_winner == actual_winner:
            correct += 1
    hit = correct / n_races
    print(f"Self-test hit rate: {hit*100:.1f}% "
          f"(coef: {model.coef_}, loss: {model.final_loss_:.4f})")
    assert hit > 0.95, f"expected near-perfect on this toy problem, got {hit}"
    print("ok")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    _self_test()
