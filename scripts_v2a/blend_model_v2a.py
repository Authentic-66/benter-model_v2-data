"""Benter-style two-stage blend for the ITM target.

Analogous to ``scripts/blend_model.BenterBlend`` but per-entry (no per-race
softmax) because the ITM target is a binary logistic estimate not a
categorical choice.

Given fundamental P(ITM) ``p_f`` and market P(ITM) ``p_m`` (both per-entry
in [0, 1]), we form a blended log-odds and pass it through a sigmoid:

    logit_final = alpha * logit(p_f) + beta * logit(p_m) + gamma
    p_final     = sigmoid(logit_final)

Three scalars ``(alpha, beta, gamma)`` are learned by minimising the
weighted binary cross-entropy on a validation slice. ``gamma`` is an
intercept term that lets the model recalibrate the overall positive rate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit


log = logging.getLogger("blend_model_v2a")


def _logit(p: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    p = np.clip(p, eps, 1 - eps)
    return np.log(p) - np.log(1 - p)


@dataclass
class BenterBlendITM:
    """3-parameter blend: alpha, beta, gamma."""

    alpha_: float = float("nan")
    beta_: float = float("nan")
    gamma_: float = float("nan")
    final_loss_: float = float("nan")
    n_iter_: int = 0

    def fit(
        self,
        p_f: np.ndarray,
        p_m: np.ndarray,
        y_true: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "BenterBlendITM":
        p_f = np.asarray(p_f, dtype=float)
        p_m = np.asarray(p_m, dtype=float)
        y = np.asarray(y_true, dtype=float)
        if sample_weight is None:
            sample_weight = np.ones_like(y)
        w = np.asarray(sample_weight, dtype=float)

        # Rows where either input is NaN are dropped from the fit — they
        # can't contribute a gradient.
        good = np.isfinite(p_f) & np.isfinite(p_m) & np.isfinite(y)
        if not good.any():
            raise ValueError("no valid rows to fit blend")

        lf = _logit(p_f[good])
        lm = _logit(p_m[good])
        yv = y[good]
        wv = w[good]

        def objective(params: np.ndarray) -> float:
            alpha, beta, gamma = params
            scores = alpha * lf + beta * lm + gamma
            log1p_exp = np.log1p(np.exp(-np.abs(scores))) + np.maximum(scores, 0.0)
            log_loss = -(yv * scores - log1p_exp)
            return float(np.sum(wv * log_loss))

        # Warm start from (1, 1, 0) — the equally-weighted Benter form.
        result = minimize(
            objective,
            x0=np.array([1.0, 1.0, 0.0]),
            method="L-BFGS-B",
            options={"maxiter": 200, "ftol": 1e-8},
        )
        self.alpha_, self.beta_, self.gamma_ = (
            float(result.x[0]), float(result.x[1]), float(result.x[2]),
        )
        self.final_loss_ = float(result.fun)
        self.n_iter_ = result.nit
        return self

    def predict(
        self, p_f: np.ndarray, p_m: np.ndarray,
    ) -> np.ndarray:
        if not np.isfinite(self.alpha_):
            raise RuntimeError("call fit() before predict")
        lf = _logit(np.asarray(p_f, dtype=float))
        lm = _logit(np.asarray(p_m, dtype=float))
        return expit(self.alpha_ * lf + self.beta_ * lm + self.gamma_)


# ---- Self-test ------------------------------------------------------------

def _self_test() -> None:
    """Perfect fundamental + noisy market: blend should lean fundamental."""
    rng = np.random.default_rng(0)
    n = 5000
    y = rng.uniform(size=n) > 0.6         # ~40% positive rate
    y = y.astype(int)
    # Perfect fundamental (leaks label)
    p_f = np.where(y == 1,
                    rng.uniform(0.6, 0.9, size=n),
                    rng.uniform(0.1, 0.4, size=n))
    # Random market
    p_m = rng.uniform(0.2, 0.6, size=n)
    blend = BenterBlendITM().fit(p_f, p_m, y)
    print(f"alpha={blend.alpha_:.3f}, beta={blend.beta_:.3f}, gamma={blend.gamma_:.3f}")
    assert blend.alpha_ > blend.beta_, "fundamental should dominate"
    print("ok")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    _self_test()
