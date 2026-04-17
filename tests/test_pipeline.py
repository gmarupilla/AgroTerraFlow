import json
import textwrap
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from terraflow.pipeline import _aggregate_climate, run_pipeline


def test_run_pipeline_with_synthetic_data(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
):
    out_dir = tmp_path / "outputs"

    cfg_content = textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
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
        """)

    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df = run_pipeline(cfg_file)

    # Basic structural checks
    assert not df.empty
    assert len(df) <= 10
    assert {"cell_id", "lat", "lon", "v_index", "score", "label"}.issubset(
        df.columns,
    )

    # Scores must be in [0, 1]
    assert df["score"].between(0.0, 1.0).all()

    # Labels must be from the expected set
    assert set(df["label"].unique()).issubset({"low", "medium", "high"})

    # lat/lon must always be WGS84 geographic degrees (TERRA-011)
    assert df["lat"].between(-90.0, 90.0).all(), "lat must be in [-90, 90]"
    assert df["lon"].between(-180.0, 180.0).all(), "lon must be in [-180, 180]"

    # Artifacts live under runs/<run_fingerprint>/
    run_fp = df.attrs["run_fingerprint"]
    run_dir = out_dir / "runs" / run_fp
    assert run_dir.is_dir(), f"run_dir missing: {run_dir}"
    assert (run_dir / "features.parquet").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "results.csv").exists()


def test_run_pipeline_config_in_subdirectory(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
):
    """Relative paths in a config file must resolve against the config's directory,
    not the caller's working directory (TERRA-001)."""
    # Place data files one level up from where the config will live
    sub_dir = tmp_path / "configs"
    sub_dir.mkdir()
    out_dir = tmp_path / "outputs"

    # Write config with relative paths (../... relative to sub_dir)
    rel_raster = Path("..") / synthetic_raster.name
    rel_climate = Path("..") / synthetic_climate_csv.name
    rel_out = Path("..") / "outputs"

    # Copy fixtures into tmp_path root so relative paths resolve correctly
    import shutil

    shutil.copy(synthetic_raster, tmp_path / synthetic_raster.name)
    shutil.copy(synthetic_climate_csv, tmp_path / synthetic_climate_csv.name)

    cfg_content = f"""
raster_path: "{rel_raster.as_posix()}"
climate_csv: "{rel_climate.as_posix()}"
output_dir: "{rel_out.as_posix()}"

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

max_cells: 5
"""
    cfg_file = sub_dir / "config.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df = run_pipeline(cfg_file)

    assert not df.empty
    run_fp = df.attrs["run_fingerprint"]
    run_dir = out_dir / "runs" / run_fp
    assert (run_dir / "results.csv").exists()


def test_pipeline_lat_lon_wgs84_for_projected_raster(tmp_path: Path):
    """Pipeline must output lat/lon in WGS84 degrees even when the input raster
    is in a projected CRS (TERRA-011)."""
    # Build a tiny EPSG:32614 (UTM Zone 14N) raster over Kansas
    raster_path = tmp_path / "utm_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    west_utm, north_utm, pixel_m = 500_000.0, 4_261_000.0, 1_000.0
    transform = from_origin(
        west=west_utm, north=north_utm, xsize=pixel_m, ysize=pixel_m
    )
    crs = CRS.from_epsg(32614)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(arr, 1)

    # Derive WGS84 ROI from the raster's UTM extent
    t = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    lon_min, lat_min = t.transform(west_utm, north_utm - 5 * pixel_m)
    lon_max, lat_max = t.transform(west_utm + 5 * pixel_m, north_utm)

    # Climate CSV with one station near Kansas (WGS84 degrees)
    climate_path = tmp_path / "climate.csv"
    climate_path.write_text(
        "lat,lon,mean_temp,total_rain\n38.5,-99.0,20.0,120.0\n", encoding="utf-8"
    )

    cfg_content = f"""
raster_path: "{raster_path}"
climate_csv: "{climate_path}"
output_dir: "{tmp_path / 'outputs'}"
roi:
  type: bbox
  xmin: {lon_min}
  ymin: {lat_min}
  xmax: {lon_max}
  ymax: {lat_max}
  roi_crs: "EPSG:4326"
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
max_cells: 5
"""
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df = run_pipeline(cfg_file)

    assert not df.empty
    # Core acceptance criterion: lat/lon must be geographic degrees
    assert (
        df["lat"].between(-90.0, 90.0).all()
    ), f"lat out of range: {df['lat'].tolist()}"
    assert (
        df["lon"].between(-180.0, 180.0).all()
    ), f"lon out of range: {df['lon'].tolist()}"
    # Scores still valid
    assert df["score"].between(0.0, 1.0).all()


def test_aggregate_climate_means():
    import pandas as pd

    df = pd.DataFrame(
        {
            "mean_temp": [10.0, 12.0, 14.0],
            "total_rain": [100.0, 110.0, 120.0],
        }
    )

    result = _aggregate_climate(df)

    assert result["mean_temp"] == 12.0
    assert result["total_rain"] == 110.0


def test_aggregate_climate_missing_columns():
    import pandas as pd

    df = pd.DataFrame({"mean_temp": [10.0, 12.0]})

    with pytest.raises(ValueError, match="total_rain"):
        _aggregate_climate(df)


# ---------------------------------------------------------------------------
# Helpers for kriging / CRS mismatch tests
# ---------------------------------------------------------------------------


def _write_kriging_config(
    cfg_file: Path,
    raster_path: Path,
    climate_csv: Path,
    output_dir: Path,
    uncertainty_samples: int = 0,
) -> Path:
    """Write a pipeline config YAML file with kriging interpolation enabled."""
    cfg = textwrap.dedent(f"""
        raster_path: "{raster_path}"
        climate_csv: "{climate_csv}"
        output_dir: "{output_dir}"

        roi:
          type: "bbox"
          xmin: -100.05
          ymin: 39.95
          xmax: -99.95
          ymax: 40.05

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
          uncertainty_samples: {uncertainty_samples}

        climate:
          strategy: "spatial"
          interpolation_method: "kriging"

        max_cells: 5
    """)
    cfg_file.write_text(cfg, encoding="utf-8")
    return cfg_file


def _write_no_crs_raster(path: Path) -> Path:
    """Create a GeoTIFF with no CRS for testing CRSMismatchError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype=arr.dtype,
        crs=None,
        transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return path


# ---------------------------------------------------------------------------
# CRS mismatch test
# ---------------------------------------------------------------------------


def test_crs_mismatch_error_none_crs(tmp_path, synthetic_climate_csv_dense):
    """Pipeline raises CRSMismatchError when raster has no CRS."""
    from terraflow.exceptions import CRSMismatchError

    raster_path = _write_no_crs_raster(tmp_path / "data" / "no_crs.tif")
    cfg_path = _write_kriging_config(
        tmp_path / "cfg.yml",
        raster_path,
        synthetic_climate_csv_dense,
        tmp_path / "out",
    )
    with pytest.raises(CRSMismatchError, match="has no CRS"):
        run_pipeline(cfg_path)


# ---------------------------------------------------------------------------
# Kriging diagnostics in report.json test
# ---------------------------------------------------------------------------


def test_kriging_diagnostics_in_report(
    tmp_path, synthetic_raster, synthetic_climate_csv_dense
):
    """report.json includes kriging_diagnostics when kriging is used."""
    cfg_path = _write_kriging_config(
        tmp_path / "cfg.yml",
        synthetic_raster,
        synthetic_climate_csv_dense,
        tmp_path / "out",
    )
    df = run_pipeline(cfg_path)
    run_dir = Path(df.attrs["run_dir"])
    report = json.loads((run_dir / "report.json").read_text())

    assert "kriging_diagnostics" in report
    diag = report["kriging_diagnostics"]
    for key in ("model", "psill", "nugget", "sill", "range_", "range_units"):
        assert key in diag, f"Missing key '{key}' in kriging_diagnostics"
    assert diag["range_units"] == "degrees_geographic"
    assert diag["sill"] == pytest.approx(diag["psill"] + diag["nugget"], rel=1e-4)


def test_resolve_run_dir_returns_deterministic_path(
    tmp_path, synthetic_raster, synthetic_climate_csv
):
    """resolve_run_dir returns the same fingerprinted path as run_pipeline."""
    from terraflow.pipeline import resolve_run_dir

    cfg_path = tmp_path / "cfg.yml"
    out_dir = tmp_path / "out"
    cfg_path.write_text(textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
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
    """))

    run_dir = resolve_run_dir(cfg_path)
    assert run_dir.name  # fingerprint is non-empty
    assert "runs" in run_dir.parts

    # Calling twice returns the same path (deterministic)
    assert resolve_run_dir(cfg_path) == run_dir
