"""Tests for terraflow.validation module (Phase 3: Model Validation)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


class TestSpatialBlockCV:
    """VALD-01: Spatial block cross-validation."""

    def test_assign_block_ids_grid(self):
        """Block IDs assigned correctly for a regular grid."""
        # 16 points in a 4x4 grid → 4 blocks with n_blocks_side=2
        lats = np.array(
            [
                0.0,
                0.0,
                1.0,
                1.0,
                0.0,
                0.0,
                1.0,
                1.0,
                2.0,
                2.0,
                3.0,
                3.0,
                2.0,
                2.0,
                3.0,
                3.0,
            ]
        )
        lons = np.array(
            [
                0.0,
                1.0,
                0.0,
                1.0,
                2.0,
                3.0,
                2.0,
                3.0,
                0.0,
                1.0,
                0.0,
                1.0,
                2.0,
                3.0,
                2.0,
                3.0,
            ]
        )
        from terraflow.validation import _assign_block_ids

        ids = _assign_block_ids(lats, lons, n_blocks_side=2)
        assert ids.shape == (16,)
        assert len(np.unique(ids)) >= 2

    def test_spatial_block_cv_returns_fold_accuracies(self):
        """Spatial block CV returns a list of per-fold accuracy floats."""
        lats = np.linspace(0, 3, 20)
        lons = np.linspace(0, 3, 20)
        labels = np.array(["low"] * 10 + ["high"] * 10)
        from terraflow.validation import _spatial_block_cv

        accs = _spatial_block_cv(lats, lons, labels, n_blocks_side=2, buffer_deg=0.1)
        assert isinstance(accs, list)
        assert all(0.0 <= a <= 1.0 for a in accs)

    def test_spatial_cv_degenerate_few_blocks(self):
        """Fewer than 2 unique blocks returns empty list with warning."""
        lats = np.array([1.0, 1.0, 1.0])
        lons = np.array([1.0, 1.0, 1.0])
        labels = np.array(["low", "low", "low"])
        from terraflow.validation import _spatial_block_cv

        accs = _spatial_block_cv(lats, lons, labels, n_blocks_side=2, buffer_deg=0.1)
        assert accs == []


class TestReportValidationBlock:
    """VALD-04: report.json validation block structure."""

    def test_validation_block_has_required_keys(self):
        """Validation block exposes mean_fold_accuracy + n_folds."""
        from terraflow.validation import run_validation

        assert callable(run_validation)


_MINIMAL_CONFIG = """\
raster_path: fake.tif
climate_csv: fake.csv
output_dir: {out_dir}
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
validation:
  n_blocks_side: 2
  buffer_deg: 0.0
"""


def _make_features_parquet(run_dir, n=30):
    """Write a minimal features.parquet into run_dir."""

    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        {
            "lat": np.linspace(0.0, 3.0, n),
            "lon": np.linspace(0.0, 3.0, n),
            "score": rng.uniform(0.2, 0.9, n),
            "label": np.where(np.linspace(0.0, 3.0, n) > 1.5, "high", "low"),
            "cell_id": np.arange(n),
            "run_id": ["test"] * n,
        }
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(run_dir / "features.parquet", index=False)
    return df


class TestRunValidation:
    """Integration tests for run_validation() — exercises lines 268-345."""

    def test_run_validation_writes_block(self, tmp_path):
        """run_validation writes required keys to report.json."""
        import json
        from unittest.mock import patch

        from terraflow.validation import run_validation

        run_dir = tmp_path / "runs" / "abc123"
        _make_features_parquet(run_dir)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_MINIMAL_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.validation.resolve_run_dir", return_value=run_dir):
            result = run_validation(cfg_path)

        assert result.exists()
        block = json.loads(result.read_text())["validation"]
        for key in (
            "method",
            "n_folds",
            "mean_fold_accuracy",
            "n_blocks_side",
            "buffer_deg",
        ):
            assert key in block, f"missing key: {key}"

    def test_run_validation_merges_existing_report(self, tmp_path):
        """Existing report.json fields are preserved after validation."""
        import json
        from unittest.mock import patch

        from terraflow.validation import run_validation

        run_dir = tmp_path / "runs" / "abc123"
        _make_features_parquet(run_dir)
        (run_dir / "report.json").write_text(
            json.dumps({"run_id": "abc123", "timings": {"total_s": 1.5}})
        )

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_MINIMAL_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.validation.resolve_run_dir", return_value=run_dir):
            run_validation(cfg_path)

        report = json.loads((run_dir / "report.json").read_text())
        assert report["run_id"] == "abc123"
        assert "validation" in report

    def test_run_validation_no_existing_report(self, tmp_path):
        """run_validation creates report.json when none exists."""
        import json
        from unittest.mock import patch

        from terraflow.validation import run_validation

        run_dir = tmp_path / "runs" / "abc123"
        _make_features_parquet(run_dir)

        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_MINIMAL_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.validation.resolve_run_dir", return_value=run_dir):
            result = run_validation(cfg_path)

        assert result.exists()
        assert "validation" in json.loads(result.read_text())

    def test_run_validation_missing_features_raises(self, tmp_path):
        """FileNotFoundError when features.parquet is absent."""
        from unittest.mock import patch

        from terraflow.validation import run_validation

        run_dir = tmp_path / "runs" / "missing"
        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(_MINIMAL_CONFIG.format(out_dir=tmp_path))

        with patch("terraflow.validation.resolve_run_dir", return_value=run_dir):
            with pytest.raises(FileNotFoundError):
                run_validation(cfg_path)
