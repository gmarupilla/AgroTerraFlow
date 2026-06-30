"""CMIP6 NetCDF scenario ingest (flagship #138c).

Reads a CMIP6 scenario NetCDF (typically a CF-compliant daily-or-monthly
``temperature_c`` or ``precipitation_mm`` cube) and samples it at station
coordinates, producing the long-format DataFrame shape that the
:mod:`terraflow.temporal` aggregation engine consumes.

The module is gated behind the optional ``[cmip6]`` install extra so the
default install stays lean::

    pip install "terraflow-agro[cmip6]"

Imports ``xarray`` and ``netCDF4`` lazily inside each callable so users
who only run the historical CSV path never pay the import cost.

Expected NetCDF shape (CF convention):
- Dimensions: ``time``, ``lat`` / ``latitude``, ``lon`` / ``longitude``.
- A single primary data variable (e.g. ``tas`` for near-surface
  temperature, ``pr`` for precipitation).
- Global attributes optionally containing ``variant_label``,
  ``source_id``, and ``experiment_id`` (folded into the run fingerprint
  by the pipeline in #138e).

The module deliberately does NOT depend on ``terraflow.config`` — it is
a thin adapter so the temporal engine can stay format-agnostic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

# Canonical input column names that downstream code (e.g. terraflow.temporal)
# expects on a long-format station time-series.
STATION_ID_COL = "station_id"
LAT_COL = "lat"
LON_COL = "lon"
DATE_COL = "date"


_CMIP6_METADATA_KEYS = (
    "variant_label",
    "source_id",
    "experiment_id",
    "institution_id",
    "table_id",
)


def _require_xarray() -> Any:
    """Lazy-import xarray with a helpful error when the extra is missing."""
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError(
            "CMIP6 NetCDF ingest requires the optional [cmip6] extra. "
            "Install with: pip install 'terraflow-agro[cmip6]'"
        ) from exc
    return xr


def _times_to_pandas(time_coord: Any) -> pd.DatetimeIndex:
    """Convert an xarray time coordinate to a pandas ``DatetimeIndex``.

    CMIP6 NetCDFs commonly use non-Gregorian calendars (``365_day``,
    ``noleap``, ``360_day``); xarray decodes those to ``cftime`` objects
    which ``pd.to_datetime`` rejects. Round-trip through ISO strings so
    both ``datetime64`` and ``cftime`` paths land in pandas.
    """
    arr = np.asarray(time_coord)
    if np.issubdtype(arr.dtype, np.datetime64):
        return pd.to_datetime(arr)
    return pd.to_datetime([t.isoformat() for t in arr])


def _resolve_lat_lon_names(ds: Any) -> tuple[str, str]:
    """Find the latitude and longitude dimensions on *ds*.

    CMIP6 datasets commonly use ``lat``/``lon`` but some sources use
    ``latitude``/``longitude``. We accept both.
    """
    candidates: list[tuple[str, str]] = [
        ("lat", "lon"),
        ("latitude", "longitude"),
    ]
    for lat_name, lon_name in candidates:
        if lat_name in ds.coords and lon_name in ds.coords:
            return lat_name, lon_name
    raise ValueError(
        "could not locate latitude/longitude coordinates on the dataset; "
        f"expected one of {candidates}; got coords {list(ds.coords)}"
    )


def _resolve_data_variable(ds: Any, variable_hint: str | None) -> str:
    """Pick the data variable to sample.

    If *variable_hint* is given, require an exact match. Otherwise pick
    the only data variable, or raise if the dataset is ambiguous.
    """
    data_vars = list(ds.data_vars)
    if variable_hint is not None:
        if variable_hint not in data_vars:
            raise ValueError(
                f"variable {variable_hint!r} not present in dataset; "
                f"available: {data_vars}"
            )
        return variable_hint
    if len(data_vars) == 1:
        return data_vars[0]
    raise ValueError(
        f"dataset has multiple data variables ({data_vars}); "
        "pass variable= to disambiguate"
    )


def cmip6_metadata(path: str | Path) -> dict[str, str]:
    """Extract CMIP6 provenance attributes from a NetCDF file.

    Returns a dict with keys ``sha256`` (file content hash),
    ``size_bytes``, and a subset of ``variant_label``, ``source_id``,
    ``experiment_id``, ``institution_id``, ``table_id`` when those
    global attributes are set on the file.

    The pipeline (in #138e) folds this dict into the run fingerprint
    so different CMIP6 variants of the same SSP scenario yield distinct
    cache directories.

    Parameters
    ----------
    path:
        Path to a CMIP6-conformant NetCDF file. The file is opened
        twice — once for SHA-256 hashing of bytes, once via xarray to
        read global attrs.
    """
    xr = _require_xarray()
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CMIP6 NetCDF file not found: {path}")

    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)

    metadata: dict[str, str] = {
        "sha256": digest.hexdigest(),
        "size_bytes": str(size),
    }
    with xr.open_dataset(path, decode_times=True) as ds:
        for key in _CMIP6_METADATA_KEYS:
            value = ds.attrs.get(key)
            if value is not None:
                metadata[key] = str(value)
    return metadata


def load_cmip6_scenario(
    path: str | Path,
    *,
    variable: str | None = None,
    period: tuple[int, int] | None = None,
) -> Any:
    """Open a CMIP6 NetCDF and return the requested DataArray (lazy).

    The result is an xarray DataArray indexed by ``time, lat, lon``
    (or ``time, latitude, longitude``). The underlying data is loaded
    lazily — pulling a station's full time-series is what materialises
    values from disk.

    Parameters
    ----------
    path:
        Path to a CMIP6 NetCDF file.
    variable:
        Data variable name to extract. Optional when the file contains
        exactly one variable.
    period:
        ``(year_min, year_max)`` inclusive year window. Slices the
        ``time`` axis. When ``None``, the full time range is kept.
    """
    xr = _require_xarray()
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CMIP6 NetCDF file not found: {path}")

    ds = xr.open_dataset(path, decode_times=True)
    var_name = _resolve_data_variable(ds, variable)
    da = ds[var_name]
    if period is not None:
        year_min, year_max = period
        if "time" not in da.dims:
            raise ValueError(
                f"variable {var_name!r} has no 'time' dimension; cannot apply period filter"
            )
        years = da["time"].dt.year.to_numpy()
        mask = (years >= year_min) & (years <= year_max)
        da = da.isel(time=mask)
    return da


def extract_station_timeseries(
    da: Any,
    stations: pd.DataFrame,
    *,
    output_variable: str,
) -> pd.DataFrame:
    """Sample a CMIP6 DataArray at each station's (lat, lon) coordinates.

    Uses nearest-neighbour selection on the lat/lon coordinates. The
    output is a long-format DataFrame in the shape consumed by
    :mod:`terraflow.temporal`.

    Parameters
    ----------
    da:
        An xarray DataArray with ``time, lat, lon`` dims (latitude /
        longitude variants tolerated).
    stations:
        DataFrame with at minimum ``station_id``, ``lat``, ``lon``.
    output_variable:
        Name of the climate variable column in the output (e.g.
        ``temperature_c`` or ``precipitation_mm``). Lets a caller line
        up the column with the schema expected by
        :func:`terraflow.temporal.aggregate_per_station`.

    Returns
    -------
    pd.DataFrame:
        Columns ``station_id, lat, lon, date, <output_variable>``. One
        row per (station, time) pair.
    """
    if STATION_ID_COL not in stations.columns:
        raise ValueError(
            f"stations DataFrame missing required column {STATION_ID_COL!r}; "
            f"got columns: {sorted(stations.columns)}"
        )
    for required in (LAT_COL, LON_COL):
        if required not in stations.columns:
            raise ValueError(
                f"stations DataFrame missing required column {required!r}; "
                f"got columns: {sorted(stations.columns)}"
            )

    lat_dim, lon_dim = _resolve_lat_lon_names(da)
    if "time" not in da.dims:
        raise ValueError(
            f"DataArray missing 'time' dimension; got dims {list(da.dims)}"
        )

    station_lats = stations[LAT_COL].to_numpy()
    station_lons = stations[LON_COL].to_numpy()
    station_ids = stations[STATION_ID_COL].to_numpy()

    # xarray supports vectorised nearest-neighbour selection by passing
    # DataArrays with a shared "station" dim — that returns a (time x
    # station) slab in one pass.
    xr = _require_xarray()
    sampled = da.sel(
        {
            lat_dim: xr.DataArray(station_lats, dims=("station",)),
            lon_dim: xr.DataArray(station_lons, dims=("station",)),
        },
        method="nearest",
    )

    # Materialise into a long-format DataFrame.
    times = _times_to_pandas(sampled["time"].to_numpy())
    arr = sampled.to_numpy()  # shape: (time, station)
    if arr.ndim == 1:
        # single-station case — xarray returns (time,)
        arr = arr.reshape(arr.shape[0], 1)

    n_time, n_stations = arr.shape
    out = pd.DataFrame(
        {
            STATION_ID_COL: np.repeat(station_ids, n_time),
            LAT_COL: np.repeat(station_lats, n_time),
            LON_COL: np.repeat(station_lons, n_time),
            DATE_COL: np.tile(times.to_numpy(), n_stations),
            output_variable: arr.T.reshape(-1),
        }
    )
    out[DATE_COL] = pd.to_datetime(out[DATE_COL])
    out[output_variable] = out[output_variable].astype(float)
    # Drop the station_dim coord — it confused round-tripping otherwise.
    return out.reset_index(drop=True)


def cmip6_to_station_timeseries(
    path: str | Path,
    stations: pd.DataFrame,
    *,
    variable: str | None = None,
    period: tuple[int, int] | None = None,
    output_variable: str,
) -> pd.DataFrame:
    """Convenience: open a CMIP6 NetCDF and return a station time-series.

    One-call wrapper around :func:`load_cmip6_scenario` +
    :func:`extract_station_timeseries`. Yields a DataFrame in the shape
    :mod:`terraflow.temporal` consumes.
    """
    da = load_cmip6_scenario(path, variable=variable, period=period)
    return extract_station_timeseries(da, stations, output_variable=output_variable)


__all__: list[str] = [
    "STATION_ID_COL",
    "LAT_COL",
    "LON_COL",
    "DATE_COL",
    "cmip6_metadata",
    "load_cmip6_scenario",
    "extract_station_timeseries",
    "cmip6_to_station_timeseries",
]


def _attrs_doc_only_to_silence_unused_imports() -> Mapping[str, str]:
    """Keep ``Mapping`` referenced so mypy does not flag the import."""
    return {}
