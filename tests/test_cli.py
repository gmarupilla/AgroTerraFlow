"""Unit tests for the CLI module."""

import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from terraflow.cli import _invoke, app, main

runner = CliRunner()


def test_cli_missing_config_arg(capsys):
    """Test that CLI errors when config argument is missing."""
    with patch.object(sys, "argv", ["terraflow", "run"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


def test_cli_config_file_not_found(tmp_path: Path, capsys):
    """Test that CLI provides helpful error when config file doesn't exist."""
    nonexistent_path = tmp_path / "nonexistent.yml"

    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(nonexistent_path)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2  # Typer exits with 2 for invalid path option


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
    import pandas as pd
    import rasterio
    from rasterio.transform import from_origin

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

    # Create climate CSV (with lat/lon for spatial interpolation)
    climate_df = pd.DataFrame(
        {
            "lat": [39.995, 40.005, 40.015],
            "lon": [-100.005, -99.995, -99.985],
            "mean_temp": [15.0, 16.0, 17.0],
            "total_rain": [100.0, 110.0, 120.0],
        }
    )
    climate_df.to_csv(data_dir / "climate.csv", index=False)

    # Run CLI — Typer calls sys.exit(0) on success in standalone mode
    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(cfg_file)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    # Artifacts live under outputs/runs/<run_fingerprint>/
    outputs_dir = tmp_path / "outputs"
    runs_dir = outputs_dir / "runs"
    assert runs_dir.is_dir(), "runs/ directory must be created"
    run_subdirs = list(runs_dir.iterdir())
    assert len(run_subdirs) == 1, "Exactly one run directory expected"
    run_dir = run_subdirs[0]

    results_file = run_dir / "results.csv"
    assert results_file.exists()
    results_df = pd.read_csv(results_file)
    assert len(results_df) > 0
    assert "score" in results_df.columns
    assert (run_dir / "features.parquet").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "report.json").exists()


def test_cli_raster_file_not_found(tmp_path: Path, capsys):
    """Test CLI error handling when raster file doesn't exist."""
    cfg_content = textwrap.dedent("""
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
        """)

    cfg_file = tmp_path / "test_config.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(cfg_file)]):
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

    cfg_content = textwrap.dedent("""
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
        """)

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

    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(cfg_file)]):
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
    assert "run" in captured.out.lower()
    assert "sensitivity" in captured.out.lower()


@pytest.mark.parametrize(
    "exc, expected_exit, expected_substr",
    [
        (ValueError("bad cfg"), 1, "bad cfg"),
        (FileNotFoundError("no file"), 1, "no file"),
        (ImportError("no module"), 1, "no module"),
        (NotImplementedError("placeholder"), 2, "not yet implemented"),
        (RuntimeError("boom"), 1, "Demo failed"),
    ],
)
def test_invoke_translates_known_exceptions(
    exc, expected_exit, expected_substr, capsys
):
    def fn():
        raise exc

    with pytest.raises(SystemExit) as exc_info:
        _invoke("Demo", fn)
    assert exc_info.value.code == expected_exit
    captured = capsys.readouterr()
    assert expected_substr in captured.err


def test_invoke_returns_value_on_success():
    assert _invoke("Demo", lambda: "ok") == "ok"


def test_cli_value_error_from_pipeline(tmp_path: Path, capsys):
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text('raster_path: "data.tif"', encoding="utf-8")

    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(cfg_file)]):
        with patch("terraflow.cli.run_pipeline", side_effect=ValueError("bad config")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "bad config" in captured.err.lower()


def test_cli_unexpected_exception_from_pipeline(tmp_path: Path, capsys):
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text('raster_path: "data.tif"', encoding="utf-8")

    with patch.object(sys, "argv", ["terraflow", "run", "-c", str(cfg_file)]):
        with patch("terraflow.cli.run_pipeline", side_effect=RuntimeError("boom")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "pipeline failed" in captured.err.lower()


def test_cli_old_flat_command_fails(tmp_path: Path):
    """Test that old flat 'terraflow -c' no longer works (D-02)."""
    cfg_file = tmp_path / "test_config.yml"
    cfg_file.write_text("raster_path: x\n", encoding="utf-8")
    with patch.object(sys, "argv", ["terraflow", "-c", str(cfg_file)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2  # Typer: no such option at top level


def test_sensitivity_cmd_success(tmp_path: Path):
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake.tif"
climate_csv: "{tmp_path}/fake.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
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
sensitivity:
  w_v:
    low: 0.2
    high: 0.5
  w_t:
    low: 0.2
    high: 0.5
  w_r:
    low: 0.1
    high: 0.4
  n_samples: 64
  method: both
""",
        encoding="utf-8",
    )
    with patch.object(sys, "argv", ["terraflow", "sensitivity", "-c", str(cfg)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    assert (tmp_path / "outputs" / "sensitivity_report.json").exists()


def test_sensitivity_nonpower_of_two(tmp_path: Path, capsys):
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake.tif"
climate_csv: "{tmp_path}/fake.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
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
sensitivity:
  w_v:
    low: 0.2
    high: 0.5
  w_t:
    low: 0.2
    high: 0.5
  w_r:
    low: 0.1
    high: 0.4
  n_samples: 100
  method: sobol
""",
        encoding="utf-8",
    )
    with patch.object(sys, "argv", ["terraflow", "sensitivity", "-c", str(cfg)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "power of 2" in captured.err.lower()


def test_sensitivity_missing_section(tmp_path: Path, capsys):
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake.tif"
climate_csv: "{tmp_path}/fake.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
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
""",
        encoding="utf-8",
    )
    with patch.object(sys, "argv", ["terraflow", "sensitivity", "-c", str(cfg)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "sensitivity" in captured.err.lower()


class TestExportCLI:
    """CLI tests for the export subcommand."""

    def _minimal_export_config(self, tmp_path: Path) -> Path:
        cfg_content = f"""raster_path: "{tmp_path}/fake.tif"
climate_csv: "{tmp_path}/fake.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
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
export:
  h3_resolution: 8
"""
        cfg = tmp_path / "export_config.yml"
        cfg.write_text(cfg_content, encoding="utf-8")
        return cfg

    def test_cli_export_missing_format(self, tmp_path: Path):
        """export command exits 2 when --format is missing (required option)."""
        cfg = self._minimal_export_config(tmp_path)
        with patch.object(sys, "argv", ["terraflow", "export", "-c", str(cfg)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_cli_export_unsupported_format(self, tmp_path: Path, capsys):
        """export command exits 1 when format is unsupported."""
        cfg = self._minimal_export_config(tmp_path)
        with patch.object(
            sys, "argv", ["terraflow", "export", "--format", "geojson", "-c", str(cfg)]
        ):
            with patch(
                "terraflow.export.run_export",
                side_effect=ValueError("Unsupported export format: 'geojson'"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    def test_cli_export_h3_success(self, tmp_path: Path):
        """export command exits 0 on successful H3 export."""
        cfg = self._minimal_export_config(tmp_path)
        fake_output = (
            tmp_path / "outputs" / "runs" / "abc123" / "h3_resolution_8.parquet"
        )
        with patch.object(
            sys, "argv", ["terraflow", "export", "--format", "h3", "-c", str(cfg)]
        ):
            with patch("terraflow.export.run_export", return_value=fake_output):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_cli_export_missing_h3(self, tmp_path: Path, capsys):
        """export command exits 1 when h3 package is not installed."""
        cfg = self._minimal_export_config(tmp_path)
        with patch.object(
            sys, "argv", ["terraflow", "export", "--format", "h3", "-c", str(cfg)]
        ):
            with patch(
                "terraflow.export.run_export",
                side_effect=ImportError("h3 is required..."),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


class TestValidateCLI:
    """CLI tests for the validate subcommand."""

    def test_validate_missing_config_section(self, tmp_path):
        """validate command exits 1 when config has no validation section."""
        cfg = tmp_path / "no_val.yml"
        cfg.write_text(
            "raster_path: fake.tif\nclimate_csv: fake.csv\noutput_dir: out\n"
        )
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["validate", "-c", str(cfg)])
        assert result.exit_code != 0

    def test_validate_help(self):
        """validate --help shows usage."""
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert (
            "validation" in result.output.lower() or "config" in result.output.lower()
        )
