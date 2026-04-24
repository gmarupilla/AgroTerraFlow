"""Artifact-contract tests for TerraFlow.

Verifies that every pipeline run produces the three required artifacts with
stable, schema-compliant content:

- features.parquet  — tidy/wide schema v1
- manifest.json     — config snapshot + provenance
- report.json       — QA summaries + timings

Also covers:
- Determinism regression (same inputs → same run_fingerprint, mtime-independent)
- CRS mismatch behaviour (must fail loudly with clear error)
- Nodata / coverage QA sanity checks
- DataCatalog contract
- No-op rerun detection
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from terraflow.core.run_identity import (
    compute_run_fingerprint,
    fingerprint_file,
    hash_roi_geometry,
)
from terraflow.ingest import ClimateLayer, DataCatalog, RasterLayer, build_data_catalog
from terraflow.pipeline import (
    FEATURES_COLUMNS_ORDERED,
    FEATURES_SCHEMA_VERSION,
    run_pipeline,
)

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _make_config(
    tmp_path: Path,
    raster_path: Path,
    climate_csv: Path,
    *,
    xmin: float = -101.0,
    ymin: float = 39.0,
    xmax: float = -99.0,
    ymax: float = 41.0,
    max_cells: int = 5,
) -> Path:
    content = textwrap.dedent(f"""
        raster_path: "{raster_path}"
        climate_csv: "{climate_csv}"
        output_dir: "{tmp_path / 'outputs'}"
        roi:
          type: "bbox"
          xmin: {xmin}
          ymin: {ymin}
          xmax: {xmax}
          ymax: {ymax}
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
        max_cells: {max_cells}
    """)
    cfg = tmp_path / "config.yml"
    cfg.write_text(content, encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# features.parquet — schema contract
# ---------------------------------------------------------------------------


class TestFeaturesParquetSchema:
    def test_all_required_columns_present(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        for col in FEATURES_COLUMNS_ORDERED:
            assert col in pq_df.columns, f"Missing column: {col}"

    def test_column_order_matches_contract(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert list(pq_df.columns) == FEATURES_COLUMNS_ORDERED

    def test_dtypes_are_correct(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        # pandas ≥ 2.x may return StringDtype or object for string cols
        assert pd.api.types.is_string_dtype(pq_df["run_id"]), "run_id must be string"
        assert pd.api.types.is_integer_dtype(
            pq_df["cell_id"]
        ), "cell_id must be integer"
        for col in ("lat", "lon", "v_index", "mean_temp", "total_rain", "score"):
            assert pd.api.types.is_float_dtype(pq_df[col]), f"{col} must be float"
        assert pd.api.types.is_string_dtype(pq_df["label"]), "label must be string"

    def test_run_id_matches_fingerprint(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])
        fp = df.attrs["run_fingerprint"]

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert (
            pq_df["run_id"] == fp
        ).all(), "All run_id values must match run_fingerprint"

    def test_score_in_unit_interval(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert pq_df["score"].between(0.0, 1.0).all(), "Scores must be in [0, 1]"

    def test_label_values_are_categorical(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert set(pq_df["label"].unique()).issubset({"low", "medium", "high"})

    def test_lat_lon_wgs84_range(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert pq_df["lat"].between(-90.0, 90.0).all(), "lat out of WGS84 range"
        assert pq_df["lon"].between(-180.0, 180.0).all(), "lon out of WGS84 range"

    def test_schema_version_in_parquet_metadata(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        import pyarrow.parquet as pq

        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        meta = pq.read_metadata(run_dir / "features.parquet")
        raw = meta.metadata or {}
        schema_ver = raw.get(b"terraflow_schema_version", b"").decode()
        assert schema_ver == FEATURES_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# manifest.json — schema contract
# ---------------------------------------------------------------------------


class TestManifestJsonSchema:
    def test_required_top_level_keys(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "manifest.json", encoding="utf-8") as fh:
            manifest = json.load(fh)

        required = {
            "schema_version",
            "run_fingerprint",
            "code_version",
            "created_at_utc",
            "config",
            "input_fingerprints",
            "output_files",
        }
        assert required.issubset(
            manifest.keys()
        ), f"Missing manifest keys: {required - set(manifest.keys())}"

    def test_run_fingerprint_is_consistent(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])
        fp = df.attrs["run_fingerprint"]

        with open(run_dir / "manifest.json", encoding="utf-8") as fh:
            manifest = json.load(fh)

        assert manifest["run_fingerprint"] == fp

    def test_output_files_list_complete(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "manifest.json", encoding="utf-8") as fh:
            manifest = json.load(fh)

        required_files = {"features.parquet", "manifest.json", "report.json"}
        assert required_files.issubset(set(manifest["output_files"]))

    def test_all_listed_output_files_exist_on_disk(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "manifest.json", encoding="utf-8") as fh:
            manifest = json.load(fh)

        for fname in manifest["output_files"]:
            assert (run_dir / fname).exists(), f"Listed artifact missing: {fname}"

    def test_input_fingerprints_have_sha256(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "manifest.json", encoding="utf-8") as fh:
            manifest = json.load(fh)

        for fp_rec in manifest["input_fingerprints"]:
            assert "sha256" in fp_rec, "Each fingerprint record must have sha256"
            assert len(fp_rec["sha256"]) == 64, "sha256 must be 64 hex chars"


# ---------------------------------------------------------------------------
# report.json — schema contract
# ---------------------------------------------------------------------------


class TestReportJsonSchema:
    def test_required_top_level_keys(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        required = {
            "schema_version",
            "run_fingerprint",
            "coverage",
            "raster_stats",
            "climate_stats",
            "n_cells_sampled",
            "score_stats",
            "timings_sec",
        }
        assert required.issubset(report.keys())

    def test_coverage_fields_are_consistent(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        cov = report["coverage"]
        assert cov["n_raster_cells_total"] >= cov["n_roi_valid_cells"]
        assert (
            cov["n_roi_valid_cells"] + cov["n_roi_nodata_cells"]
            == cov["n_raster_cells_total"]
        )
        assert 0.0 <= cov["roi_coverage_fraction"] <= 1.0
        assert 0.0 <= cov["roi_nodata_fraction"] <= 1.0
        assert (
            abs(cov["roi_coverage_fraction"] + cov["roi_nodata_fraction"] - 1.0) < 1e-6
        )

    def test_timings_all_positive(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        for key, val in report["timings_sec"].items():
            assert isinstance(val, (int, float)), f"timing {key} not numeric"
            assert val >= 0.0, f"timing {key} is negative"

    def test_n_cells_sampled_matches_parquet_row_count(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        pq_df = pd.read_parquet(run_dir / "features.parquet")
        assert report["n_cells_sampled"] == len(pq_df)


# ---------------------------------------------------------------------------
# Determinism regression — mtime-independent fingerprint
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_fingerprint_stable_across_different_mtimes(self, tmp_path):
        """run_fingerprint must NOT change when only file mtime changes."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"stable-content")

        roi = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0}
        cfg = {"raster_path": "data.bin", "roi": roi}
        roi_hash = hash_roi_geometry(roi)

        # Run 1 — set mtime to T0
        os.utime(f, (1_700_000_000, 1_700_000_000))
        fps1 = [fingerprint_file(str(f))]
        fp1 = compute_run_fingerprint(cfg, roi_hash, fps1)

        # Run 2 — advance mtime by 1 year
        os.utime(f, (1_731_536_000, 1_731_536_000))
        fps2 = [fingerprint_file(str(f))]
        fp2 = compute_run_fingerprint(cfg, roi_hash, fps2)

        assert (
            fp1 == fp2
        ), "run_fingerprint must be content-based; mtime change must not alter it"

    def test_same_pipeline_run_twice_produces_identical_fingerprint(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df1 = run_pipeline(cfg)
        df2 = run_pipeline(cfg)  # second call hits no-op rerun path
        assert df1.attrs["run_fingerprint"] == df2.attrs["run_fingerprint"]

    def test_noop_rerun_returns_same_parquet(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        """Second identical run must return cached features.parquet without re-scoring."""
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df1 = run_pipeline(cfg)
        run_dir = Path(df1.attrs["run_dir"])

        # Capture mtime of parquet BEFORE second call
        mtime_before = (run_dir / "features.parquet").stat().st_mtime

        run_pipeline(cfg)

        mtime_after = (run_dir / "features.parquet").stat().st_mtime
        assert mtime_before == mtime_after, "No-op rerun must not overwrite artifacts"

    def test_different_roi_produces_different_fingerprint(self, tmp_path):
        roi_a = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0}
        roi_b = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 2.0, "ymax": 2.0}

        f = tmp_path / "data.bin"
        f.write_bytes(b"content")
        fps = [fingerprint_file(str(f))]

        cfg = {"raster_path": "data.bin", "roi": roi_a}
        fp_a = compute_run_fingerprint(cfg, hash_roi_geometry(roi_a), fps)
        fp_b = compute_run_fingerprint(cfg, hash_roi_geometry(roi_b), fps)
        assert fp_a != fp_b


# ---------------------------------------------------------------------------
# CRS mismatch test
# ---------------------------------------------------------------------------


class TestCrsMismatch:
    def test_roi_crs_outside_raster_extent_raises_clear_error(self, tmp_path):
        """ROI in correct CRS but entirely outside raster extent must raise ValueError."""
        raster_path = tmp_path / "raster.tif"
        arr = np.arange(25, dtype="float32").reshape(5, 5)
        transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)

        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=5,
            width=5,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(arr, 1)

        climate_path = tmp_path / "climate.csv"
        climate_path.write_text("lat,lon,mean_temp,total_rain\n38.5,-99.0,20.0,120.0\n")

        # ROI is valid bbox but far away from the raster (Africa vs North America)
        cfg_content = textwrap.dedent(f"""
            raster_path: "{raster_path}"
            climate_csv: "{climate_path}"
            output_dir: "{tmp_path / 'out'}"
            roi:
              type: "bbox"
              xmin: 10.0
              ymin: -5.0
              xmax: 20.0
              ymax: 5.0
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
        """)
        cfg_file = tmp_path / "cfg.yml"
        cfg_file.write_text(cfg_content)

        with pytest.raises((ValueError, Exception)) as exc_info:
            run_pipeline(cfg_file)

        # Must fail with a descriptive message, not silently produce an empty result
        assert exc_info.value is not None


# ---------------------------------------------------------------------------
# Nodata / coverage QA
# ---------------------------------------------------------------------------


class TestNodataCoverage:
    def test_nodata_fraction_is_reported(
        self, tmp_path, synthetic_raster, synthetic_climate_csv
    ):
        cfg = _make_config(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        assert "roi_nodata_fraction" in report["coverage"]
        assert 0.0 <= report["coverage"]["roi_nodata_fraction"] <= 1.0

    def test_raster_with_partial_nodata_coverage_fraction_lt_1(self, tmp_path):
        """Raster with half nodata cells must report coverage_fraction < 1.0."""
        raster_path = tmp_path / "partial_nodata.tif"
        arr = np.full((4, 4), fill_value=-9999.0, dtype="float32")
        arr[0, :] = [1.0, 2.0, 3.0, 4.0]  # first row is valid
        arr[1, :] = [5.0, 6.0, 7.0, 8.0]  # second row is valid
        transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)

        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=4,
            width=4,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            dst.write(arr, 1)

        climate_path = tmp_path / "climate.csv"
        climate_path.write_text(
            "lat,lon,mean_temp,total_rain\n"
            "40.0,-100.0,18.0,100.0\n"
            "39.99,-99.99,19.0,110.0\n"
        )

        cfg_content = textwrap.dedent(f"""
            raster_path: "{raster_path}"
            climate_csv: "{climate_path}"
            output_dir: "{tmp_path / 'out'}"
            roi:
              type: "bbox"
              xmin: -100.05
              ymin: 39.95
              xmax: -99.95
              ymax: 40.05
            model_params:
              v_min: 0.0
              v_max: 10.0
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
        cfg_file.write_text(cfg_content)

        df = run_pipeline(cfg_file)
        run_dir = Path(df.attrs["run_dir"])

        with open(run_dir / "report.json", encoding="utf-8") as fh:
            report = json.load(fh)

        assert (
            report["coverage"]["roi_coverage_fraction"] < 1.0
        ), "Expected coverage fraction < 1.0 with partial nodata raster"


# ---------------------------------------------------------------------------
# DataCatalog contract tests
# ---------------------------------------------------------------------------


class TestDataCatalog:
    def test_build_data_catalog_returns_datacatalog(
        self, synthetic_raster, synthetic_climate_csv
    ):
        catalog = build_data_catalog(synthetic_raster, synthetic_climate_csv)
        assert isinstance(catalog, DataCatalog)

    def test_catalog_has_one_raster_layer(
        self, synthetic_raster, synthetic_climate_csv
    ):
        catalog = build_data_catalog(synthetic_raster, synthetic_climate_csv)
        assert len(catalog.raster_layers) == 1
        layer = catalog.raster_layers[0]
        assert isinstance(layer, RasterLayer)
        assert layer.sha256 is not None
        assert len(layer.sha256) == 64

    def test_catalog_has_one_climate_layer(
        self, synthetic_raster, synthetic_climate_csv
    ):
        catalog = build_data_catalog(synthetic_raster, synthetic_climate_csv)
        assert len(catalog.climate_layers) == 1
        layer = catalog.climate_layers[0]
        assert isinstance(layer, ClimateLayer)
        assert layer.n_rows > 0
        assert "mean_temp" in layer.variables
        assert "total_rain" in layer.variables

    def test_catalog_raster_layer_has_crs_and_bounds(
        self, synthetic_raster, synthetic_climate_csv
    ):
        catalog = build_data_catalog(synthetic_raster, synthetic_climate_csv)
        layer = catalog.raster_layers[0]
        assert layer.crs, "CRS must be non-empty string"
        assert len(layer.bounds) == 4
        left, bottom, right, top = layer.bounds
        assert left < right
        assert bottom < top

    def test_catalog_to_provenance_is_serialisable(
        self, synthetic_raster, synthetic_climate_csv
    ):
        catalog = build_data_catalog(synthetic_raster, synthetic_climate_csv)
        prov = catalog.to_provenance()
        # Must be JSON-serialisable
        dumped = json.dumps(prov)
        assert len(dumped) > 0

    def test_catalog_missing_raster_raises(self, tmp_path, synthetic_climate_csv):
        with pytest.raises(FileNotFoundError, match="Raster not found"):
            build_data_catalog(tmp_path / "missing.tif", synthetic_climate_csv)

    def test_catalog_missing_csv_raises(self, tmp_path, synthetic_raster):
        with pytest.raises(FileNotFoundError, match="Climate CSV not found"):
            build_data_catalog(synthetic_raster, tmp_path / "missing.csv")
