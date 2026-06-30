"""Climate-induced crop-hazard indicators (flagship #138d).

Implements the four hazard kinds dispatched from :mod:`terraflow.temporal`:

- ``growing_degree_days``: GDD accumulation above a crop-specific base
  temperature. ``GDD = sum_d max(0, daily_mean_temp - base_temp_c)``.
- ``frost_days``: count of days with daily mean temperature at or below
  a threshold (typically 0 °C).
- ``heat_stress_days``: count of days with daily mean temperature at or
  above a threshold (typically 30-35 °C for major C3 crops).
- ``spei``: Standardised Precipitation-Evapotranspiration Index using a
  simplified Thornthwaite PET. Returns the SPEI value at the final month
  of the input window.

All four functions take the same long-format station time-series
DataFrame shape used elsewhere in the climate-impact pipeline
(``station_id``, ``date``, ``temperature_c``, ``precipitation_mm``) and
return a :class:`pandas.Series` indexed by ``station_id`` with float
scalar values. Stations with no rows after upstream scenario filtering
yield ``NaN`` rather than raising — consistent with the rest of the
engine.

**Simplified-SPEI caveats** (documented for reviewers):

1. PET is computed via Thornthwaite (monthly temperature only); no
   daylight-hour or latitude correction (assumes 12 h days, 30-day
   months). Standard SPEI implementations (e.g. R's ``SPEI`` package)
   add a latitude-aware daylight factor.
2. The annual heat index ``I`` is fitted on each station's own monthly
   means within the input window. Standard practice fits ``I`` on a
   long-run climatology.
3. Standardisation is a per-station z-score of the rolling
   ``timescale_months`` water-balance sum. Standard SPEI uses a fitted
   log-logistic distribution; the simplification preserves sign and
   relative ordering but not the canonical CDF mapping.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .temporal import (
    DATE_COL,
    PRECIPITATION_COL,
    STATION_ID_COL,
    TEMPERATURE_COL,
)


def _require_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(
            f"input DataFrame missing required column {column!r}; "
            f"got columns: {sorted(df.columns)}"
        )


def growing_degree_days(df: pd.DataFrame, base_temp_c: float) -> pd.Series:
    """Per-station GDD accumulation above *base_temp_c*.

    GDD for one day = ``max(0, daily_mean_temp_c - base_temp_c)``. The
    per-station total is the sum across all rows in the (already
    scenario-filtered) DataFrame.

    Parameters
    ----------
    df:
        Long-format station time-series. Must contain ``station_id`` and
        ``temperature_c`` columns.
    base_temp_c:
        Crop-specific base temperature in °C (e.g. 10 °C for maize,
        4 °C for winter wheat).

    Returns
    -------
    pd.Series:
        Indexed by ``station_id``; float scalar GDD total per station.
        Stations missing from *df* yield NaN.
    """
    _require_column(df, STATION_ID_COL)
    _require_column(df, TEMPERATURE_COL)
    all_stations = pd.Index(df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL)
    contribution = (df[TEMPERATURE_COL] - base_temp_c).clip(lower=0.0)
    contribution_df = df.assign(_gdd_contribution=contribution)
    grouped = (
        contribution_df.groupby(STATION_ID_COL)["_gdd_contribution"].sum().astype(float)
    )
    return grouped.reindex(all_stations)


def frost_days(df: pd.DataFrame, threshold_c: float) -> pd.Series:
    """Per-station count of days with mean temperature ≤ *threshold_c*.

    A daily mean of exactly ``threshold_c`` counts as a frost day —
    matches the WMO convention for ETCCDI ``FD0`` when threshold = 0 °C.
    """
    _require_column(df, STATION_ID_COL)
    _require_column(df, TEMPERATURE_COL)
    all_stations = pd.Index(df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL)
    flags = (df[TEMPERATURE_COL] <= threshold_c).astype(int)
    counted = df.assign(_frost_flag=flags)
    grouped = counted.groupby(STATION_ID_COL)["_frost_flag"].sum().astype(float)
    return grouped.reindex(all_stations)


def heat_stress_days(df: pd.DataFrame, threshold_c: float) -> pd.Series:
    """Per-station count of days with mean temperature ≥ *threshold_c*.

    A daily mean of exactly ``threshold_c`` counts as a heat-stress day —
    consistent with the WMO ETCCDI ``TX35`` convention when the threshold
    matches.
    """
    _require_column(df, STATION_ID_COL)
    _require_column(df, TEMPERATURE_COL)
    all_stations = pd.Index(df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL)
    flags = (df[TEMPERATURE_COL] >= threshold_c).astype(int)
    counted = df.assign(_heat_flag=flags)
    grouped = counted.groupby(STATION_ID_COL)["_heat_flag"].sum().astype(float)
    return grouped.reindex(all_stations)


def _thornthwaite_pet_monthly(monthly_temp_c: pd.Series) -> pd.Series:
    """Simplified Thornthwaite PET (mm/month) from monthly mean temperature.

    PET_m = 16 * (10 * T_m / I)^a

    where ``I`` is the annual heat index fitted on the station's own
    monthly means and ``a`` is the standard Thornthwaite polynomial of
    ``I``. PET is zero for months with mean temperature at or below 0 °C.
    No daylight-length correction (assumes 12 h days, 30-day months).

    Parameters
    ----------
    monthly_temp_c:
        Series indexed by month-period (``PeriodIndex[freq="M"]``) with
        monthly mean temperatures in °C.

    Returns
    -------
    pd.Series:
        PET in mm/month, indexed by the same months. NaN where the input
        is NaN.
    """
    positive = monthly_temp_c.where(monthly_temp_c > 0.0, other=np.nan)
    heat_contribution = (positive / 5.0).pow(1.514)
    annual_heat_index = heat_contribution.sum(skipna=True)
    if annual_heat_index <= 0 or np.isnan(annual_heat_index):
        return pd.Series(0.0, index=monthly_temp_c.index, dtype=float)
    a_exponent = (
        6.75e-7 * annual_heat_index**3
        - 7.71e-5 * annual_heat_index**2
        + 1.7912e-2 * annual_heat_index
        + 0.49239
    )
    base = (10.0 * positive / annual_heat_index).pow(a_exponent)
    pet = 16.0 * base
    return pet.fillna(0.0).astype(float)


def _spei_one_station(daily: pd.DataFrame, timescale_months: int) -> float:
    """Compute one station's SPEI value at the final month of the window."""
    if daily.empty:
        return float("nan")
    dates = pd.to_datetime(daily[DATE_COL])
    grouped = daily.assign(_month=dates.dt.to_period("M")).groupby("_month")
    monthly_temp = grouped[TEMPERATURE_COL].mean()
    monthly_precip = grouped[PRECIPITATION_COL].sum()
    if monthly_temp.empty:
        return float("nan")

    monthly_pet = _thornthwaite_pet_monthly(monthly_temp)
    water_balance = monthly_precip.subtract(monthly_pet, fill_value=0.0)

    rolling = water_balance.rolling(
        window=timescale_months, min_periods=timescale_months
    ).sum()
    valid = rolling.dropna()
    if valid.empty:
        return float("nan")
    mean = float(valid.mean())
    std = float(valid.std(ddof=0))
    final = float(rolling.iloc[-1])
    if std == 0 or np.isnan(std):
        return float("nan")
    return (final - mean) / std


def spei(df: pd.DataFrame, timescale_months: int) -> pd.Series:
    """Per-station simplified SPEI at the final month of the input window.

    Drought index combining precipitation and evapotranspiration into a
    standardised metric. Values near zero indicate normal conditions;
    negative values indicate drought (more negative = more severe);
    positive values indicate wet anomalies. The scalar returned is the
    SPEI at the **last** month covered by the input data, computed over
    a rolling *timescale_months* window.

    See module docstring for the documented simplifications relative to
    the canonical R-package SPEI implementation.
    """
    _require_column(df, STATION_ID_COL)
    _require_column(df, TEMPERATURE_COL)
    _require_column(df, PRECIPITATION_COL)
    _require_column(df, DATE_COL)
    if timescale_months <= 0:
        raise ValueError(f"timescale_months must be positive, got {timescale_months}")
    all_stations = pd.Index(df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL)
    results = {
        station: _spei_one_station(group, timescale_months)
        for station, group in df.groupby(STATION_ID_COL, sort=False)
    }
    series = pd.Series(results, dtype=float)
    series.index.name = STATION_ID_COL
    return series.reindex(all_stations)


__all__ = [
    "growing_degree_days",
    "frost_days",
    "heat_stress_days",
    "spei",
]
