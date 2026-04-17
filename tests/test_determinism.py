"""Determinism regression tests.

Verifies that TerraFlow's reproducibility guarantees hold:
- Identical config + inputs → identical run_fingerprint (run_identity contract)
- Identical run_fingerprint → identical sampled cell_ids (seeded sampling contract)

These tests encode the invariants that must never regress.
"""

import textwrap
from pathlib import Path

import pandas as pd


def _write_config(cfg_file: Path, raster: Path, climate: Path, out_dir: Path) -> Path:
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

        max_cells: 3
    """)
    cfg_file.write_text(cfg, encoding="utf-8")
    return cfg_file


class TestSamplingDeterminism:
    """Seeded cell sampling must produce identical cell sets across runs.

    The run_fingerprint encodes the full config (including output_dir), so
    two runs with the same scientific inputs but different output directories
    intentionally produce different fingerprints and — by design — different
    seeds.  To test seeded reproducibility we therefore use the SAME config
    (same output_dir) and clear cached artifacts between the two executions.
    """

    def _run_twice_same_config(
        self,
        tmp_path: Path,
        raster: Path,
        climate: Path,
    ):
        """Run pipeline twice with identical config; clear cache between runs."""
        import shutil

        from terraflow.pipeline import run_pipeline

        shared_out = tmp_path / "shared_out"
        cfg_file = _write_config(tmp_path / "cfg.yml", raster, climate, shared_out)

        df1 = run_pipeline(cfg_file)
        # Delete cached artifacts so the second run recomputes from scratch.
        run_dir = Path(df1.attrs["run_dir"])
        shutil.rmtree(run_dir)

        df2 = run_pipeline(cfg_file)
        return df1, df2

    def test_two_runs_same_inputs_identical_cell_lats_lons(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        """Same config + inputs → same cell lat/lon on every run (seeded sampling)."""
        df1, df2 = self._run_twice_same_config(
            tmp_path, synthetic_raster, synthetic_climate_csv
        )

        assert list(df1["lat"]) == list(df2["lat"]), (
            "Seeded sampling contract violated: same inputs produced different cell lats.\n"
            f"Run 1 lats: {list(df1['lat'])}\n"
            f"Run 2 lats: {list(df2['lat'])}"
        )
        assert list(df1["lon"]) == list(df2["lon"])

    def test_two_runs_same_inputs_identical_scores(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        """Same config + inputs → identical scores across recomputed runs."""
        df1, df2 = self._run_twice_same_config(
            tmp_path, synthetic_raster, synthetic_climate_csv
        )

        pd.testing.assert_frame_equal(
            df1[["lat", "lon", "v_index", "score", "label"]].reset_index(drop=True),
            df2[["lat", "lon", "v_index", "score", "label"]].reset_index(drop=True),
            check_exact=False,
            rtol=1e-9,
        )

    def test_fingerprint_attribute_set(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        """run_pipeline must set df.attrs['run_fingerprint']."""
        from terraflow.pipeline import run_pipeline

        cfg = _write_config(
            tmp_path / "cfg.yml",
            synthetic_raster,
            synthetic_climate_csv,
            tmp_path / "out",
        )
        df = run_pipeline(cfg)
        assert "run_fingerprint" in df.attrs
        assert isinstance(df.attrs["run_fingerprint"], str)
        assert len(df.attrs["run_fingerprint"]) > 0

    def test_fingerprint_stable_across_reruns(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        """Identical config + inputs → identical run_fingerprint on both runs.

        The second run hits the cache and returns early; the fingerprint in
        df.attrs must still match the first run's fingerprint.
        """
        from terraflow.pipeline import run_pipeline

        shared_out = tmp_path / "shared_out"
        cfg = _write_config(
            tmp_path / "cfg.yml", synthetic_raster, synthetic_climate_csv, shared_out
        )

        df1 = run_pipeline(cfg)
        df2 = run_pipeline(cfg)  # cache hit

        assert df1.attrs["run_fingerprint"] == df2.attrs["run_fingerprint"], (
            "run_fingerprint is not stable across identical runs — "
            "run identity contract broken."
        )
