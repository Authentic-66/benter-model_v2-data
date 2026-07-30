"""Benter two-stage blend.

Given per-race probabilities from a fundamental model (``p_f``) and the
market implied probability (``p_m``), the classical Benter blend forms:

    score_i    = alpha * log(p_f_i) + beta * log(p_m_i)
    p_final_i  = softmax_race(score_i)

The two scalars (alpha, beta) are learned on a held-out validation slice by
minimising the same per-race log-loss the metrics module measures.

Notes
-----
* ``alpha = beta = 1`` recovers the multiplicative blend ``p_f * p_m``
  (also renormalised per race) — often surprisingly close to optimal.
* ``alpha ≫ 0, beta = 0`` recovers the fundamental model alone.
* ``alpha = 0, beta ≫ 0`` recovers the market alone.
* Optimising the two together lets the model discover the right mix.

We use scipy L-BFGS on a two-variable problem; convergence is instant.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp


log = logging.getLogger("blend_model")


@dataclass
class BenterBlend:
    """Learn ``(alpha, beta)`` to blend fundamental + market log-probs."""

    l2: float = 0.0
    alpha_: float = float("nan")
    beta_: float = float("nan")
    final_loss_: float = float("nan")
    n_iter_: int = 0

    def fit(
        self,
        p_f: np.ndarray,
        p_m: np.ndarray,
        race_ids: np.ndarray,
        y_true: np.ndarray,
        eps: float = 1e-12,
    ) -> "BenterBlend":
        """Fit ``(alpha, beta)`` by minimising the per-race log-loss.

        Both inputs are treated as per-race normalised probabilities on the
        [0, 1] interval; we clip to ``eps`` for numerical stability before
        taking logs.
        """
        p_f = np.clip(np.asarray(p_f, dtype=np.float64), eps, 1 - eps)
        p_m = np.clip(np.asarray(p_m, dtype=np.float64), eps, 1 - eps)
        y_true = np.asarray(y_true, dtype=np.float64)
        race_ids = np.asarray(race_ids)

        log_pf = np.log(p_f)
        log_pm = np.log(p_m)

        r_series = pd.Series(race_ids)
        # Contributing races: exactly one marked winner
        contributing = []
        for r, idx in r_series.groupby(r_series).groups.items():
            idx = np.asarray(idx.values)
            if y_true[idx].sum() == 1.0:
                contributing.append((idx, int(idx[np.argmax(y_true[idx])])))
        if not contributing:
            raise ValueError("no races with a marked winner to fit blend")

        def objective(params: np.ndarray) -> float:
            alpha, beta = params
            total = 0.0
            for idx, winner_i in contributing:
                s = alpha * log_pf[idx] + beta * log_pm[idx]
                total += logsumexp(s) - (alpha * log_pf[winner_i]
                                         + beta * log_pm[winner_i])
            if self.l2 > 0:
                total += 0.5 * self.l2 * (alpha ** 2 + beta ** 2)
            return total

        # Warm start from (1, 1) — the multiplicative Benter baseline.
        result = minimize(
            objective,
            x0=np.array([1.0, 1.0]),
            method="L-BFGS-B",
            options={"maxiter": 100, "ftol": 1e-8},
        )
        self.alpha_, self.beta_ = float(result.x[0]), float(result.x[1])
        self.final_loss_ = float(result.fun)
        self.n_iter_ = result.nit
        return self

    def predict_race_probabilities(
        self,
        p_f: np.ndarray,
        p_m: np.ndarray,
        race_ids: np.ndarray,
        eps: float = 1e-12,
    ) -> np.ndarray:
        """Blend fundamental + market probs into final per-race probs."""
        if not np.isfinite(self.alpha_) or not np.isfinite(self.beta_):
            raise RuntimeError("call fit() before predict")
        p_f = np.clip(np.asarray(p_f, dtype=np.float64), eps, 1 - eps)
        p_m = np.clip(np.asarray(p_m, dtype=np.float64), eps, 1 - eps)
        scores = self.alpha_ * np.log(p_f) + self.beta_ * np.log(p_m)
        return _softmax_per_race(scores, race_ids)


# ---- Helpers --------------------------------------------------------------

def _softmax_per_race(scores: np.ndarray, race_ids: np.ndarray) -> np.ndarray:
    s_series = pd.Series(scores)
    r_series = pd.Series(race_ids)
    max_per_race = s_series.groupby(r_series).transform("max")
    exp_shift = np.exp(scores - max_per_race.to_numpy())
    sum_per_race = pd.Series(exp_shift).groupby(r_series).transform("sum").to_numpy()
    sum_per_race = np.where(sum_per_race <= 0, 1.0, sum_per_race)
    return exp_shift / sum_per_race


# ---- Self-test ------------------------------------------------------------

def _self_test() -> None:
    """Synthetic: perfect market, noisy fundamental. Blend should lean on market."""
    rng = np.random.default_rng(42)
    n_races = 500
    field_size = 6
    n = n_races * field_size
    race_ids = np.repeat(np.arange(n_races), field_size)
    y = np.zeros(n, dtype=int)
    for r in range(n_races):
        y[r * field_size + rng.integers(field_size)] = 1
    # p_market equals true probability (perfect market on this synth)
    p_m = np.where(y == 1, 0.7, 0.06)
    # Re-normalise per race
    from market_model import MarketModel  # noqa
    # Use direct grouping since MarketModel expects odds
    pm_series = pd.Series(p_m)
    rid_series = pd.Series(race_ids)
    p_m = p_m / pm_series.groupby(rid_series).transform("sum").to_numpy()
    # p_fundamental = uniform (adds no info)
    p_f = np.full(n, 1.0 / field_size)

    blend = BenterBlend().fit(p_f, p_m, race_ids, y)
    print(f"alpha = {blend.alpha_:.3f}, beta = {blend.beta_:.3f}")
    assert blend.beta_ > blend.alpha_, (
        "market should dominate a uniform fundamental"
    )
    print("ok")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    _self_test()
