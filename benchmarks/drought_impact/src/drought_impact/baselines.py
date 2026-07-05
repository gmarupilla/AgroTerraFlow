"""Baselines + leaderboard for the two benchmark tasks.

Three tiers, mirroring the plan:

- **naive** — county historical loss rate, and climatology (global training mean).
- **index** — a single external severity index used directly as the signal (USDM D2+,
  VCI/TCI/VHI, flashdry WxCond prob). These probe the headline hook: a good drought
  *severity* index only partially predicts drought *loss*. An index baseline is run for
  whichever of :data:`INDEX_COLUMN_CANDIDATES` is present in the benchmark frame.
- **ML** — Ridge / RandomForest / GradientBoosting on the aggregated ``_anom`` predictors.

Everything is fit on the temporal-split train rows and scored on the held-out test rows.
Degenerate folds (single-class, too few rows) yield NaN metrics rather than errors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge

from .metrics import classification_metrics, regression_metrics

TARGET_REG = "drought_loss_cost"
TARGET_CLF = "significant_loss"

# Columns that are never predictors (labels, coverage, keys, and leaked signal).
_NON_FEATURE = {
    "GEOID",
    "year",
    "drought_loss_cost",
    "significant_loss",
    "drought_indemnity",
    "county_liability",
    "total_premium_sum",
    "total_indemnity",
    "insured_acres",
    "planted_acres",
    "insured_acre_fraction",
}

# External severity indices, used directly as a signal when present.
INDEX_COLUMN_CANDIDATES = ["wxcond_prob", "usdm_d2plus", "vci", "tci", "vhi"]

_RANDOM_STATE = 0


def feature_columns(benchmark: pd.DataFrame) -> list[str]:
    """Return the aggregated ``_anom`` predictor columns (numeric, non-label, non-index)."""
    cols = []
    for c in benchmark.columns:
        if c in _NON_FEATURE or c in INDEX_COLUMN_CANDIDATES:
            continue
        if pd.api.types.is_numeric_dtype(benchmark[c]):
            cols.append(c)
    return sorted(cols)


def _xy(df: pd.DataFrame, feats: list[str], target: str):
    x = df[feats].to_numpy(dtype=float) if feats else np.empty((len(df), 0))
    x = np.nan_to_num(x, nan=0.0)
    y = df[target].to_numpy(dtype=float)
    return x, y


def _minmax(series: pd.Series) -> np.ndarray:
    v = series.to_numpy(dtype=float)
    v = np.nan_to_num(v, nan=np.nanmean(v) if np.isfinite(np.nanmean(v)) else 0.0)
    lo, hi = np.min(v), np.max(v)
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v)


def run_baselines(benchmark: pd.DataFrame, splits: dict) -> pd.DataFrame:
    """Fit every baseline on the temporal train split, score on test → leaderboard frame.

    Returns one row per (baseline, task) with the relevant metrics.
    """
    train_keys = set(splits["temporal"]["train"])
    test_keys = set(splits["temporal"]["test"])
    keyed = benchmark.assign(_key=[f"{g}:{int(y)}" for g, y in zip(benchmark["GEOID"], benchmark["year"])])
    train = keyed[keyed["_key"].isin(train_keys)].copy()
    test = keyed[keyed["_key"].isin(test_keys)].copy()
    feats = feature_columns(benchmark)

    rows: list[dict] = []

    def add_reg(name: str, y_pred) -> None:
        rows.append({"baseline": name, "task": "regression", **regression_metrics(test[TARGET_REG], y_pred)})

    def add_clf(name: str, y_prob) -> None:
        rows.append({"baseline": name, "task": "classification", **classification_metrics(test[TARGET_CLF], y_prob)})

    if len(train) < 2 or len(test) < 1:
        return pd.DataFrame(rows)

    # --- naive ---------------------------------------------------------------------
    global_mean = float(train[TARGET_REG].mean())
    add_reg("naive_climatology", np.full(len(test), global_mean))
    county_mean = train.groupby("GEOID")[TARGET_REG].mean()
    add_reg("naive_county", test["GEOID"].map(county_mean).fillna(global_mean).to_numpy())

    prevalence = float(train[TARGET_CLF].mean())
    add_clf("naive_prevalence", np.full(len(test), prevalence))
    county_pos = train.groupby("GEOID")[TARGET_CLF].mean()
    add_clf("naive_county", test["GEOID"].map(county_pos).fillna(prevalence).to_numpy())

    # --- index (severity != impact) ------------------------------------------------
    for col in INDEX_COLUMN_CANDIDATES:
        if col in benchmark.columns:
            add_reg(f"index_{col}", _index_reg(train, test, col))
            add_clf(f"index_{col}", _minmax(test[col]))

    # --- ML ------------------------------------------------------------------------
    if feats:
        x_tr, y_tr_reg = _xy(train, feats, TARGET_REG)
        x_te, _ = _xy(test, feats, TARGET_REG)
        y_tr_clf = train[TARGET_CLF].to_numpy(dtype=int)

        reg_models = {
            "ridge": Ridge(),
            "random_forest": RandomForestRegressor(n_estimators=200, random_state=_RANDOM_STATE),
            "gradient_boosting": GradientBoostingRegressor(random_state=_RANDOM_STATE),
        }
        for name, model in reg_models.items():
            model.fit(x_tr, y_tr_reg)
            add_reg(name, model.predict(x_te))

        if len(np.unique(y_tr_clf)) == 2:
            clf_models = {
                "logistic": LogisticRegression(max_iter=1000),
                "random_forest": RandomForestClassifier(n_estimators=200, random_state=_RANDOM_STATE),
                "gradient_boosting": GradientBoostingClassifier(random_state=_RANDOM_STATE),
            }
            for name, model in clf_models.items():
                model.fit(x_tr, y_tr_clf)
                add_clf(name, model.predict_proba(x_te)[:, 1])

    return pd.DataFrame(rows)


def _index_reg(train: pd.DataFrame, test: pd.DataFrame, col: str) -> np.ndarray:
    """Univariate linear fit of the loss-cost on one index column (test predictions)."""
    from sklearn.linear_model import LinearRegression

    x_tr = np.nan_to_num(train[[col]].to_numpy(dtype=float))
    x_te = np.nan_to_num(test[[col]].to_numpy(dtype=float))
    model = LinearRegression().fit(x_tr, train[TARGET_REG].to_numpy(dtype=float))
    return model.predict(x_te)
