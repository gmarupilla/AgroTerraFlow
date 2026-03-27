"""Tests for Stage 2 — Monte Carlo uncertainty propagation.

Covers:
- suitability_score_array: vectorized scoring correctness and shape
- MC columns appear in features.parquet when kriging + uncertainty_samples > 0
- score_ci_low <= score <= score_ci_high for every cell
- uncertainty block present in report.json with expected keys
- No MC columns when uncertainty_samples=0 (default)
- No MC columns when uncertainty_samples > 0 but no kriging (warns, skips)
- MC results are deterministic across identical runs
"""

import json
import textwrap
from pathlib import Path

import numpy as np
import pytest

from terraflow.config import ModelParams
from terraflow.model import suitability_score, suitability_score_array


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_params(**overrides: object) -> ModelParams:
    base: dict[str, object] = dict(
        v_min=0.0, v_max=255.0,
        t_min=0.0, t_max=40.0,
        r_min=0.0, r_max=300.0,
        w_v=0.4, w_t=0.3, w_r=0.3,
    )
    base.update(overrides)
    return ModelParams(**base)  # type: ignore[arg-type]


def _write_kriging_config(
    cfg_file: Path,
    raster: Path,
    climate: Path,
    out_dir: Path,
    uncertainty_samples: int = 0,
) -> Path:
    cfg = textwrap.dedent(f"""
        raster_path: "{raster}"
        climate_csv: "{climate}"
        output_dir: "{out_dir}"

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


def _write_linear_config(
    cfg_file: Path,
    raster: Path,
    climate: Path,
    out_dir: Path,
    uncertainty_samples: int = 200,
) -> Path:
    cfg = textwrap.dedent(f"""
        raster_path: "{raster}"
        climate_csv: "{climate}"
        output_dir: "{out_dir}"

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
          interpolation_method: "linear"

        max_cells: 5
    """)
    cfg_file.write_text(cfg, encoding="utf-8")
    return cfg_file


# ---------------------------------------------------------------------------
# suitability_score_array unit tests
# ---------------------------------------------------------------------------

class TestSuitabilityScoreArray:
    def test_scalar_equivalence(self):
        """suitability_score_array should match suitability_score element-wise."""
        params = _default_params()
        v = np.array([10.0, 128.0, 200.0])
        t = np.array([5.0, 20.0, 35.0])
        r = np.array([50.0, 150.0, 250.0])

        arr_result = suitability_score_array(v, t, r, params)
        scalar_results = [suitability_score(float(v[i]), float(t[i]), float(r[i]), params) for i in range(len(v))]

        np.testing.assert_allclose(arr_result, scalar_results, atol=1e-12)

    def test_output_clipped_to_unit_interval(self):
        params = _default_params()
        # Extreme out-of-range values
        v = np.array([-999.0, 999.0])
        t = np.array([-999.0, 999.0])
        r = np.array([-999.0, 999.0])

        result = suitability_score_array(v, t, r, params)
        assert (result >= 0.0).all()
        assert (result <= 1.0).all()

    def test_2d_shape_preserved(self):
        params = _default_params()
        v = np.full((4, 10), 100.0)
        t = np.full((4, 10), 20.0)
        r = np.full((4, 10), 150.0)

        result = suitability_score_array(v, t, r, params)
        assert result.shape == (4, 10)

    def test_monotonic_in_v_index(self):
        params = _default_params()
        v_low = np.array([10.0])
        v_high = np.array([200.0])
        t = np.array([20.0])
        r = np.array([150.0])

        assert suitability_score_array(v_high, t, r, params) >= suitability_score_array(v_low, t, r, params)

    def test_degenerate_range(self):
        """When v_min == v_max, vegetation contribution is 0."""
        params = _default_params(v_min=100.0, v_max=100.0)
        v = np.array([100.0, 50.0, 200.0])
        t = np.zeros(3)
        r = np.zeros(3)

        result = suitability_score_array(v, t, r, params)
        # With t=0, r=0 → normalized to 0 → score = 0 regardless of v
        np.testing.assert_allclose(result, 0.0, atol=1e-12)


# ---------------------------------------------------------------------------
# Pipeline integration tests
# ---------------------------------------------------------------------------

class TestMCColumnsPresent:
    def test_ci_columns_in_features_parquet(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """score_ci_low and score_ci_high appear when kriging + uncertainty_samples > 0."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=100,
        )
        df = run_pipeline(cfg)

        assert "score_ci_low" in df.columns
        assert "score_ci_high" in df.columns

    def test_ci_bounds_bracket_point_estimate(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """5th pct ≤ point score ≤ 95th pct for every sampled cell."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=200,
        )
        df = run_pipeline(cfg)

        assert (df["score_ci_low"] <= df["score"] + 1e-9).all(), (
            "score_ci_low must be <= point score"
        )
        assert (df["score_ci_high"] >= df["score"] - 1e-9).all(), (
            "score_ci_high must be >= point score"
        )
        assert (df["score_ci_low"] <= df["score_ci_high"]).all()

    def test_ci_columns_in_valid_range(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """CI bounds must be in [0, 1]."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=100,
        )
        df = run_pipeline(cfg)

        assert df["score_ci_low"].between(0.0, 1.0).all()
        assert df["score_ci_high"].between(0.0, 1.0).all()


class TestMCColumnsAbsent:
    def test_no_ci_columns_when_samples_zero(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """Default config (uncertainty_samples=0) must not produce CI columns."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=0,
        )
        df = run_pipeline(cfg)

        assert "score_ci_low" not in df.columns
        assert "score_ci_high" not in df.columns

    def test_no_ci_columns_without_kriging(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """uncertainty_samples > 0 but linear interpolation → no CI columns (warns)."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_linear_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=200,
        )
        df = run_pipeline(cfg)

        assert "score_ci_low" not in df.columns
        assert "score_ci_high" not in df.columns


class TestReportUncertaintyBlock:
    def test_uncertainty_block_in_report_json(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """report.json has an 'uncertainty' key with expected structure."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=150,
        )
        df = run_pipeline(cfg)

        run_dir = Path(df.attrs["run_dir"])
        report = json.loads((run_dir / "report.json").read_text())

        assert "uncertainty" in report
        unc = report["uncertainty"]
        assert unc["method"] == "monte_carlo"
        assert unc["n_samples"] == 150
        assert unc["ci_low_pct"] == 5
        assert unc["ci_high_pct"] == 95
        assert "mean_temp" in unc["perturbed_variables"]
        assert "total_rain" in unc["perturbed_variables"]
        assert "score_ci_low_mean" in unc
        assert "score_ci_high_mean" in unc
        assert "mean_ci_width" in unc
        assert unc["mean_ci_width"] >= 0.0

    def test_no_uncertainty_block_when_samples_zero(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """report.json must not have 'uncertainty' when uncertainty_samples=0."""
        from terraflow.pipeline import run_pipeline

        out_dir = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out_dir,
            uncertainty_samples=0,
        )
        df = run_pipeline(cfg)

        run_dir = Path(df.attrs["run_dir"])
        report = json.loads((run_dir / "report.json").read_text())

        assert "uncertainty" not in report


class TestMCDeterminism:
    def test_identical_ci_across_reruns(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """Re-running the same config after clearing the cache yields bit-identical CIs."""
        from terraflow.pipeline import run_pipeline

        out = tmp_path / "out"
        cfg = _write_kriging_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv_dense,
            out,
            uncertainty_samples=100,
        )

        # First execution
        df1 = run_pipeline(cfg)
        ci_low_1 = df1.sort_values("cell_id")["score_ci_low"].to_numpy()
        ci_high_1 = df1.sort_values("cell_id")["score_ci_high"].to_numpy()

        # Clear cached artifacts to force a fresh execution with the same seed.
        run_dir = Path(df1.attrs["run_dir"])
        for artifact in ("features.parquet", "manifest.json", "report.json"):
            (run_dir / artifact).unlink()

        # Second execution — must reproduce identical CIs from the seeded RNG.
        df2 = run_pipeline(cfg)
        ci_low_2 = df2.sort_values("cell_id")["score_ci_low"].to_numpy()
        ci_high_2 = df2.sort_values("cell_id")["score_ci_high"].to_numpy()

        np.testing.assert_array_equal(ci_low_1, ci_low_2)
        np.testing.assert_array_equal(ci_high_1, ci_high_2)


# ---------------------------------------------------------------------------
# MC edge case tests
# ---------------------------------------------------------------------------


class TestMCEdgeCases:
    def test_mc_zero_variance_ci_collapsed(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
        monkeypatch,
    ):
        """When kriging std is zero everywhere, MC CI width must collapse to zero."""
        from terraflow.climate import ClimateInterpolator
        from terraflow.pipeline import run_pipeline

        _orig_interpolate = ClimateInterpolator.interpolate

        def _zero_std_interpolate(self, lats, lons):
            result = _orig_interpolate(self, lats, lons)
            for col in result.columns:
                if col.endswith("_krig_std"):
                    result[col] = 0.0
            return result

        monkeypatch.setattr(ClimateInterpolator, "interpolate", _zero_std_interpolate)

        cfg_path = _write_kriging_config(
            tmp_path / "cfg.yml", synthetic_raster, synthetic_climate_csv_dense,
            tmp_path / "out", uncertainty_samples=50,
        )
        df = run_pipeline(cfg_path)

        assert "score_ci_low" in df.columns
        assert "score_ci_high" in df.columns
        np.testing.assert_array_almost_equal(
            df["score_ci_low"].to_numpy(), df["score_ci_high"].to_numpy(), decimal=9
        )

    def test_mc_single_sample_ci_width_zero(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv_dense: Path,
    ):
        """uncertainty_samples=1 produces CI width of zero (single draw = point estimate)."""
        from terraflow.pipeline import run_pipeline

        cfg_path = _write_kriging_config(
            tmp_path / "cfg.yml", synthetic_raster, synthetic_climate_csv_dense,
            tmp_path / "out", uncertainty_samples=1,
        )
        df = run_pipeline(cfg_path)

        assert "score_ci_low" in df.columns
        assert "score_ci_high" in df.columns
        ci_width = (df["score_ci_high"] - df["score_ci_low"]).abs()
        assert ci_width.max() < 1e-9, (
            f"CI width should be ~0 with 1 MC sample, got max={ci_width.max()}"
        )
