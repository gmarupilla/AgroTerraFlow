"""Unit tests for the CLI module."""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest
import textwrap

from terraflow.cli import main


def test_cli_missing_config_arg(capsys):
    """Test that CLI errors when config argument is missing."""
    with patch.object(sys, "argv", ["terraflow"]):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "required" in captured.err.lower() or "arguments" in captured.err.lower()


def test_cli_config_file_not_found(tmp_path: Path, capsys):
    """Test that CLI provides helpful error when config file doesn't exist."""
    nonexistent_path = tmp_path / "nonexistent.yml"

    with patch.object(sys, "argv", ["terraflow", "-c", str(nonexistent_path)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


def test_cli_valid_config_runs_pipeline(tmp_path: Path):
    """Test that CLI successfully runs pipeline with valid config."""
    # Create minimal config with paths relative to tmp_path
    cfg_content = f"""raster_path: "{tmp_path}/data/synthetic_raster.tif"
climate_csv: "{tmp_path}/data/climate.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: "bbox"
  xmin: -100.005
  ymin: 39.995
  xmax: -99.985
  ymax: 40.015
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
"""

    # Create temporary config file
    cfg_file = tmp_path / "test_config.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    # Create synthetic data files
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    import pandas as pd

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create synthetic raster
    raster_path = data_dir / "synthetic_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(arr, 1)

    # Create climate CSV
    climate_df = pd.DataFrame({"mean_temp": [15.0], "total_rain": [100.0]})
    climate_df.to_csv(data_dir / "climate.csv", index=False)

    # Run CLI
    with patch.object(sys, "argv", ["terraflow", "-c", str(cfg_file)]):
        main()

    # Verify output was created
    results_file = tmp_path / "outputs" / "results.csv"
    assert results_file.exists()
    results_df = pd.read_csv(results_file)
    assert len(results_df) > 0
    assert "score" in results_df.columns


def test_cli_raster_file_not_found(tmp_path: Path, capsys):
    """Test CLI error handling when raster file doesn't exist."""
    cfg_content = textwrap.dedent(
        """
        raster_path: "nonexistent_raster.tif"
        climate_csv: "data/climate.csv"
        output_dir: "outputs"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        max_cells: 10
        """
    )

    cfg_file = tmp_path / "test_config.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with patch.object(sys, "argv", ["terraflow", "-c", str(cfg_file)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "error" in captured.err.lower() or "not found" in captured.err.lower()


def test_cli_climate_file_not_found(tmp_path: Path, capsys):
    """Test CLI error handling when climate CSV doesn't exist."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    cfg_content = textwrap.dedent(
        """
        raster_path: "data/synthetic_raster.tif"
        climate_csv: "nonexistent_climate.csv"
        output_dir: "outputs"
        roi:
          type: "bbox"
          xmin: -100.005
          ymin: 39.995
          xmax: -99.985
          ymax: 40.015
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
        """
    )

    cfg_file = tmp_path / "test_config.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    # Create synthetic raster
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    raster_path = data_dir / "synthetic_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(arr, 1)

    with patch.object(sys, "argv", ["terraflow", "-c", str(cfg_file)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "error" in captured.err.lower()


def test_cli_help_message(capsys):
    """Test that --help displays helpful information."""
    with patch.object(sys, "argv", ["terraflow", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "terraflow" in captured.out.lower()
    assert "config" in captured.out.lower()
