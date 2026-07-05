"""Tests for predictor aggregation, splits, and metrics."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from terraflow.drought.config import DroughtConfig
from terraflow.drought.metrics import classification_metrics, regression_metrics
from terraflow.drought.predictors import (
    aggregate_predictors,
    climate_predictor_columns,
    severity_predictor_columns,
)
from terraflow.drought.splits import (
    describe_splits,
    loyo_folds,
    spatial_folds,
    temporal_masks,
)

from .drought_synthetic import make_feature_table


def _cfg(tmp_path: Path, **kw) -> DroughtConfig:
    d = dict(
        states=["17", "19"],
        year_min=2000,
        year_max=2001,
        rma_dir=tmp_path,
        feature_table=tmp_path / "x",
        output_dir=tmp_path / "o",
    )
    d.update(kw)
    return DroughtConfig(**d)


def test_aggregate_respects_cutoff_and_shapes(tmp_path: Path):
    ft = make_feature_table(["17001", "19005"], [2000, 2001], doys=(130, 160, 190, 220))
    cfg = _cfg(tmp_path, cutoff_doy=200)
    out = aggregate_predictors(ft, cfg)

    assert set(zip(out["GEOID"], out["year"])) == {("17001", 2000), ("17001", 2001), ("19005", 2000), ("19005", 2001)}
    # doy 220 is past the cutoff → 3 obs per county-year.
    assert (out["n_obs"] == 3).all()
    for col in climate_predictor_columns()[:2] + severity_predictor_columns()[:2]:
        assert col in out.columns
    assert "n_stress_weeks" in out.columns


def test_aggregate_last_is_value_at_max_doy(tmp_path: Path):
    ft = make_feature_table(["17001"], [2000], doys=(130, 160, 190))
    cfg = _cfg(tmp_path, cutoff_doy=300)
    out = aggregate_predictors(ft, cfg)
    expected_last = ft[(ft.doy == 190)]["NDVI_anom_z"].iloc[0]
    assert out["NDVI_anom_z_last"].iloc[0] == expected_last


def test_temporal_masks_disjoint(tmp_path: Path):
    import pandas as pd

    df = pd.DataFrame({"GEOID": ["17001"] * 5, "year": [2000, 2001, 2002, 2012, 2017]})
    cfg = _cfg(tmp_path, year_max=2017, test_years=[2012, 2017], train_max_year=2002)
    train, test = temporal_masks(df, cfg)
    assert not (train & test).any()
    assert list(df["year"][test]) == [2012, 2017]
    assert set(df["year"][train]) == {2000, 2001, 2002}


def test_spatial_and_loyo_folds(tmp_path: Path):
    import pandas as pd

    df = pd.DataFrame({"GEOID": ["17001", "17003", "19001", "19003"], "year": [2000, 2001, 2000, 2001]})
    states = [s for s, _tr, _te in spatial_folds(df)]
    assert states == ["17", "19"]
    for _s, tr, te in spatial_folds(df):
        assert not (tr & te).any()
    years = [y for y, _tr, _te in loyo_folds(df)]
    assert years == [2000, 2001]


def test_describe_splits_keys(tmp_path: Path):
    d = describe_splits(_cfg(tmp_path))
    assert set(d) == {"temporal", "spatial", "loyo"}
    assert d["spatial"]["scheme"] == "leave-one-state-out"


def test_regression_metrics():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    perfect = regression_metrics(y, y)
    assert perfect["spearman"] == 1.0
    assert perfect["rmse"] == 0.0
    # constant prediction → spearman undefined (NaN), no warning/crash.
    const = regression_metrics(y, np.ones_like(y))
    assert np.isnan(const["spearman"])


def test_classification_metrics():
    y = np.array([0, 0, 1, 1])
    sep = classification_metrics(y, np.array([0.1, 0.2, 0.8, 0.9]))
    assert sep["roc_auc"] == 1.0
    assert sep["positives"] == 2
    # single-class truth → AUC/AP undefined but Brier still defined.
    single = classification_metrics(np.array([0, 0, 0]), np.array([0.1, 0.2, 0.3]))
    assert np.isnan(single["roc_auc"])
    assert not np.isnan(single["brier"])
