"""Multi-temporal climate aggregation engine (flagship #138b).

Takes a long-format station time-series DataFrame and produces one scalar
per station for each ``TemporalAggregation`` rule. Downstream callers
(the climate-impact pipeline path landing in #138e) interpolate those
per-station scalars onto cell centroids via the existing
``ClimateInterpolator``.

Expected input shape::

    station_id   lat       lon         date         temperature_c   precipitation_mm
    KS-001       38.95    -100.50      2010-01-01   -2.3            0.0
    KS-001       38.95    -100.50      2010-01-02   -1.1            1.4
    ...

Each ``aggregate_per_station`` call returns a ``pandas.Series`` indexed
by ``station_id`` with scalar float values. Stations with no data after
filtering yield ``NaN`` rather than raising — this lets downstream kriging
LOOCV handle missing stations cleanly.

Hazard-specific kinds (``growing_degree_days``, ``frost_days``,
``heat_stress_days``, ``spei``) raise ``NotImplementedError`` and point
at the hazard module that lands in #138d.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .config import Scenario, TemporalAggregation

# Column names enforced on the input long-format DataFrame.
STATION_ID_COL = "station_id"
DATE_COL = "date"
TEMPERATURE_COL = "temperature_c"
PRECIPITATION_COL = "precipitation_mm"

_HAZARD_KINDS: frozenset[str] = frozenset(
    {"growing_degree_days", "frost_days", "heat_stress_days", "spei"}
)


def filter_scenario(df: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """Return the subset of *df* whose ``date`` year falls in the scenario.

    The scenario period is closed-inclusive: ``[year_min, year_max]``.

    Parameters
    ----------
    df:
        Long-format station time-series. Must contain a ``date`` column
        parsable as ``datetime64[ns]``.
    scenario:
        A validated :class:`terraflow.config.Scenario` instance.

    Returns
    -------
    pd.DataFrame:
        Filtered rows. Empty DataFrames are returned unchanged when no
        rows match the scenario window.
    """
    if DATE_COL not in df.columns:
        raise ValueError(
            f"input DataFrame missing required column {DATE_COL!r}; "
            f"got columns: {sorted(df.columns)}"
        )
    dates = pd.to_datetime(df[DATE_COL])
    year_min, year_max = scenario.period
    mask = (dates.dt.year >= year_min) & (dates.dt.year <= year_max)
    return df.loc[mask].copy()


def aggregate_per_station(
    df: pd.DataFrame,
    rule: TemporalAggregation,
) -> pd.Series:
    """Apply one ``TemporalAggregation`` rule to a station time-series.

    Parameters
    ----------
    df:
        Long-format station time-series. Must contain ``station_id`` and
        ``date`` columns plus whatever variable column the rule needs.
    rule:
        A validated :class:`terraflow.config.TemporalAggregation` instance.

    Returns
    -------
    pd.Series:
        Indexed by unique ``station_id``. Float scalar per station. NaN
        when a station has no rows after filtering. Series ``name`` is set
        to a human-readable column identifier matching the rule's kind
        and parameters.
    """
    if STATION_ID_COL not in df.columns:
        raise ValueError(
            f"input DataFrame missing required column {STATION_ID_COL!r}; "
            f"got columns: {sorted(df.columns)}"
        )

    if rule.kind in _HAZARD_KINDS:
        raise NotImplementedError(
            f"temporal_aggregation kind={rule.kind!r} is implemented in "
            f"terraflow.hazard (#138d) — that module lands after the "
            f"engine framework in #138b."
        )

    if rule.kind == "annual_mean":
        return _aggregate_annual_mean(df).rename("annual_mean")

    if rule.kind == "seasonal_mean":
        # months is required for seasonal_mean per #138a model_validator.
        assert rule.months is not None, "seasonal_mean.months should be validated"
        result = _aggregate_seasonal_mean(df, months=rule.months)
        months_label = "_".join(str(m) for m in rule.months)
        return result.rename(f"seasonal_mean__months_{months_label}")

    if rule.kind == "precip_percentile":
        assert rule.percentile is not None
        result = _aggregate_precip_percentile(df, percentile=rule.percentile)
        # Render the percentile label without trailing zeros.
        pct_label = f"{rule.percentile:g}".replace(".", "p")
        return result.rename(f"precip_percentile__p{pct_label}")

    raise ValueError(f"unsupported temporal_aggregation kind: {rule.kind!r}")


def _require_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(
            f"input DataFrame missing required column {column!r}; "
            f"got columns: {sorted(df.columns)}"
        )


def _aggregate_annual_mean(df: pd.DataFrame) -> pd.Series:
    """Per-station mean of ``temperature_c`` across all rows.

    ``annual_mean`` here means the long-run average of the variable over
    the entire (already scenario-filtered) window. Stations with no rows
    yield NaN rather than raising.
    """
    _require_column(df, TEMPERATURE_COL)
    grouped = df.groupby(STATION_ID_COL)[TEMPERATURE_COL].mean()
    return grouped.astype(float)


def _aggregate_seasonal_mean(df: pd.DataFrame, months: list[int]) -> pd.Series:
    """Per-station mean of ``temperature_c`` over the selected calendar months.

    Stations that exist in *df* but have no rows in the selected months
    yield NaN rather than being dropped from the index.
    """
    _require_column(df, TEMPERATURE_COL)
    _require_column(df, DATE_COL)
    all_stations = pd.Index(df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL)
    dates = pd.to_datetime(df[DATE_COL])
    mask = dates.dt.month.isin(months)
    grouped = df.loc[mask].groupby(STATION_ID_COL)[TEMPERATURE_COL].mean().astype(float)
    return grouped.reindex(all_stations)


def _aggregate_precip_percentile(df: pd.DataFrame, percentile: float) -> pd.Series:
    """Per-station Nth percentile of daily precipitation."""
    _require_column(df, PRECIPITATION_COL)
    fraction = percentile / 100.0
    grouped = df.groupby(STATION_ID_COL)[PRECIPITATION_COL]
    return grouped.quantile(fraction).astype(float)


def compute_per_station_aggregations(
    df: pd.DataFrame,
    rules: list[TemporalAggregation],
    scenarios: list[Scenario],
) -> pd.DataFrame:
    """Outer-product of *rules* × *scenarios* → per-station, per-(rule,scenario) scalars.

    Result columns are ``<rule_label>__<scenario_name>``. The index is the
    union of station_ids observed in *df*. Hazard-kind rules (handled in
    #138d) trigger :class:`NotImplementedError` from the dispatcher.

    Returns an empty DataFrame when *rules* or *scenarios* is empty —
    this matches the v0.4.x single-period behaviour.
    """
    if not rules or not scenarios:
        return pd.DataFrame()

    columns: dict[str, pd.Series] = {}
    all_station_ids = pd.Index(
        df[STATION_ID_COL].dropna().unique(), name=STATION_ID_COL
    )

    for scenario in scenarios:
        scenario_df = filter_scenario(df, scenario)
        for rule in rules:
            series = aggregate_per_station(scenario_df, rule)
            column_label = f"{series.name}__{scenario.name}"
            # Re-index against the union of stations so each column has the
            # same index. Missing stations end up NaN.
            columns[column_label] = series.reindex(all_station_ids)

    out = pd.DataFrame(columns, index=all_station_ids)
    out.index.name = STATION_ID_COL
    return out


__all__: list[Any] = [
    "STATION_ID_COL",
    "DATE_COL",
    "TEMPERATURE_COL",
    "PRECIPITATION_COL",
    "aggregate_per_station",
    "compute_per_station_aggregations",
    "filter_scenario",
]
