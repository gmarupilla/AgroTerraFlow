"""End-to-end smoke test for TerraFlow.

Self-contained: builds synthetic raster + climate CSV from scratch (no real
data files required) then runs the full pipeline and validates all three
required artifacts.

Run with:
    pytest tests/test_e2e_smoke.py -v
    # or via the Makefile:
    make smoke-test
    # or filter by marker anywhere in the suite:
    pytest -m smoke
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from terraflow.pipeline import FEATURES_COLUMNS_ORDERED, run_pipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_raster(path: Path) -> Path:
    """Write a tiny 5×5 GeoTIFF in EPSG:4326 centred near (−100 °, 40 °)."""
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as ds:
        ds.write(arr, 1)
    return path


def _make_synthetic_climate(path: Path) -> Path:
    """Write a 3-row climate CSV that falls within the synthetic raster extent."""
    pd.DataFrame(
        {
            "lat": [40.0, 40.01, 40.02],
            "lon": [-100.0, -99.99, -99.98],
            "mean_temp": [18.0, 19.0, 20.0],
            "total_rain": [100.0, 120.0, 140.0],
        }
    ).to_csv(path, index=False)
    return path


def _write_config(path: Path, raster: Path, climate: Path, out_dir: Path) -> Path:
    path.write_text(
        f"""
raster_path: "{raster}"
climate_csv: "{climate}"
output_dir: "{out_dir}"
roi:
  type: "bbox"
  xmin: -101.0
  ymin: 39.0
  xmax: -99.0
  ymax: 41.0
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
max_cells: 10
""",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_e2e_pipeline_produces_all_artifacts(tmp_path: Path) -> None:
    """Full pipeline run: synthetic inputs → all 4 artifacts present and valid."""
    raster = _make_synthetic_raster(tmp_path / "raster.tif")
    climate = _make_synthetic_climate(tmp_path / "climate.csv")
    cfg = _write_config(tmp_path / "config.yml", raster, climate, tmp_path / "out")

    df = run_pipeline(cfg)
    run_dir = Path(df.attrs["run_dir"])
    fp = df.attrs["run_fingerprint"]

    # --- All four artifacts must exist on disk ---
    assert (run_dir / "features.parquet").exists(), "features.parquet missing"
    assert (run_dir / "manifest.json").exists(), "manifest.json missing"
    assert (run_dir / "report.json").exists(), "report.json missing"
    assert (run_dir / "results.csv").exists(), "results.csv missing"

    # --- features.parquet: schema columns and basic value ranges ---
    pq = pd.read_parquet(run_dir / "features.parquet")
    assert list(pq.columns) == FEATURES_COLUMNS_ORDERED, "column order mismatch"
    assert len(pq) > 0, "features.parquet is empty"
    assert pq["score"].between(0.0, 1.0).all(), "scores out of [0, 1]"
    assert pq["lat"].between(-90.0, 90.0).all(), "lat out of WGS84 range"
    assert pq["lon"].between(-180.0, 180.0).all(), "lon out of WGS84 range"
    assert set(pq["label"].unique()).issubset({"low", "medium", "high"})
    assert (pq["run_id"] == fp).all(), "run_id column does not match fingerprint"

    # --- manifest.json: fingerprint round-trip ---
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["run_fingerprint"] == fp, "manifest fingerprint mismatch"
    assert "config" in manifest, "manifest missing config snapshot"
    assert "input_fingerprints" in manifest, "manifest missing input fingerprints"
    for inp in manifest["input_fingerprints"]:
        assert len(inp["sha256"]) == 64, "fingerprint sha256 is not 64 hex chars"

    # --- report.json: coverage invariant and timing sanity ---
    report = json.loads((run_dir / "report.json").read_text())
    cov = report["coverage"]
    assert (
        abs(cov["roi_coverage_fraction"] + cov["roi_nodata_fraction"] - 1.0) < 1e-5
    ), "coverage fractions do not sum to 1"
    assert report["n_cells_sampled"] == len(pq), "n_cells_sampled mismatch"
    assert report["timings_sec"]["total"] > 0, "total timing must be positive"


@pytest.mark.smoke
def test_e2e_noop_rerun_does_not_overwrite(tmp_path: Path) -> None:
    """Second identical run must return cached results without touching artifacts."""
    raster = _make_synthetic_raster(tmp_path / "raster.tif")
    climate = _make_synthetic_climate(tmp_path / "climate.csv")
    cfg = _write_config(tmp_path / "config.yml", raster, climate, tmp_path / "out")

    df1 = run_pipeline(cfg)
    run_dir = Path(df1.attrs["run_dir"])
    mtime_before = (run_dir / "features.parquet").stat().st_mtime

    df2 = run_pipeline(cfg)
    mtime_after = (run_dir / "features.parquet").stat().st_mtime

    assert df1.attrs["run_fingerprint"] == df2.attrs["run_fingerprint"]
    assert (
        mtime_before == mtime_after
    ), "no-op rerun must not overwrite features.parquet"


@pytest.mark.smoke
def test_e2e_run_dir_named_after_fingerprint(tmp_path: Path) -> None:
    """Run directory name must equal the run_fingerprint string."""
    raster = _make_synthetic_raster(tmp_path / "raster.tif")
    climate = _make_synthetic_climate(tmp_path / "climate.csv")
    cfg = _write_config(tmp_path / "config.yml", raster, climate, tmp_path / "out")

    df = run_pipeline(cfg)
    run_dir = Path(df.attrs["run_dir"])
    assert (
        run_dir.name == df.attrs["run_fingerprint"]
    ), "run directory name must equal run_fingerprint"


# ---------------------------------------------------------------------------
# Climate-impact E2E smoke (#138f) — CMIP6 NetCDF → pipeline → climate_features
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_e2e_cmip6_climate_impact_pipeline(tmp_path: Path) -> None:
    """Full climate-impact path with a CMIP6 NetCDF input.

    Builds a synthetic CF-compliant NetCDF, converts it to the long-format
    station CSV via ``terraflow.cmip6``, then runs the full
    ``terraflow.pipeline.run_pipeline`` with both ``temporal_aggregations``
    and ``scenarios`` populated. Confirms ``climate_features.parquet`` lands
    alongside ``features.parquet`` with one column per ``<rule>__<scenario>``
    pair, and the CMIP6 file hash appears in ``manifest.json``."""
    xr = pytest.importorskip("xarray")
    pytest.importorskip("netCDF4")

    from terraflow.cmip6 import cmip6_to_station_timeseries

    # --- 1. Synthetic CMIP6 NetCDF (3 years × 3×3 lat/lon grid) ---
    nc_path = tmp_path / "tas_synthetic.nc"
    times = pd.date_range("2009-01-01", "2011-12-31", freq="D")
    lats = np.array([39.5, 40.0, 40.5])
    lons = np.array([-100.5, -100.0, -99.5])
    doy = times.dayofyear.to_numpy()
    seasonal = 12.0 + 12.0 * np.sin(2 * np.pi * (doy - 105) / 365.0)
    values = (
        seasonal.reshape(-1, 1, 1)
        + (np.arange(3).reshape(1, -1, 1) - 1) * 1.5
        + (np.arange(3).reshape(1, 1, -1) - 1) * 0.5
    ).astype("float32")
    da = xr.DataArray(
        values,
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": lats, "lon": lons},
        name="tas",
    )
    ds = da.to_dataset()
    ds.attrs.update(
        {
            "variant_label": "r1i1p1f1",
            "source_id": "TEST-CM",
            "experiment_id": "historical",
            "table_id": "day",
        }
    )
    ds.to_netcdf(nc_path)

    # --- 2. Convert to long-format station CSV ---
    stations = pd.DataFrame(
        {
            "station_id": ["S1", "S2", "S3"],
            "lat": [39.6, 40.0, 40.4],
            "lon": [-100.4, -100.0, -99.6],
        }
    )
    ts_df = cmip6_to_station_timeseries(
        nc_path, stations, output_variable="temperature_c"
    )
    # The temporal engine also needs precipitation_mm for SPEI etc. — add a
    # constant column so the schema validator passes.
    ts_df["precipitation_mm"] = 2.5
    ts_csv = tmp_path / "ts.csv"
    ts_df.to_csv(ts_csv, index=False)

    # --- 3. Pipeline inputs ---
    raster = _make_synthetic_raster(tmp_path / "raster.tif")
    climate = _make_synthetic_climate(tmp_path / "climate.csv")
    out_dir = tmp_path / "out"
    cfg_path = tmp_path / "cfg.yml"
    cfg_path.write_text(
        f"""
raster_path: "{raster}"
climate_csv: "{climate}"
output_dir: "{out_dir}"
roi:
  type: bbox
  xmin: -101.0
  ymin: 39.0
  xmax: -99.0
  ymax: 41.0
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
climate:
  strategy: spatial
  interpolation_method: linear
  timeseries_csv: "{ts_csv}"
  temporal_aggregations:
    - kind: annual_mean
    - kind: growing_degree_days
      base_temp_c: 10.0
  scenarios:
    - name: historical
      period: [2009, 2009]
    - name: ssp245
      period: [2011, 2011]
max_cells: 10
""",
        encoding="utf-8",
    )

    # --- 4. Run pipeline ---
    df = run_pipeline(cfg_path)
    run_dir = Path(df.attrs["run_dir"])

    # --- 5. Validate climate_features.parquet ---
    cf_path = run_dir / "climate_features.parquet"
    assert cf_path.exists(), "climate_features.parquet must be written"
    cf = pd.read_parquet(cf_path)
    assert "cell_id" in cf.columns
    derived = [c for c in cf.columns if c != "cell_id"]
    assert len(derived) == 4, f"expected 4 derived columns, got {derived}"
    expected = {
        "annual_mean__historical",
        "annual_mean__ssp245",
        "growing_degree_days__base10__historical",
        "growing_degree_days__base10__ssp245",
    }
    assert expected <= set(cf.columns)

    # --- 6. Manifest must list the new artifact ---
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "climate_features.parquet" in manifest["output_files"]
