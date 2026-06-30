"""Climate-impact pipeline orchestration (flagship #138e).

Glues together the schema (#138a), aggregation engine (#138b),
CMIP6 ingest (#138c), and hazard module (#138d) into one entry point
that produces scenario-tagged cell-level columns from a long-format
station time-series CSV.

The function lives in its own module so the historical single-period
``run_pipeline`` flow stays unchanged. Downstream tools merge the new
``climate_features.parquet`` artifact with the existing
``features.parquet`` on ``cell_id``.

Usage::

    from terraflow.climate_impact import run_climate_impact_features
    from terraflow.config import load_config

    cfg = load_config("config.yml")
    out_path = run_climate_impact_features(cfg, run_dir, cells_df)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .climate import ClimateInterpolator
from .config import PipelineConfig
from .temporal import (
    DATE_COL,
    PRECIPITATION_COL,
    STATION_ID_COL,
    TEMPERATURE_COL,
    compute_per_station_aggregations,
)
from .utils import logger

# Required columns on the long-format station time-series CSV.
_REQUIRED_TIMESERIES_COLS: frozenset[str] = frozenset(
    {STATION_ID_COL, "lat", "lon", DATE_COL, TEMPERATURE_COL, PRECIPITATION_COL}
)


def _validate_timeseries_schema(df: pd.DataFrame) -> None:
    """Reject DataFrames missing any required column.

    The contract is enforced strictly at the boundary so kriging and the
    aggregation engine can rely on well-typed inputs downstream.
    """
    missing = _REQUIRED_TIMESERIES_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"climate timeseries CSV missing required column(s): {sorted(missing)}; "
            f"got columns {sorted(df.columns)}. The schema is: station_id, "
            "lat, lon, date, temperature_c, precipitation_mm."
        )


def load_timeseries_csv(path: str | Path) -> pd.DataFrame:
    """Load and validate a long-format station time-series CSV.

    Parameters
    ----------
    path:
        Path to the CSV file. Must contain columns ``station_id``, ``lat``,
        ``lon``, ``date``, ``temperature_c``, ``precipitation_mm``.

    Returns
    -------
    pd.DataFrame:
        Validated DataFrame with ``date`` parsed as ``datetime64[ns]``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"climate timeseries CSV not found: {path}")
    df = pd.read_csv(path)
    _validate_timeseries_schema(df)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    df[TEMPERATURE_COL] = df[TEMPERATURE_COL].astype(float)
    df[PRECIPITATION_COL] = df[PRECIPITATION_COL].astype(float)
    return df


def _stations_with_aggregations(
    timeseries_df: pd.DataFrame, cfg: PipelineConfig
) -> pd.DataFrame:
    """Return per-station scenario × rule scalars joined with station lat/lon.

    Result columns: ``station_id, lat, lon, <rule_label>__<scenario_name>, ...``.
    Stations missing from any scenario window become NaN in the relevant column
    rather than being dropped from the index.
    """
    aggregations = compute_per_station_aggregations(
        timeseries_df,
        rules=cfg.climate.temporal_aggregations,
        scenarios=cfg.climate.scenarios,
    )
    if aggregations.empty:
        # No rules or no scenarios — nothing to do.
        return pd.DataFrame()

    # Station lat/lon is a per-station property: take the first observation.
    coords = timeseries_df.groupby(STATION_ID_COL)[["lat", "lon"]].first().reset_index()
    return coords.merge(
        aggregations.reset_index(),
        on=STATION_ID_COL,
        how="inner",
    )


def _interpolate_column_to_cells(
    stations_df: pd.DataFrame,
    column: str,
    cell_lats,
    cell_lons,
    cfg: PipelineConfig,
) -> pd.Series:
    """Kriging-interpolate one per-station derived value onto cell centroids.

    Drops stations whose value is NaN before interpolation (e.g. when a
    station was missing from a scenario window).
    """
    subset = stations_df[[STATION_ID_COL, "lat", "lon", column]].dropna(subset=[column])
    if subset.empty:
        # No usable stations — return NaN column.
        return pd.Series([float("nan")] * len(cell_lats), name=column)

    # ClimateInterpolator expects columns ``lat``, ``lon``, and the variable
    # name in the DataFrame; pass our derived column verbatim.
    interpolator = ClimateInterpolator(
        climate_df=subset.rename(columns={column: column}),
        strategy="spatial",
        interpolation_method=cfg.climate.interpolation_method,
        variogram_mode=cfg.climate.variogram_mode,
        fallback_to_mean=cfg.climate.fallback_to_mean,
    )
    interp_df = interpolator.interpolate(cell_lats, cell_lons)
    if column not in interp_df.columns:
        # ClimateInterpolator silently dropped the variable — surface it.
        raise RuntimeError(
            f"interpolation returned no column {column!r}; "
            f"got columns {sorted(interp_df.columns)}"
        )
    return interp_df[column]


def run_climate_impact_features(
    cfg: PipelineConfig,
    run_dir: Path,
    cells_df: pd.DataFrame,
) -> Path:
    """Compute scenario × rule cell-level derived columns and write the artifact.

    Parameters
    ----------
    cfg:
        Validated pipeline configuration with non-empty
        ``climate.temporal_aggregations`` and ``climate.scenarios``.
    run_dir:
        Run directory under ``<output_dir>/runs/<run_fingerprint>/``.
    cells_df:
        Cell centroid DataFrame with at minimum ``cell_id``, ``lat``, ``lon``.

    Returns
    -------
    Path:
        Absolute path to the written ``climate_features.parquet``.

    Raises
    ------
    ValueError:
        If the config lacks ``timeseries_csv`` or the CSV schema is invalid.
    FileNotFoundError:
        If the timeseries CSV does not exist.
    """
    if not cfg.climate.temporal_aggregations or not cfg.climate.scenarios:
        raise ValueError(
            "run_climate_impact_features called with empty "
            "temporal_aggregations or scenarios — nothing to compute."
        )
    if not cfg.climate.timeseries_csv:
        raise ValueError(
            "run_climate_impact_features requires climate.timeseries_csv "
            "(long-format station daily data)."
        )

    logger.info(
        f"Climate-impact features: {len(cfg.climate.temporal_aggregations)} rules "
        f"× {len(cfg.climate.scenarios)} scenarios → "
        f"{len(cfg.climate.temporal_aggregations) * len(cfg.climate.scenarios)} derived columns"
    )

    timeseries_df = load_timeseries_csv(cfg.climate.timeseries_csv)
    stations_df = _stations_with_aggregations(timeseries_df, cfg)
    if stations_df.empty:
        raise RuntimeError(
            "no per-station aggregations produced; "
            "check that the timeseries CSV covers the configured scenario windows."
        )

    derived_columns = [
        c for c in stations_df.columns if c not in (STATION_ID_COL, "lat", "lon")
    ]

    cell_lats = cells_df["lat"].to_numpy()
    cell_lons = cells_df["lon"].to_numpy()

    result = pd.DataFrame({"cell_id": cells_df["cell_id"].to_numpy()})
    for column in derived_columns:
        result[column] = _interpolate_column_to_cells(
            stations_df, column, cell_lats, cell_lons, cfg
        ).to_numpy()

    out_path = run_dir / "climate_features.parquet"
    result.to_parquet(out_path, index=False)
    logger.info(
        f"Wrote climate_features.parquet ({len(derived_columns)} columns) → {out_path}"
    )
    return out_path


__all__ = [
    "load_timeseries_csv",
    "run_climate_impact_features",
]
