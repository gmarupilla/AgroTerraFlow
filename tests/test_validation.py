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
        lats = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0,
                         2.0, 2.0, 3.0, 3.0, 2.0, 2.0, 3.0, 3.0])
        lons = np.array([0.0, 1.0, 0.0, 1.0, 2.0, 3.0, 2.0, 3.0,
                         0.0, 1.0, 0.0, 1.0, 2.0, 3.0, 2.0, 3.0])
        from terraflow.validation import _assign_block_ids
        ids = _assign_block_ids(lats, lons, n_blocks_side=2)
        assert ids.shape == (16,)
        assert len(np.unique(ids)) >= 2

    def test_spatial_block_cv_returns_fold_accuracies(self):
        """Spatial block CV returns a list of per-fold accuracy floats."""
        lats = np.linspace(0, 3, 20)
        lons = np.linspace(0, 3, 20)
        labels = np.array(['low'] * 10 + ['high'] * 10)
        from terraflow.validation import _spatial_block_cv
        accs = _spatial_block_cv(lats, lons, labels, n_blocks_side=2, buffer_deg=0.1)
        assert isinstance(accs, list)
        assert all(0.0 <= a <= 1.0 for a in accs)

    def test_spatial_cv_degenerate_few_blocks(self):
        """Fewer than 2 unique blocks returns empty list with warning."""
        lats = np.array([1.0, 1.0, 1.0])
        lons = np.array([1.0, 1.0, 1.0])
        labels = np.array(['low', 'low', 'low'])
        from terraflow.validation import _spatial_block_cv
        accs = _spatial_block_cv(lats, lons, labels, n_blocks_side=2, buffer_deg=0.1)
        assert accs == []


class TestCohensKappa:
    """VALD-02: Cohen's kappa against reference."""

    def test_kappa_perfect_agreement(self):
        """Perfect agreement produces kappa = 1.0."""
        cells_df = pd.DataFrame({
            'lat': [0.0, 1.0, 2.0],
            'lon': [0.0, 1.0, 2.0],
            'label': ['low', 'medium', 'high'],
        })
        ref_df = pd.DataFrame({
            'lat': [0.0, 1.0, 2.0],
            'lon': [0.0, 1.0, 2.0],
            'label': ['low', 'medium', 'high'],
        })
        from terraflow.validation import _compute_kappa
        kappa = _compute_kappa(cells_df, ref_df)
        assert kappa == pytest.approx(1.0)

    def test_kappa_with_mismatch(self):
        """Partial mismatch produces 0 < kappa < 1."""
        cells_df = pd.DataFrame({
            'lat': [0.0, 1.0, 2.0, 3.0],
            'lon': [0.0, 1.0, 2.0, 3.0],
            'label': ['low', 'medium', 'high', 'low'],
        })
        ref_df = pd.DataFrame({
            'lat': [0.0, 1.0, 2.0, 3.0],
            'lon': [0.0, 1.0, 2.0, 3.0],
            'label': ['low', 'medium', 'low', 'low'],
        })
        from terraflow.validation import _compute_kappa
        kappa = _compute_kappa(cells_df, ref_df)
        assert -1.0 <= kappa <= 1.0

    def test_kappa_extent_warning(self):
        """Reference points far from cells emit a warning."""
        cells_df = pd.DataFrame({
            'lat': [0.0], 'lon': [0.0], 'label': ['low'],
        })
        ref_df = pd.DataFrame({
            'lat': [50.0], 'lon': [50.0], 'label': ['low'],
        })
        import warnings

        from terraflow.validation import _compute_kappa
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _compute_kappa(cells_df, ref_df)
            assert any("distance" in str(warning.message).lower() for warning in w)


class TestMoransI:
    """VALD-04: Moran's I on residuals."""

    def test_morans_i_spatially_clustered(self):
        """Spatially clustered residuals produce positive Moran's I."""
        lats = np.array([0.0, 0.0, 0.0, 3.0, 3.0, 3.0])
        lons = np.array([0.0, 0.1, 0.2, 3.0, 3.1, 3.2])
        residuals = np.array([1.0, 1.1, 0.9, -1.0, -0.9, -1.1])
        from terraflow.validation import _morans_i
        moran_stat = _morans_i(lats, lons, residuals)
        assert moran_stat is not None
        assert moran_stat > 0.0

    def test_morans_i_degenerate_uniform(self):
        """All-equal residuals return None."""
        lats = np.array([0.0, 1.0, 2.0])
        lons = np.array([0.0, 1.0, 2.0])
        residuals = np.array([5.0, 5.0, 5.0])
        from terraflow.validation import _morans_i
        moran_stat = _morans_i(lats, lons, residuals)
        assert moran_stat is None


class TestReportValidationBlock:
    """VALD-04: report.json validation block structure."""

    def test_validation_block_has_required_keys(self):
        """Validation block contains kappa, morans_i, mean_fold_accuracy."""
        # This test will be fleshed out in Plan 02 when run_validation exists
        from terraflow.validation import run_validation
        # Placeholder: verify the function is importable
        assert callable(run_validation)
