"""Tests for terraflow.hazard — climate-induced crop-hazard indicators (#138d)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from terraflow.config import TemporalAggregation
from terraflow.hazard import (
    frost_days,
    growing_degree_days,
    heat_stress_days,
    spei,
)
from terraflow.temporal import aggregate_per_station


def _daily(
    station_id: str,
    start: str,
    end: str,
    temperature_c_fn=lambda d: 15.0,
    precipitation_mm_fn=lambda d: 2.0,
) -> pd.DataFrame:
    dates = pd.date_range(start=start, end=end, freq="D")
    return pd.DataFrame(
        {
            "station_id": station_id,
            "lat": 0.0,
            "lon": 0.0,
            "date": dates,
            "temperature_c": [float(temperature_c_fn(d)) for d in dates],
            "precipitation_mm": [float(precipitation_mm_fn(d)) for d in dates],
        }
    )


# ---------------------------------------------------------------------------
# growing_degree_days
# ---------------------------------------------------------------------------


def test_gdd_constant_temperature_above_base():
    """N days at 20°C with base 10°C → GDD = N * (20 - 10). 2020 is a leap year (366 days)."""
    df = _daily("S1", "2020-01-01", "2020-12-31", temperature_c_fn=lambda d: 20.0)
    n_days = len(df)
    result = growing_degree_days(df, base_temp_c=10.0)
    assert result["S1"] == pytest.approx(n_days * 10.0)


def test_gdd_below_base_contributes_zero():
    """All-cold year → GDD = 0 (no negative contribution)."""
    df = _daily("S1", "2020-01-01", "2020-12-31", temperature_c_fn=lambda d: 5.0)
    result = growing_degree_days(df, base_temp_c=10.0)
    assert result["S1"] == pytest.approx(0.0)


def test_gdd_mixed_temperatures():
    """100 days at 20°C, 100 days at 0°C → 100 * (20 - 10) = 1000."""

    def temp(d: pd.Timestamp) -> float:
        return 20.0 if d.dayofyear <= 100 else 0.0

    df = _daily("S1", "2020-01-01", "2020-07-19", temperature_c_fn=temp)  # 201 days
    result = growing_degree_days(df, base_temp_c=10.0)
    assert result["S1"] == pytest.approx(1000.0)


def test_gdd_multiple_stations_distinct_totals():
    df = pd.concat(
        [
            _daily("S1", "2020-01-01", "2020-01-10", temperature_c_fn=lambda d: 20.0),
            _daily("S2", "2020-01-01", "2020-01-10", temperature_c_fn=lambda d: 15.0),
        ],
        ignore_index=True,
    )
    result = growing_degree_days(df, base_temp_c=10.0)
    assert result["S1"] == pytest.approx(10 * 10.0)
    assert result["S2"] == pytest.approx(10 * 5.0)


# ---------------------------------------------------------------------------
# frost_days
# ---------------------------------------------------------------------------


def test_frost_days_all_below_threshold():
    df = _daily("S1", "2020-01-01", "2020-01-31", temperature_c_fn=lambda d: -5.0)
    result = frost_days(df, threshold_c=0.0)
    assert result["S1"] == pytest.approx(31.0)


def test_frost_days_threshold_equality_counts():
    """Day with mean exactly == threshold counts as a frost day."""
    df = _daily("S1", "2020-01-01", "2020-01-10", temperature_c_fn=lambda d: 0.0)
    result = frost_days(df, threshold_c=0.0)
    assert result["S1"] == pytest.approx(10.0)


def test_frost_days_partial_year():
    """50 days at -1°C + 50 days at +5°C → 50 frost days."""

    def temp(d: pd.Timestamp) -> float:
        return -1.0 if d.dayofyear <= 50 else 5.0

    df = _daily("S1", "2020-01-01", "2020-04-09", temperature_c_fn=temp)  # 100 days
    result = frost_days(df, threshold_c=0.0)
    assert result["S1"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# heat_stress_days
# ---------------------------------------------------------------------------


def test_heat_stress_days_all_above_threshold():
    df = _daily("S1", "2020-06-01", "2020-08-31", temperature_c_fn=lambda d: 40.0)
    result = heat_stress_days(df, threshold_c=35.0)
    assert result["S1"] == pytest.approx(92.0)  # 92 days in JJA


def test_heat_stress_days_threshold_equality_counts():
    df = _daily("S1", "2020-07-01", "2020-07-10", temperature_c_fn=lambda d: 35.0)
    result = heat_stress_days(df, threshold_c=35.0)
    assert result["S1"] == pytest.approx(10.0)


def test_heat_stress_days_none_when_cold():
    df = _daily("S1", "2020-12-01", "2020-12-31", temperature_c_fn=lambda d: 20.0)
    result = heat_stress_days(df, threshold_c=35.0)
    assert result["S1"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# spei (simplified Thornthwaite)
# ---------------------------------------------------------------------------


def test_spei_returns_nan_for_empty_dataframe():
    df = pd.DataFrame(
        {
            "station_id": pd.Series([], dtype=str),
            "date": pd.Series([], dtype="datetime64[ns]"),
            "temperature_c": pd.Series([], dtype=float),
            "precipitation_mm": pd.Series([], dtype=float),
        }
    )
    result = spei(df, timescale_months=3)
    assert result.empty


def test_spei_returns_nan_when_window_too_short():
    """timescale_months=12 with only 6 months of data → NaN (no rolling window completes)."""
    df = _daily("S1", "2020-01-01", "2020-06-30")
    result = spei(df, timescale_months=12)
    assert pd.isna(result["S1"])


def test_spei_finite_for_constant_climate():
    """Constant daily climate still produces finite SPEI — monthly sums differ
    by calendar month length (28/30/31 days) which gives non-zero variance.
    This documents the simplification: zero-variance NaN behaviour requires
    truly constant *monthly* aggregates, which only occurs with degenerate
    monthly-input data (not constant daily-input data)."""
    df = _daily(
        "S1",
        "2020-01-01",
        "2022-12-31",
        temperature_c_fn=lambda d: 20.0,
        precipitation_mm_fn=lambda d: 2.0,
    )
    result = spei(df, timescale_months=3)
    assert not pd.isna(result["S1"])
    assert np.isfinite(result["S1"])


def test_spei_dry_anomaly_at_window_end_is_negative():
    """Anomalously dry final months → negative SPEI."""

    def precip(d: pd.Timestamp) -> float:
        # Wet baseline for first ~2 years, dry final 6 months.
        if d.year < 2022 or (d.year == 2022 and d.month <= 6):
            return 5.0
        return 0.5

    df = _daily(
        "S1",
        "2020-01-01",
        "2022-12-31",
        temperature_c_fn=lambda d: 18.0,
        precipitation_mm_fn=precip,
    )
    result = spei(df, timescale_months=3)
    assert result["S1"] < 0.0


def test_spei_wet_anomaly_at_window_end_is_positive():
    def precip(d: pd.Timestamp) -> float:
        if d.year < 2022 or (d.year == 2022 and d.month <= 6):
            return 1.0
        return 10.0

    df = _daily(
        "S1",
        "2020-01-01",
        "2022-12-31",
        temperature_c_fn=lambda d: 18.0,
        precipitation_mm_fn=precip,
    )
    result = spei(df, timescale_months=3)
    assert result["S1"] > 0.0


def test_spei_rejects_non_positive_timescale():
    df = _daily("S1", "2020-01-01", "2020-12-31")
    with pytest.raises(ValueError, match="timescale_months"):
        spei(df, timescale_months=0)


# ---------------------------------------------------------------------------
# Dispatcher integration via terraflow.temporal.aggregate_per_station
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule, df, expected_value, label_prefix",
    [
        (
            TemporalAggregation(kind="growing_degree_days", base_temp_c=10.0),
            _daily("S1", "2020-01-01", "2020-01-10", temperature_c_fn=lambda d: 20.0),
            100.0,  # 10 days * (20 - 10)
            "growing_degree_days",
        ),
        (
            TemporalAggregation(kind="frost_days", threshold_c=0.0),
            _daily("S1", "2020-01-01", "2020-01-10", temperature_c_fn=lambda d: -5.0),
            10.0,
            "frost_days",
        ),
        (
            TemporalAggregation(kind="heat_stress_days", threshold_c=35.0),
            _daily("S1", "2020-07-01", "2020-07-10", temperature_c_fn=lambda d: 40.0),
            10.0,
            "heat_stress_days",
        ),
    ],
)
def test_dispatcher_routes_hazard_kinds(rule, df, expected_value, label_prefix):
    result = aggregate_per_station(df, rule)
    assert result["S1"] == pytest.approx(expected_value)
    assert result.name.startswith(label_prefix)


def test_dispatcher_routes_spei():
    rule = TemporalAggregation(kind="spei", timescale_months=3)
    df = _daily(
        "S1",
        "2020-01-01",
        "2022-12-31",
        temperature_c_fn=lambda d: 18.0,
        precipitation_mm_fn=lambda d: 1.0 if d.month <= 6 else 10.0,
    )
    result = aggregate_per_station(df, rule)
    # Should be a finite float (sign depends on which months land at the window end).
    assert result.name == "spei__ts3"
    assert not np.isnan(result["S1"])
