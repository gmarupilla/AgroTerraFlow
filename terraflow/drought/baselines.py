"""Baseline models for the drought-impact benchmark.

Three tiers, to make the leaderboard interpretable:
- **naive** — constant train mean, and per-county historical mean (the bar any model must beat).
- **severity-only** — a model on the USDM severity aggregates alone. USDM D2+ is a *strong*
  baseline for loss; the point of isolating it is to quantify how much within-season climate signal
  adds on top (and that it is available earlier in the season for early warning).
- **climate ML** — Ridge / RandomForest / GradientBoosting on the within-season anomaly features.

All estimators are seeded (``random_state=0``, ``n_jobs=1``) so the leaderboard is deterministic.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge

from .predictors import climate_predictor_columns, severity_predictor_columns

RANDOM_STATE = 0
REGRESSION_TARGET = "drought_loss_ratio"
CLASSIFICATION_TARGET = "significant_drought_loss"


def feature_columns(which: str) -> list[str]:
    """Feature column names for a feature set: 'climate', 'severity', or 'all'."""
    if which == "climate":
        return climate_predictor_columns() + ["n_obs", "n_stress_weeks"]
    if which == "severity":
        return severity_predictor_columns()
    if which == "all":
        return feature_columns("climate") + feature_columns("severity")
    raise ValueError(f"Unknown feature set: {which!r}")


def feature_matrix(df: pd.DataFrame, which: str) -> np.ndarray:
    """Numeric feature matrix (NaN → 0.0; anomalies are z-scores, so 0 is neutral)."""
    cols = feature_columns(which)
    return df[cols].to_numpy(dtype=float, na_value=0.0)


def make_regressors() -> dict[str, Any]:
    return {
        "Ridge": Ridge(alpha=1.0),
        "RandomForest": RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE, n_jobs=1),
        "GradientBoost": GradientBoostingRegressor(random_state=RANDOM_STATE),
    }


def make_classifiers() -> dict[str, Any]:
    return {
        "LogReg": LogisticRegression(max_iter=1000),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, random_state=RANDOM_STATE, n_jobs=1, class_weight="balanced"
        ),
        "GradientBoost": GradientBoostingClassifier(random_state=RANDOM_STATE),
    }


class MeanBaseline:
    """Predict the constant training mean of the target."""

    def fit(self, df_train: pd.DataFrame, target: str) -> "MeanBaseline":
        self.value_ = float(df_train[target].astype(float).mean())
        return self

    def predict(self, df_test: pd.DataFrame) -> np.ndarray:
        return np.full(len(df_test), self.value_, dtype=float)


class CountyHistoryBaseline:
    """Predict each county's historical (training) mean target, falling back to the global mean."""

    def fit(self, df_train: pd.DataFrame, target: str) -> "CountyHistoryBaseline":
        self.global_ = float(df_train[target].astype(float).mean())
        self.by_county_ = df_train.groupby("GEOID")[target].mean().astype(float).to_dict()
        return self

    def predict(self, df_test: pd.DataFrame) -> np.ndarray:
        return df_test["GEOID"].map(self.by_county_).fillna(self.global_).to_numpy(dtype=float)
