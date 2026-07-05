import pytest

from drought_impact.labels import build_labels
from drought_impact.rma import load_col


@pytest.fixture
def labels(bench_cfg):
    return build_labels(load_col(bench_cfg), bench_cfg)


def test_loss_cost_is_drought_indemnity_over_liability(labels):
    row = labels[(labels["GEOID"] == "17001") & (labels["year"] == 2012)].iloc[0]
    # drought indemnity 300k over 1M liability = 0.30
    assert row["drought_loss_cost"] == pytest.approx(0.30)


def test_zero_loss_county_year_is_negative_not_missing(labels):
    row = labels[(labels["GEOID"] == "17003") & (labels["year"] == 2010)].iloc[0]
    assert row["drought_indemnity"] == 0.0
    assert row["drought_loss_cost"] == 0.0
    assert row["significant_loss"] == 0


def test_2012_has_the_largest_loss_cost(labels):
    per_year_max = labels.groupby("year")["drought_loss_cost"].max()
    assert per_year_max.idxmax() == 2012


def test_binary_flag_positives_are_minority(labels):
    positives = labels["significant_loss"].sum()
    assert 0 < positives < len(labels)  # imbalanced, PR-AUC matters
    # only 2012 county-years cross the 0.10 threshold
    assert set(labels[labels["significant_loss"] == 1]["year"]) == {2012}
