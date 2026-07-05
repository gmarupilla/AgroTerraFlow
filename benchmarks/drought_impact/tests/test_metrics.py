import math

from drought_impact.metrics import classification_metrics, regression_metrics


def test_perfect_regression():
    m = regression_metrics([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0])
    assert m["r2"] == 1.0
    assert m["rmse"] == 0.0
    assert m["spearman"] == 1.0


def test_regression_rmse_value():
    m = regression_metrics([0.0, 0.0], [1.0, -1.0])
    assert m["rmse"] == 1.0


def test_perfect_classification():
    m = classification_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    assert m["roc_auc"] == 1.0
    assert m["pr_auc"] == 1.0
    assert 0.0 <= m["brier"] < 0.1


def test_single_class_returns_nan_auc():
    m = classification_metrics([1, 1, 1], [0.4, 0.5, 0.6])
    assert math.isnan(m["roc_auc"])
    assert math.isnan(m["pr_auc"])


def test_too_few_samples_is_nan():
    assert math.isnan(regression_metrics([1.0], [1.0])["r2"])
