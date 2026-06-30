"""Tests for terraflow.temporal — multi-temporal climate aggregation engine (#138b)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from terraflow.config import Scenario, TemporalAggregation
from terraflow.temporal import (
    aggregate_per_station,
    compute_per_station_aggregations,
    filter_scenario,
)


def _daily_series(
    station_id: str,
    lat: float,
    lon: float,
    start: str,
    end: str,
    temperature_c_fn=lambda dt: 20.0,
    precipitation_mm_fn=lambda dt: 1.0,
) -> pd.DataFrame:
    """Build a synthetic daily station time-series."""
    dates = pd.date_range(start=start, end=end, freq="D")
    rows = []
    for d in dates:
        rows.append(
            {
                "station_id": station_id,
                "lat": lat,
                "lon": lon,
                "date": d,
                "temperature_c": float(temperature_c_fn(d)),
                "precipitation_mm": float(precipitation_mm_fn(d)),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# filter_scenario
# ---------------------------------------------------------------------------


def test_filter_scenario_returns_inclusive_year_range():
    df = pd.concat(
        [
            _daily_series("S1", 0.0, 0.0, "2018-12-29", "2019-01-03"),
            _daily_series("S1", 0.0, 0.0, "2020-12-29", "2021-01-03"),
        ],
        ignore_index=True,
    )
    scenario = Scenario(name="window", period=[2019, 2020])
    filtered = filter_scenario(df, scenario)
    years = pd.to_datetime(filtered["date"]).dt.year.unique()
    assert set(years) == {2019, 2020}


def test_filter_scenario_empty_result_for_out_of_range():
    df = _daily_series("S1", 0.0, 0.0, "2010-01-01", "2010-12-31")
    scenario = Scenario(name="future", period=[2100, 2110])
    filtered = filter_scenario(df, scenario)
    assert filtered.empty


def test_filter_scenario_rejects_missing_date_column():
    df = pd.DataFrame({"station_id": ["S1"], "temperature_c": [20.0]})
    scenario = Scenario(name="x", period=[2000, 2010])
    with pytest.raises(ValueError, match="'date'"):
        filter_scenario(df, scenario)


# ---------------------------------------------------------------------------
# annual_mean
# ---------------------------------------------------------------------------


def test_aggregate_annual_mean_simple():
    """Constant 20°C over a year → annual mean is 20°C."""
    df = _daily_series(
        "S1",
        0.0,
        0.0,
        "2020-01-01",
        "2020-12-31",
        temperature_c_fn=lambda d: 20.0,
    )
    rule = TemporalAggregation(kind="annual_mean")
    result = aggregate_per_station(df, rule)
    assert result.name == "annual_mean"
    assert result["S1"] == pytest.approx(20.0)


def test_aggregate_annual_mean_multiple_stations():
    df = pd.concat(
        [
            _daily_series(
                "S1",
                0.0,
                0.0,
                "2020-01-01",
                "2020-12-31",
                temperature_c_fn=lambda d: 18.0,
            ),
            _daily_series(
                "S2",
                1.0,
                1.0,
                "2020-01-01",
                "2020-12-31",
                temperature_c_fn=lambda d: 22.0,
            ),
        ],
        ignore_index=True,
    )
    rule = TemporalAggregation(kind="annual_mean")
    result = aggregate_per_station(df, rule)
    assert result["S1"] == pytest.approx(18.0)
    assert result["S2"] == pytest.approx(22.0)


def test_aggregate_annual_mean_requires_temperature_column():
    df = pd.DataFrame({"station_id": ["S1"], "date": [pd.Timestamp("2020-01-01")]})
    rule = TemporalAggregation(kind="annual_mean")
    with pytest.raises(ValueError, match="temperature_c"):
        aggregate_per_station(df, rule)


# ---------------------------------------------------------------------------
# seasonal_mean
# ---------------------------------------------------------------------------


def test_aggregate_seasonal_mean_filters_to_selected_months():
    """Winter cold + summer warm → seasonal_mean over JJA picks up the warm half."""

    def temp_seasonal(d: pd.Timestamp) -> float:
        return 30.0 if 6 <= d.month <= 8 else 5.0

    df = _daily_series(
        "S1",
        0.0,
        0.0,
        "2020-01-01",
        "2020-12-31",
        temperature_c_fn=temp_seasonal,
    )
    rule = TemporalAggregation(kind="seasonal_mean", months=[6, 7, 8])
    result = aggregate_per_station(df, rule)
    assert result["S1"] == pytest.approx(30.0)
    assert result.name == "seasonal_mean__months_6_7_8"


def test_aggregate_seasonal_mean_empty_when_no_matching_months():
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-01-31")
    rule = TemporalAggregation(kind="seasonal_mean", months=[6])
    result = aggregate_per_station(df, rule)
    # Single station, no matching rows → NaN
    assert pd.isna(result["S1"])


# ---------------------------------------------------------------------------
# precip_percentile
# ---------------------------------------------------------------------------


def test_aggregate_precip_percentile_50th_equals_median():
    """50th percentile == median of a known distribution."""
    df = _daily_series(
        "S1",
        0.0,
        0.0,
        "2020-01-01",
        "2020-01-10",
        precipitation_mm_fn=lambda d: float(d.day),
    )
    rule = TemporalAggregation(kind="precip_percentile", percentile=50.0)
    result = aggregate_per_station(df, rule)
    # 10 days, precip = [1..10], median is 5.5
    assert result["S1"] == pytest.approx(5.5)
    assert result.name == "precip_percentile__p50"


def test_aggregate_precip_percentile_95th_picks_high_value():
    df = _daily_series(
        "S1",
        0.0,
        0.0,
        "2020-01-01",
        "2020-04-09",
        precipitation_mm_fn=lambda d: float(d.dayofyear),
    )
    rule = TemporalAggregation(kind="precip_percentile", percentile=95.0)
    result = aggregate_per_station(df, rule)
    # 100 daily values (1..100); 95th percentile = 95.05
    assert result["S1"] == pytest.approx(95.05, rel=1e-3)
    assert result.name == "precip_percentile__p95"


# ---------------------------------------------------------------------------
# Hazard kinds — deferred to #138d
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, kwargs",
    [
        ("growing_degree_days", {"base_temp_c": 10.0}),
        ("frost_days", {"threshold_c": 0.0}),
        ("heat_stress_days", {"threshold_c": 35.0}),
        ("spei", {"timescale_months": 3}),
    ],
)
def test_aggregate_hazard_kinds_raise_not_implemented(kind, kwargs):
    """Hazard kinds land in #138d (terraflow.hazard); engine framework
    surfaces a clear NotImplementedError pointing at the follow-up PR."""
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-12-31")
    rule = TemporalAggregation(kind=kind, **kwargs)
    with pytest.raises(NotImplementedError, match="138d"):
        aggregate_per_station(df, rule)


# ---------------------------------------------------------------------------
# compute_per_station_aggregations — the outer-product helper
# ---------------------------------------------------------------------------


def test_compute_per_station_aggregations_outer_product_shape():
    """3 rules × 2 scenarios → 6 columns per station."""
    df = pd.concat(
        [
            _daily_series(
                "S1",
                0.0,
                0.0,
                "2010-01-01",
                "2010-12-31",
                temperature_c_fn=lambda d: 18.0,
                precipitation_mm_fn=lambda d: 2.0,
            ),
            _daily_series(
                "S1",
                0.0,
                0.0,
                "2050-01-01",
                "2050-12-31",
                temperature_c_fn=lambda d: 22.0,
                precipitation_mm_fn=lambda d: 3.0,
            ),
            _daily_series(
                "S2",
                1.0,
                1.0,
                "2010-01-01",
                "2010-12-31",
                temperature_c_fn=lambda d: 15.0,
                precipitation_mm_fn=lambda d: 1.5,
            ),
            _daily_series(
                "S2",
                1.0,
                1.0,
                "2050-01-01",
                "2050-12-31",
                temperature_c_fn=lambda d: 19.0,
                precipitation_mm_fn=lambda d: 2.5,
            ),
        ],
        ignore_index=True,
    )
    rules = [
        TemporalAggregation(kind="annual_mean"),
        TemporalAggregation(kind="seasonal_mean", months=[6, 7, 8]),
        TemporalAggregation(kind="precip_percentile", percentile=50.0),
    ]
    scenarios = [
        Scenario(name="historical", period=[2010, 2010]),
        Scenario(name="ssp245", period=[2050, 2050]),
    ]

    out = compute_per_station_aggregations(df, rules, scenarios)

    assert out.shape == (2, 6)
    assert set(out.index) == {"S1", "S2"}
    expected_columns = {
        "annual_mean__historical",
        "annual_mean__ssp245",
        "seasonal_mean__months_6_7_8__historical",
        "seasonal_mean__months_6_7_8__ssp245",
        "precip_percentile__p50__historical",
        "precip_percentile__p50__ssp245",
    }
    assert set(out.columns) == expected_columns
    assert out.loc["S1", "annual_mean__historical"] == pytest.approx(18.0)
    assert out.loc["S1", "annual_mean__ssp245"] == pytest.approx(22.0)


def test_compute_per_station_aggregations_empty_when_no_rules():
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-12-31")
    rules: list[TemporalAggregation] = []
    scenarios = [Scenario(name="x", period=[2020, 2020])]
    out = compute_per_station_aggregations(df, rules, scenarios)
    assert out.empty


def test_compute_per_station_aggregations_empty_when_no_scenarios():
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-12-31")
    rules = [TemporalAggregation(kind="annual_mean")]
    scenarios: list[Scenario] = []
    out = compute_per_station_aggregations(df, rules, scenarios)
    assert out.empty


def test_compute_per_station_aggregations_handles_missing_station_in_scenario():
    """Station that has no rows in a scenario window → NaN for that column."""
    df = pd.concat(
        [
            _daily_series("S1", 0.0, 0.0, "2010-01-01", "2010-12-31"),
            _daily_series("S2", 1.0, 1.0, "2050-01-01", "2050-12-31"),
        ],
        ignore_index=True,
    )
    rules = [TemporalAggregation(kind="annual_mean")]
    scenarios = [
        Scenario(name="historical", period=[2010, 2010]),
        Scenario(name="ssp245", period=[2050, 2050]),
    ]
    out = compute_per_station_aggregations(df, rules, scenarios)
    # S1 has 2010 rows but no 2050 rows → NaN in ssp245 column
    assert np.isnan(out.loc["S1", "annual_mean__ssp245"])
    # S2 has 2050 rows but no 2010 rows → NaN in historical column
    assert np.isnan(out.loc["S2", "annual_mean__historical"])


# ---------------------------------------------------------------------------
# Label-collision safety (Codex P2 on PR #145)
# ---------------------------------------------------------------------------


def test_precip_percentile_label_preserves_precision():
    """percentile=99.99999 and percentile=100.0 must produce distinct labels."""
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-01-10")
    a = aggregate_per_station(df, TemporalAggregation(kind="precip_percentile", percentile=99.99999))
    b = aggregate_per_station(df, TemporalAggregation(kind="precip_percentile", percentile=100.0))
    assert a.name != b.name


def test_compute_per_station_aggregations_rejects_duplicate_labels():
    """Two rules that would generate the same column label raise ValueError."""
    df = _daily_series("S1", 0.0, 0.0, "2020-01-01", "2020-12-31")
    # Two identical annual_mean rules → identical labels under the same scenario.
    rules = [
        TemporalAggregation(kind="annual_mean"),
        TemporalAggregation(kind="annual_mean"),
    ]
    scenarios = [Scenario(name="historical", period=[2020, 2020])]
    with pytest.raises(ValueError, match="duplicate generated column label"):
        compute_per_station_aggregations(df, rules, scenarios)
