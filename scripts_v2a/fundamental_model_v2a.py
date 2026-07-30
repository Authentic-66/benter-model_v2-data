"""Binary-logistic fundamental model for the ITM target (Phase 3G).

The v2 model was conditional logit — softmax within each race, exactly one
winner per race. For ITM (top-3 finish) that constraint doesn't hold:
three horses per race are positive, and their outcomes aren't jointly
constrained the same way. So we switch to plain binary logistic
regression per entry:

    L(w) = -sum_i weight_i * [y_i log s_i + (1 - y_i) log (1 - s_i)]
           + 0.5 * lambda * ||w||^2
    s_i  = sigmoid(x_i . w)

Analytical gradient (closed form):

    dL/dw = X.T @ (weight * (s - y)) + lambda * w

Solved via scipy L-BFGS-B, same as ``scripts/fundamental_model.FundamentalModel``.
Interface (``fit``, ``coef_``, ``predict_probabilities``) mirrors v2 so
callers barely notice the swap.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit  # numerically-stable sigmoid


log = logging.getLogger("fundamental_model_v2a")


@dataclass
class FundamentalModelITM:
    """Binary-logistic fitter for the ITM target, sklearn-ish interface."""

    l2: float = 0.01
    max_iter: int = 200
    tol: float = 1e-6
    verbose: bool = False

    coef_: np.ndarray = field(default_factory=lambda: np.empty(0))
    intercept_: float = 0.0
    feature_names_: list[str] = field(default_factory=list)
    n_iter_: int = 0
    final_loss_: float = float("nan")
    fit_seconds_: float = float("nan")

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
        feature_names: list[str] | None = None,
    ) -> "FundamentalModelITM":
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        n, d = X.shape
        if sample_weight is None:
            sample_weight = np.ones(n, dtype=np.float64)
        sample_weight = np.asarray(sample_weight, dtype=np.float64)
        # Append a bias column so we learn an intercept (matters when the
        # ITM rate is ~0.39, not 0.5).
        X_aug = np.column_stack([X, np.ones(n, dtype=np.float64)])

        def loss_and_grad(w: np.ndarray) -> tuple[float, np.ndarray]:
            scores = X_aug @ w
            # log-loss via log1p for numerical stability
            # positive-y contribution: -y * (score - log(1 + exp(score)))
            # negative-y contribution: -(1-y) * (-log(1 + exp(score)))
            # Use log1p(exp(-|s|)) trick:
            log1p_exp = np.log1p(np.exp(-np.abs(scores))) + np.maximum(scores, 0.0)
            log_loss = -(y * scores - log1p_exp)
            total = float(np.sum(sample_weight * log_loss))
            # Regularise weights but NOT the intercept
            reg_w = w[:-1]
            total += 0.5 * self.l2 * float(np.dot(reg_w, reg_w))
            # Gradient
            probs = expit(scores)
            residual = sample_weight * (probs - y)
            grad = X_aug.T @ residual
            grad[:-1] += self.l2 * reg_w   # add reg to non-intercept dims
            return total, grad

        w0 = np.zeros(d + 1)
        t0 = time.perf_counter()
        result = minimize(
            loss_and_grad,
            w0,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": self.max_iter, "ftol": self.tol},
        )
        self.fit_seconds_ = time.perf_counter() - t0
        self.coef_ = result.x[:-1]
        self.intercept_ = float(result.x[-1])
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
        return np.asarray(X, dtype=np.float64) @ self.coef_ + self.intercept_

    def predict_probabilities(self, X: np.ndarray) -> np.ndarray:
        """Per-entry sigmoid — NOT per-race normalised.

        Callers can freely rank horses within a race by these probabilities;
        they don't sum to 1 within a race (about 3 do, since 3 horses per
        race hit ITM in the training set).
        """
        return expit(self.decision_function(X))


# ---- Self-test ------------------------------------------------------------

def _self_test() -> None:
    """Toy dataset — recovered coefficients should reflect the signal."""
    rng = np.random.default_rng(0)
    n = 5000
    X = np.column_stack([
        rng.normal(size=n),          # noise
        rng.normal(size=n),          # signal (will get weight ~2)
    ])
    logits = 2.0 * X[:, 1] - 0.5
    y = (expit(logits) > rng.uniform(size=n)).astype(int)
    model = FundamentalModelITM(l2=0.01, verbose=False).fit(X, y)
    print(f"coef = {model.coef_}, intercept = {model.intercept_:.3f}")
    print(f"positive rate: {y.mean():.3f}, model mean prob: "
          f"{model.predict_probabilities(X).mean():.3f}")
    # Should recover ~[0, 2] and intercept ~-0.5
    assert abs(model.coef_[0]) < 0.15, model.coef_
    assert 1.6 < model.coef_[1] < 2.4, model.coef_
    print("ok")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    _self_test()
