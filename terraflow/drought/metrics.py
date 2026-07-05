"""Evaluation metrics for the drought-impact benchmark.

Regression (continuous ``drought_loss_ratio``): R², RMSE, and Spearman rank correlation — the
rank metric is the robust headline because the loss-experience ratio has a heavy tail and can
exceed 1 (see :mod:`terraflow.drought.labels`).

Classification (binary ``significant_drought_loss``): ROC-AUC, average precision (PR-AUC — the
positive class is imbalanced, so PR-AUC is the honest headline), and Brier score.
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """R², RMSE, Spearman ρ. Returns NaNs gracefully for degenerate inputs."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred)) if len(np.unique(y_true)) > 1 else float("nan")
    # Spearman is undefined if either input is constant (e.g. a constant-mean baseline).
    constant = np.unique(y_true).size < 2 or np.unique(y_pred).size < 2
    if len(y_true) <= 2 or constant:
        rho = float("nan")
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rho = float(spearmanr(y_true, y_pred).statistic)
    return {"r2": r2, "rmse": rmse, "spearman": rho}


def classification_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float]:
    """ROC-AUC, average precision (PR-AUC), Brier. AUC/AP are NaN if only one class present."""
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)
    single_class = len(np.unique(y_true)) < 2
    return {
        "roc_auc": float("nan") if single_class else float(roc_auc_score(y_true, y_score)),
        "pr_auc": float("nan") if single_class else float(average_precision_score(y_true, y_score)),
        "brier": float(brier_score_loss(y_true, np.clip(y_score, 0.0, 1.0))),
        "positives": int(y_true.sum()),
        "n": int(len(y_true)),
    }
