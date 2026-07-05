"""Run the drought-impact benchmark leaderboard.

Headline = the official **temporal** split (train on early years, test on held-out years incl. the
2012 extreme). Also reports a **spatial** leave-one-state-out summary for the climate models. The
severity-only baseline is included in both to expose the severity≠impact gap.

Writes ``evaluate_report.json`` and ``leaderboard.csv`` to the run's output directory.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .baselines import (
    CLASSIFICATION_TARGET,
    REGRESSION_TARGET,
    CountyHistoryBaseline,
    MeanBaseline,
    feature_matrix,
    make_classifiers,
    make_regressors,
)
from .config import DroughtConfig
from .metrics import classification_metrics, regression_metrics
from .splits import spatial_folds, temporal_masks


def _fit_predict_regression(name: str, feats: str, train: pd.DataFrame, test: pd.DataFrame) -> dict:
    est = make_regressors()[name]
    est.fit(feature_matrix(train, feats), train[REGRESSION_TARGET].to_numpy(dtype=float))
    pred = est.predict(feature_matrix(test, feats))
    return regression_metrics(test[REGRESSION_TARGET].to_numpy(dtype=float), pred)


def _fit_predict_classification(name: str, feats: str, train: pd.DataFrame, test: pd.DataFrame) -> dict:
    y_train = train[CLASSIFICATION_TARGET].to_numpy(dtype=int)
    y_test = test[CLASSIFICATION_TARGET].to_numpy(dtype=int)
    # A one-class training set (rare-event scope / high threshold) can't fit sklearn classifiers;
    # fall back to a constant predictor at the single observed class rather than crashing.
    if np.unique(y_train).size < 2:
        return classification_metrics(y_test, np.full(len(y_test), float(y_train[0]) if len(y_train) else 0.0))
    est = make_classifiers()[name]
    est.fit(feature_matrix(train, feats), y_train)
    if hasattr(est, "predict_proba"):
        score = est.predict_proba(feature_matrix(test, feats))[:, 1]
    else:  # pragma: no cover - all configured classifiers expose predict_proba
        score = est.predict(feature_matrix(test, feats)).astype(float)
    return classification_metrics(y_test, score)


def _temporal_leaderboard(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    regression: dict[str, dict] = {
        "Mean": regression_metrics(
            test[REGRESSION_TARGET].to_numpy(dtype=float),
            MeanBaseline().fit(train, REGRESSION_TARGET).predict(test),
        ),
        "CountyHistory": regression_metrics(
            test[REGRESSION_TARGET].to_numpy(dtype=float),
            CountyHistoryBaseline().fit(train, REGRESSION_TARGET).predict(test),
        ),
    }
    for name in make_regressors():
        regression[f"{name}[severity]"] = _fit_predict_regression(name, "severity", train, test)
        regression[f"{name}[climate]"] = _fit_predict_regression(name, "climate", train, test)

    classification: dict[str, dict] = {
        "PositiveRate": classification_metrics(
            test[CLASSIFICATION_TARGET].to_numpy(dtype=int),
            MeanBaseline().fit(train, CLASSIFICATION_TARGET).predict(test),
        ),
        "CountyHistory": classification_metrics(
            test[CLASSIFICATION_TARGET].to_numpy(dtype=int),
            CountyHistoryBaseline().fit(train, CLASSIFICATION_TARGET).predict(test),
        ),
    }
    for name in make_classifiers():
        classification[f"{name}[severity]"] = _fit_predict_classification(name, "severity", train, test)
        classification[f"{name}[climate]"] = _fit_predict_classification(name, "climate", train, test)

    return {"regression": regression, "classification": classification}


def _spatial_summary(benchmark: pd.DataFrame) -> dict:
    """Mean classification metrics across leave-one-state-out folds for the climate RF/GBM."""
    summary: dict[str, dict] = {}
    for name in ("RandomForest", "GradientBoost"):
        aucs, aps = [], []
        for _state, tr_mask, te_mask in spatial_folds(benchmark):
            tr, te = benchmark[tr_mask], benchmark[te_mask]
            if te[CLASSIFICATION_TARGET].nunique() < 2 or tr[CLASSIFICATION_TARGET].nunique() < 2:
                continue
            m = _fit_predict_classification(name, "climate", tr, te)
            aucs.append(m["roc_auc"])
            aps.append(m["pr_auc"])
        summary[f"{name}[climate]"] = {
            "mean_roc_auc": float(np.nanmean(aucs)) if aucs else float("nan"),
            "mean_pr_auc": float(np.nanmean(aps)) if aps else float("nan"),
            "n_folds": len(aucs),
        }
    return summary


def run_leaderboard(benchmark: pd.DataFrame, cfg: DroughtConfig, *, write_dir: Path | None = None) -> dict:
    """Compute the full leaderboard; optionally persist report + CSV to ``write_dir``."""
    train_mask, test_mask = temporal_masks(benchmark, cfg)
    train, test = benchmark[train_mask], benchmark[test_mask]
    if len(train) == 0 or len(test) == 0:
        raise ValueError("Temporal split produced an empty train or test set; check config years.")

    report = {
        "temporal": _temporal_leaderboard(train, test),
        "spatial_loso": _spatial_summary(benchmark),
        "counts": {"n_train": int(len(train)), "n_test": int(len(test)), "test_years": list(cfg.test_years)},
    }

    if write_dir is not None:
        write_dir = Path(write_dir)
        write_dir.mkdir(parents=True, exist_ok=True)
        (write_dir / "evaluate_report.json").write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
        _leaderboard_frame(report).to_csv(write_dir / "leaderboard.csv", index=False)
    return report


def _json_safe(obj):
    """Recursively replace non-finite floats (NaN/inf) with None so the JSON is strict-parseable."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _leaderboard_frame(report: dict) -> pd.DataFrame:
    rows = []
    for task, models in report["temporal"].items():
        for model, metrics in models.items():
            rows.append({"split": "temporal", "task": task, "model": model, **metrics})
    return pd.DataFrame(rows)
