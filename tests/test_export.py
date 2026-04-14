"""Unit tests for terraflow.export (to_h3) and ExportConfig."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

_H3_INSTALLED = importlib.util.find_spec("h3") is not None


# ── ExportConfig tests ─────────────────────────────────────────────────────────


def test_export_config_default():
    from terraflow.config import ExportConfig

    cfg = ExportConfig()
    assert cfg.h3_resolution == 8


def test_export_config_valid_resolution_zero():
    from terraflow.config import ExportConfig

    cfg = ExportConfig(h3_resolution=0)
    assert cfg.h3_resolution == 0


def test_export_config_valid_resolution_fifteen():
    from terraflow.config import ExportConfig

    cfg = ExportConfig(h3_resolution=15)
    assert cfg.h3_resolution == 15


def test_export_config_invalid_resolution_negative():
    from pydantic import ValidationError

    from terraflow.config import ExportConfig

    with pytest.raises(ValidationError):
        ExportConfig(h3_resolution=-1)


def test_export_config_invalid_resolution_sixteen():
    from pydantic import ValidationError

    from terraflow.config import ExportConfig

    with pytest.raises(ValidationError):
        ExportConfig(h3_resolution=16)


def test_pipeline_config_accepts_export_section():
    from terraflow.config import ExportConfig

    cfg = ExportConfig(h3_resolution=6)
    assert cfg.h3_resolution == 6


def test_pipeline_config_export_defaults_none():
    """PipelineConfig.export should default to None when not provided."""
    from terraflow.config import PipelineConfig

    fields = PipelineConfig.model_fields
    assert "export" in fields
    assert fields["export"].default is None


# ── to_h3 tests ────────────────────────────────────────────────────────────────


def _make_df(n=5, lat=37.0, lon=-122.0):
    """Helper: minimal features DataFrame for to_h3 tests."""
    return pd.DataFrame(
        {
            "lat": [lat] * n,
            "lon": [lon] * n,
            "score": [float(i) for i in range(n)],
            "v_index": [0.5] * n,
            "mean_temp": [20.0] * n,
            "total_rain": [100.0] * n,
            "label": ["high"] * n,
        }
    )


def test_to_h3_importerror():
    """to_h3 raises ImportError with install hint when h3 unavailable."""
    from terraflow import export as export_mod
    from terraflow.export import to_h3

    with patch.object(export_mod, "_H3_AVAILABLE", False):
        with pytest.raises(ImportError, match="pip install terraflow-agro\\[h3\\]"):
            to_h3(_make_df())


def test_to_h3_basic():
    """to_h3 returns H3-indexed DataFrame with expected columns."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    df = _make_df(n=5)
    result = to_h3(df, resolution=4)

    assert result.index.name == "h3_cell"
    for col in ["score", "v_index", "mean_temp", "total_rain", "label"]:
        assert col in result.columns
    assert len(result) > 0


_SAME_CELL_DF = pd.DataFrame(
    {
        "lat": [37.0, 37.0, 37.0],
        "lon": [-122.0, -122.0, -122.0],
        "score": [1.0, 2.0, 3.0],
        "v_index": [0.5, 0.5, 0.5],
        "mean_temp": [20.0, 20.0, 20.0],
        "total_rain": [100.0, 100.0, 100.0],
        "label": ["high", "high", "low"],
    }
)


def test_to_h3_aggregation_mean():
    """Rows mapping to same H3 cell are aggregated by mean for numeric columns."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    result = to_h3(_SAME_CELL_DF.copy(), resolution=4)

    assert len(result) == 1
    assert result["score"].iloc[0] == pytest.approx(2.0)


def test_to_h3_aggregation_mode():
    """Label column is aggregated by mode."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    result = to_h3(_SAME_CELL_DF.copy(), resolution=4)

    assert result["label"].iloc[0] == "high"


def test_to_h3_invalid_resolution():
    """to_h3 raises ValueError for resolution outside 0-15."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    with pytest.raises(ValueError):
        to_h3(_make_df(), resolution=20)


def test_to_h3_missing_columns():
    """to_h3 raises ValueError when required columns are missing."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    df = pd.DataFrame({"score": [1.0], "lon": [-122.0]})  # missing lat and others
    with pytest.raises(ValueError, match="Missing required columns"):
        to_h3(df)


# ── run_export tests ────────────────────────────────────────────────────────────

_BASE_CONFIG = """\
raster_path: raster.tif
climate_csv: climate.csv
output_dir: {out_dir}
roi:
  xmin: -123.0
  ymin: 36.0
  xmax: -121.0
  ymax: 38.0
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
"""

_EXPORT_CONFIG = _BASE_CONFIG + "export:\n  h3_resolution: 8\n"
_NO_EXPORT_CONFIG = _BASE_CONFIG


def _make_features_parquet(run_dir: "Path", n: int = 5) -> None:
    """Write a minimal features.parquet to run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "run_id": ["r"] * n,
            "cell_id": list(range(n)),
            "lat": [37.0] * n,
            "lon": [-122.0] * n,
            "v_index": [0.5] * n,
            "mean_temp": [20.0] * n,
            "total_rain": [100.0] * n,
            "score": [float(i) for i in range(n)],
            "label": ["high"] * n,
        }
    )
    df.to_parquet(run_dir / "features.parquet", index=False)


class TestRunExport:
    """Tests for run_export() orchestrator."""

    def test_run_export_writes_artifact(self, tmp_path):
        """run_export writes h3_resolution_8.parquet to the run directory."""
        pytest.importorskip("h3")
        from unittest.mock import patch

        from terraflow.export import run_export

        run_dir = tmp_path / "runs" / "abc123"
        _make_features_parquet(run_dir)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_EXPORT_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.export.resolve_run_dir", return_value=run_dir):
            result = run_export(cfg_path)

        assert (run_dir / "h3_resolution_8.parquet").exists()
        assert result == run_dir / "h3_resolution_8.parquet"

    def test_run_export_resolution_override_filename(self, tmp_path):
        """resolution_override changes the output filename but not the run directory."""
        pytest.importorskip("h3")
        from unittest.mock import patch

        from terraflow.export import run_export

        run_dir = tmp_path / "runs" / "abc123"
        _make_features_parquet(run_dir)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_EXPORT_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.export.resolve_run_dir", return_value=run_dir):
            result = run_export(cfg_path, resolution_override=4)

        assert (run_dir / "h3_resolution_4.parquet").exists()
        assert not (run_dir / "h3_resolution_8.parquet").exists()
        assert result == run_dir / "h3_resolution_4.parquet"

    def test_run_export_no_export_section(self, tmp_path):
        """run_export raises ValueError when config has no 'export:' section."""
        from unittest.mock import patch

        from terraflow.export import run_export

        run_dir = tmp_path / "runs" / "abc123"
        run_dir.mkdir(parents=True, exist_ok=True)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_NO_EXPORT_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.export.resolve_run_dir", return_value=run_dir):
            with pytest.raises(ValueError, match="no 'export:' section"):
                run_export(cfg_path)

    def test_run_export_unsupported_format(self, tmp_path):
        """run_export raises ValueError for unsupported export formats."""
        from unittest.mock import patch

        from terraflow.export import run_export

        run_dir = tmp_path / "runs" / "abc123"
        run_dir.mkdir(parents=True, exist_ok=True)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_EXPORT_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.export.resolve_run_dir", return_value=run_dir):
            with pytest.raises(ValueError, match="Unsupported export format"):
                run_export(cfg_path, format="geojson")

    def test_run_export_missing_features_raises(self, tmp_path):
        """run_export raises FileNotFoundError when features.parquet is absent."""
        from unittest.mock import patch

        from terraflow.export import run_export

        run_dir = tmp_path / "runs" / "missing"
        # Do NOT create features.parquet

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_EXPORT_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.export.resolve_run_dir", return_value=run_dir):
            with pytest.raises(FileNotFoundError):
                run_export(cfg_path)


def test_resolution_changes_fingerprint():
    """Two configs differing only in h3_resolution produce distinct fingerprints (H3-03)."""
    from terraflow.core.run_identity import compute_run_fingerprint

    config_res8 = {
        "raster_path": "/data/raster.tif",
        "climate_csv": "/data/climate.csv",
        "output_dir": "/data/outputs",
        "roi": {"xmin": -123.0, "ymin": 36.0, "xmax": -121.0, "ymax": 38.0},
        "export": {"h3_resolution": 8},
    }
    config_res4 = {
        **config_res8,
        "export": {"h3_resolution": 4},
    }

    roi_hash = "deadbeef" * 8  # arbitrary stable hash
    fp8 = compute_run_fingerprint(config_res8, roi_hash, [])
    fp4 = compute_run_fingerprint(config_res4, roi_hash, [])

    assert (
        fp8 != fp4
    ), "Different h3_resolution values must produce distinct fingerprints"
