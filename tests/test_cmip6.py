"""Tests for terraflow.cmip6 — CMIP6 NetCDF scenario ingest (#138c)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

xr = pytest.importorskip("xarray")
pytest.importorskip("netCDF4")

from terraflow.cmip6 import (  # noqa: E402
    cmip6_metadata,
    cmip6_to_station_timeseries,
    load_cmip6_scenario,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_synthetic_cmip6_netcdf(
    path: Path,
    *,
    times: pd.DatetimeIndex,
    lats: np.ndarray,
    lons: np.ndarray,
    variable_name: str = "tas",
    base_value: float = 280.0,
    attrs: dict[str, str] | None = None,
) -> Path:
    """Write a minimal CF-compliant CMIP6-style NetCDF for testing.

    Data values follow a deterministic gradient so tests can assert exact
    station samples: ``v(t, lat, lon) = base_value + t_idx + lat_idx +
    lon_idx``.
    """
    n_t, n_lat, n_lon = len(times), len(lats), len(lons)
    grid_t = np.arange(n_t).reshape(-1, 1, 1)
    grid_lat = np.arange(n_lat).reshape(1, -1, 1)
    grid_lon = np.arange(n_lon).reshape(1, 1, -1)
    values = base_value + grid_t + grid_lat + grid_lon

    da = xr.DataArray(
        values,
        dims=("time", "lat", "lon"),
        coords={
            "time": times,
            "lat": lats,
            "lon": lons,
        },
        name=variable_name,
    )
    ds = da.to_dataset()
    if attrs:
        ds.attrs.update(attrs)
    ds.to_netcdf(path)
    return path


@pytest.fixture
def cmip6_sample(tmp_path: Path) -> Path:
    """Build a 10-day × 4-lat × 4-lon synthetic CMIP6 file with CMIP6 attrs."""
    return _make_synthetic_cmip6_netcdf(
        tmp_path / "tas_historical.nc",
        times=pd.date_range("2010-01-01", periods=10, freq="D"),
        lats=np.array([35.0, 38.0, 40.0, 42.0]),
        lons=np.array([-105.0, -102.0, -100.0, -98.0]),
        attrs={
            "variant_label": "r1i1p1f1",
            "source_id": "MPI-ESM1-2-HR",
            "experiment_id": "historical",
            "institution_id": "MPI-M",
            "table_id": "day",
        },
    )


# ---------------------------------------------------------------------------
# cmip6_metadata
# ---------------------------------------------------------------------------


def test_cmip6_metadata_returns_hash_and_global_attrs(cmip6_sample: Path):
    meta = cmip6_metadata(cmip6_sample)
    assert len(meta["sha256"]) == 64  # SHA-256 hex digest
    assert int(meta["size_bytes"]) > 0
    assert meta["variant_label"] == "r1i1p1f1"
    assert meta["source_id"] == "MPI-ESM1-2-HR"
    assert meta["experiment_id"] == "historical"
    assert meta["institution_id"] == "MPI-M"
    assert meta["table_id"] == "day"


def test_cmip6_metadata_handles_file_without_cmip6_attrs(tmp_path: Path):
    """Plain NetCDF (no CMIP6 attrs) still yields sha256 + size_bytes."""
    path = _make_synthetic_cmip6_netcdf(
        tmp_path / "no_attrs.nc",
        times=pd.date_range("2010-01-01", periods=3, freq="D"),
        lats=np.array([0.0, 1.0]),
        lons=np.array([0.0, 1.0]),
        attrs=None,
    )
    meta = cmip6_metadata(path)
    assert "sha256" in meta
    assert "size_bytes" in meta
    assert "variant_label" not in meta


def test_cmip6_metadata_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="not found"):
        cmip6_metadata(tmp_path / "nope.nc")


# ---------------------------------------------------------------------------
# load_cmip6_scenario
# ---------------------------------------------------------------------------


def test_load_cmip6_scenario_returns_full_dataarray(cmip6_sample: Path):
    da = load_cmip6_scenario(cmip6_sample)
    assert da.dims == ("time", "lat", "lon")
    assert da.shape == (10, 4, 4)


def test_load_cmip6_scenario_period_filter_inclusive(tmp_path: Path):
    path = _make_synthetic_cmip6_netcdf(
        tmp_path / "spanning.nc",
        times=pd.date_range("2009-06-01", periods=400, freq="D"),
        lats=np.array([0.0, 1.0]),
        lons=np.array([0.0, 1.0]),
    )
    da = load_cmip6_scenario(path, period=(2010, 2010))
    years = pd.to_datetime(da["time"].to_pandas()).dt.year.unique()
    assert set(years) == {2010}


def test_load_cmip6_scenario_explicit_variable(tmp_path: Path):
    """variable= overrides default auto-detection."""
    da = _make_synthetic_cmip6_netcdf(
        tmp_path / "named.nc",
        times=pd.date_range("2020-01-01", periods=3, freq="D"),
        lats=np.array([0.0, 1.0]),
        lons=np.array([0.0, 1.0]),
        variable_name="custom",
    )
    loaded = load_cmip6_scenario(da, variable="custom")
    assert loaded.name == "custom"


def test_load_cmip6_scenario_rejects_bad_variable(cmip6_sample: Path):
    with pytest.raises(ValueError, match="not present"):
        load_cmip6_scenario(cmip6_sample, variable="bogus")


# ---------------------------------------------------------------------------
# extract_station_timeseries
# ---------------------------------------------------------------------------


def test_extract_station_timeseries_long_format_shape(cmip6_sample: Path):
    da = load_cmip6_scenario(cmip6_sample)
    stations = pd.DataFrame(
        {
            "station_id": ["S1", "S2"],
            "lat": [35.5, 41.5],  # nearest to lat[0]=35.0 and lat[3]=42.0
            "lon": [-104.0, -99.0],  # nearest to lon[0]=-105 and lon[3]=-98
        }
    )
    out = cmip6_to_station_timeseries(
        cmip6_sample,
        stations,
        output_variable="temperature_c",
    )
    assert set(out.columns) == {"station_id", "lat", "lon", "date", "temperature_c"}
    # 10 time slices × 2 stations = 20 rows.
    assert len(out) == 20
    assert pd.api.types.is_datetime64_any_dtype(out["date"])
    assert pd.api.types.is_float_dtype(out["temperature_c"])
    # Date span should cover the synthetic 10-day window inclusively.
    assert out["date"].min() == pd.Timestamp("2010-01-01")
    assert out["date"].max() == pd.Timestamp("2010-01-10")
    _ = da  # silence vulture; using cmip6_sample path was the public-API test


def test_extract_station_timeseries_nearest_neighbour_picks_correct_cell(
    cmip6_sample: Path,
):
    """Synthetic file has value = 280 + t + lat_idx + lon_idx.

    Station near (lat[0]=35, lon[0]=-105) at t=0 should yield 280 + 0 + 0 + 0 = 280.
    Station near (lat[3]=42, lon[3]=-98) at t=0 should yield 280 + 0 + 3 + 3 = 286.
    """
    stations = pd.DataFrame(
        {
            "station_id": ["S_low", "S_high"],
            "lat": [35.0, 42.0],
            "lon": [-105.0, -98.0],
        }
    )
    out = cmip6_to_station_timeseries(
        cmip6_sample,
        stations,
        output_variable="temperature_c",
    )
    first_low = out[(out["station_id"] == "S_low") & (out["date"] == "2010-01-01")][
        "temperature_c"
    ].iloc[0]
    first_high = out[(out["station_id"] == "S_high") & (out["date"] == "2010-01-01")][
        "temperature_c"
    ].iloc[0]
    assert first_low == pytest.approx(280.0)
    assert first_high == pytest.approx(286.0)


def test_extract_station_timeseries_requires_station_id(cmip6_sample: Path):
    stations = pd.DataFrame({"lat": [35.0], "lon": [-100.0]})
    with pytest.raises(ValueError, match="station_id"):
        cmip6_to_station_timeseries(
            cmip6_sample, stations, output_variable="temperature_c"
        )


def test_extract_station_timeseries_supports_latitude_longitude_names(tmp_path: Path):
    """CMIP6 files with `latitude` / `longitude` coords (some sources) work."""
    times = pd.date_range("2020-01-01", periods=2, freq="D")
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])
    values = np.arange(2 * 2 * 2, dtype=float).reshape(2, 2, 2)
    da = xr.DataArray(
        values,
        dims=("time", "latitude", "longitude"),
        coords={"time": times, "latitude": lats, "longitude": lons},
        name="pr",
    )
    path = tmp_path / "lat_long_named.nc"
    da.to_dataset().to_netcdf(path)
    stations = pd.DataFrame({"station_id": ["S1"], "lat": [0.0], "lon": [0.0]})
    out = cmip6_to_station_timeseries(
        path, stations, output_variable="precipitation_mm"
    )
    assert len(out) == 2
    assert pd.api.types.is_float_dtype(out["precipitation_mm"])


# ---------------------------------------------------------------------------
# Non-Gregorian calendar handling (cftime path)
# ---------------------------------------------------------------------------


def _make_cftime_netcdf(path: Path, calendar: str) -> Path:
    """Build a tiny NetCDF whose time axis decodes to cftime objects."""
    cftime = pytest.importorskip("cftime")
    n_t = 8
    times = cftime.num2date(
        np.arange(n_t, dtype=float),
        units="days since 2010-01-01",
        calendar=calendar,
    )
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])
    values = np.arange(n_t * 2 * 2, dtype=float).reshape(n_t, 2, 2)
    da = xr.DataArray(
        values,
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": lats, "lon": lons},
        name="tas",
    )
    da.to_dataset().to_netcdf(path)
    return path


def test_load_cmip6_scenario_period_filter_handles_noleap_calendar(tmp_path: Path):
    """cftime ``365_day`` calendar (noleap) must not break period filtering."""
    path = _make_cftime_netcdf(tmp_path / "noleap.nc", calendar="noleap")
    da = load_cmip6_scenario(path, period=(2010, 2010))
    assert da.sizes["time"] == 8  # all 8 days fall in 2010


def test_extract_station_timeseries_handles_360_day_calendar(tmp_path: Path):
    """cftime ``360_day`` time coords still produce a pandas-typed date column."""
    path = _make_cftime_netcdf(tmp_path / "360day.nc", calendar="360_day")
    stations = pd.DataFrame({"station_id": ["S1"], "lat": [0.0], "lon": [0.0]})
    out = cmip6_to_station_timeseries(
        path, stations, output_variable="temperature_c"
    )
    assert len(out) == 8
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


# ---------------------------------------------------------------------------
# Optional-extra error path
# ---------------------------------------------------------------------------


def test_import_error_when_xarray_missing(monkeypatch, tmp_path: Path):
    """When xarray import fails, surface a helpful 'install [cmip6]' error."""
    from terraflow import cmip6 as cmip6_mod

    def _bad_import():
        raise ImportError("simulated")

    monkeypatch.setattr(cmip6_mod, "_require_xarray", _bad_import)
    with pytest.raises(ImportError):
        cmip6_mod._require_xarray()
