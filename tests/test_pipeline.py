from pathlib import Path
import textwrap

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from terraflow.pipeline import run_pipeline, _aggregate_climate


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

    # Results file exists
    results_csv = out_dir / "results.csv"
    assert results_csv.exists()


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
    assert (out_dir / "results.csv").exists()


def test_pipeline_lat_lon_wgs84_for_projected_raster(tmp_path: Path):
    """Pipeline must output lat/lon in WGS84 degrees even when the input raster
    is in a projected CRS (TERRA-011)."""
    # Build a tiny EPSG:32614 (UTM Zone 14N) raster over Kansas
    raster_path = tmp_path / "utm_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    west_utm, north_utm, pixel_m = 500_000.0, 4_261_000.0, 1_000.0
    transform = from_origin(west=west_utm, north=north_utm, xsize=pixel_m, ysize=pixel_m)
    crs = CRS.from_epsg(32614)

    with rasterio.open(
        raster_path, "w", driver="GTiff",
        height=5, width=5, count=1, dtype="float32",
        crs=crs, transform=transform,
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
    assert df["lat"].between(-90.0, 90.0).all(), f"lat out of range: {df['lat'].tolist()}"
    assert df["lon"].between(-180.0, 180.0).all(), f"lon out of range: {df['lon'].tolist()}"
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
    import pytest

    df = pd.DataFrame({"mean_temp": [10.0, 12.0]})

    with pytest.raises(ValueError, match="total_rain"):
        _aggregate_climate(df)
