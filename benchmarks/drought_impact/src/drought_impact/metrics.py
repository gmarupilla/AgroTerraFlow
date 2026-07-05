"""Scoring metrics for the two benchmark tasks.

Regression (loss-cost): R², RMSE, Spearman ρ.
Classification (significant-loss flag): ROC-AUC, PR-AUC (average precision), Brier score.

Spearman uses pandas' rank correlation (no scipy dependency). Degenerate cases (a
single-class ``y_true``, or fewer than two samples) return NaN rather than raising, so a
per-year / per-block breakdown never crashes on a sparse fold.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    r2_score,
    roc_auc_score,
)


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) < 2:
        return {"r2": math.nan, "rmse": math.nan, "spearman": math.nan}
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    r2 = float(r2_score(y_true, y_pred)) if np.ptp(y_true) > 0 else math.nan
    # Spearman is undefined when either side is constant (e.g. a climatology baseline).
    if np.ptp(y_true) == 0 or np.ptp(y_pred) == 0:
        spearman = math.nan
    else:
        spearman = float(pd.Series(y_true).corr(pd.Series(y_pred), method="spearman"))
    return {"r2": r2, "rmse": rmse, "spearman": spearman}


def classification_metrics(y_true, y_prob) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    out = {"roc_auc": math.nan, "pr_auc": math.nan, "brier": math.nan}
    if len(y_true) < 2:
        return out
    out["brier"] = float(brier_score_loss(y_true, y_prob)) if len(np.unique(y_true)) >= 1 else math.nan
    # ROC-AUC / PR-AUC require both classes present.
    if len(np.unique(y_true)) == 2:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        out["pr_auc"] = float(average_precision_score(y_true, y_prob))
    return out


def per_group_metrics(
    df: pd.DataFrame,
    group_col: str,
    y_true_col: str,
    y_pred_col: str,
    *,
    task: str = "regression",
) -> pd.DataFrame:
    """Compute metrics within each group (e.g. per year or per spatial block).

    ``task`` is ``"regression"`` or ``"classification"``.
    """
    metric_fn = regression_metrics if task == "regression" else classification_metrics
    rows = []
    for key, sub in df.groupby(group_col):
        m = metric_fn(sub[y_true_col], sub[y_pred_col])
        rows.append({group_col: key, **m})
    return pd.DataFrame(rows)
