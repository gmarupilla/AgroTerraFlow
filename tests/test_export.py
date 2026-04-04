"""Unit tests for terraflow.export (to_h3) and ExportConfig."""
from __future__ import annotations

import importlib

import pandas as pd
import pytest
from unittest.mock import patch

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
    from terraflow.config import ExportConfig
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExportConfig(h3_resolution=-1)


def test_export_config_invalid_resolution_sixteen():
    from terraflow.config import ExportConfig
    from pydantic import ValidationError

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
        with pytest.raises(ImportError, match="pip install terraflow\\[h3\\]"):
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


def test_to_h3_aggregation_mean():
    """Rows mapping to same H3 cell are aggregated by mean for numeric columns."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    df = pd.DataFrame(
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
    result = to_h3(df, resolution=4)

    assert len(result) == 1
    assert result["score"].iloc[0] == pytest.approx(2.0)


def test_to_h3_aggregation_mode():
    """Label column is aggregated by mode."""
    pytest.importorskip("h3")
    from terraflow.export import to_h3

    df = pd.DataFrame(
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
    result = to_h3(df, resolution=4)

    assert result["label"].iloc[0] == "high"


def test_to_h3_invalid_resolution():
    """to_h3 raises ValueError for resolution outside 0-15."""
    from terraflow.export import to_h3

    with pytest.raises(ValueError):
        to_h3(_make_df(), resolution=20)


def test_to_h3_missing_columns():
    """to_h3 raises ValueError when required columns are missing."""
    from terraflow.export import to_h3

    df = pd.DataFrame({"score": [1.0], "lon": [-122.0]})  # missing lat and others
    with pytest.raises(ValueError, match="Missing required columns"):
        to_h3(df)
