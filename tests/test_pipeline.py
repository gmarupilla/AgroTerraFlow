import json
import textwrap
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from terraflow.pipeline import _aggregate_climate, run_pipeline


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

    # Artifacts live under runs/<run_fingerprint>/
    run_fp = df.attrs["run_fingerprint"]
    run_dir = out_dir / "runs" / run_fp
    assert run_dir.is_dir(), f"run_dir missing: {run_dir}"
    assert (run_dir / "features.parquet").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "results.csv").exists()


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
    run_fp = df.attrs["run_fingerprint"]
    run_dir = out_dir / "runs" / run_fp
    assert (run_dir / "results.csv").exists()


def test_pipeline_lat_lon_wgs84_for_projected_raster(tmp_path: Path):
    """Pipeline must output lat/lon in WGS84 degrees even when the input raster
    is in a projected CRS (TERRA-011)."""
    # Build a tiny EPSG:32614 (UTM Zone 14N) raster over Kansas
    raster_path = tmp_path / "utm_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    west_utm, north_utm, pixel_m = 500_000.0, 4_261_000.0, 1_000.0
    transform = from_origin(
        west=west_utm, north=north_utm, xsize=pixel_m, ysize=pixel_m
    )
    crs = CRS.from_epsg(32614)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
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
    assert (
        df["lat"].between(-90.0, 90.0).all()
    ), f"lat out of range: {df['lat'].tolist()}"
    assert (
        df["lon"].between(-180.0, 180.0).all()
    ), f"lon out of range: {df['lon'].tolist()}"
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

    assert result["mean_temp"] == pytest.approx(12.0)
    assert result["total_rain"] == pytest.approx(110.0)


def test_aggregate_climate_missing_columns():
    import pandas as pd

    df = pd.DataFrame({"mean_temp": [10.0, 12.0]})

    with pytest.raises(ValueError, match="total_rain"):
        _aggregate_climate(df)


# ---------------------------------------------------------------------------
# Helpers for kriging / CRS mismatch tests
# ---------------------------------------------------------------------------


def _write_kriging_config(
    cfg_file: Path,
    raster_path: Path,
    climate_csv: Path,
    output_dir: Path,
    uncertainty_samples: int = 0,
) -> Path:
    """Write a pipeline config YAML file with kriging interpolation enabled."""
    cfg = textwrap.dedent(f"""
        raster_path: "{raster_path}"
        climate_csv: "{climate_csv}"
        output_dir: "{output_dir}"

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


def _write_no_crs_raster(path: Path) -> Path:
    """Create a GeoTIFF with no CRS for testing CRSMismatchError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.arange(25, dtype="float32").reshape(5, 5)
    transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype=arr.dtype,
        crs=None,
        transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return path


# ---------------------------------------------------------------------------
# CRS mismatch test
# ---------------------------------------------------------------------------


def test_crs_mismatch_error_none_crs(tmp_path, synthetic_climate_csv_dense):
    """Pipeline raises CRSMismatchError when raster has no CRS."""
    from terraflow.exceptions import CRSMismatchError

    raster_path = _write_no_crs_raster(tmp_path / "data" / "no_crs.tif")
    cfg_path = _write_kriging_config(
        tmp_path / "cfg.yml",
        raster_path,
        synthetic_climate_csv_dense,
        tmp_path / "out",
    )
    with pytest.raises(CRSMismatchError, match="has no CRS"):
        run_pipeline(cfg_path)


# ---------------------------------------------------------------------------
# Kriging diagnostics in report.json test
# ---------------------------------------------------------------------------


def test_kriging_diagnostics_in_report(
    tmp_path, synthetic_raster, synthetic_climate_csv_dense
):
    """report.json includes kriging_diagnostics when kriging is used."""
    cfg_path = _write_kriging_config(
        tmp_path / "cfg.yml",
        synthetic_raster,
        synthetic_climate_csv_dense,
        tmp_path / "out",
    )
    df = run_pipeline(cfg_path)
    run_dir = Path(df.attrs["run_dir"])
    report = json.loads((run_dir / "report.json").read_text())

    assert "kriging_diagnostics" in report
    diag = report["kriging_diagnostics"]
    for key in ("model", "psill", "nugget", "sill", "range_", "range_units"):
        assert key in diag, f"Missing key '{key}' in kriging_diagnostics"
    assert diag["range_units"] == "degrees_geographic"
    assert diag["sill"] == pytest.approx(diag["psill"] + diag["nugget"], rel=1e-4)


def test_resolve_run_dir_returns_deterministic_path(
    tmp_path, synthetic_raster, synthetic_climate_csv
):
    """resolve_run_dir returns the same fingerprinted path as run_pipeline."""
    from terraflow.pipeline import resolve_run_dir

    cfg_path = tmp_path / "cfg.yml"
    out_dir = tmp_path / "out"
    cfg_path.write_text(textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
        output_dir: "{out_dir}"
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
    """))

    run_dir = resolve_run_dir(cfg_path)
    assert run_dir.name  # fingerprint is non-empty
    assert "runs" in run_dir.parts

    # Calling twice returns the same path (deterministic)
    assert resolve_run_dir(cfg_path) == run_dir


class TestInterpolationFallbackReporting:
    """Issue #38: ``report.json`` must break down fallback-to-mean counts
    per climate variable so users can spot variables with poor spatial
    coverage; a WARNING is emitted when any variable exceeds 10 %.
    """

    def _write_cfg(self, tmp_path: Path, raster: Path, climate: Path) -> Path:
        cfg_path = tmp_path / "cfg.yml"
        cfg_path.write_text(textwrap.dedent(f"""
            raster_path: "{raster}"
            climate_csv: "{climate}"
            output_dir: "{tmp_path / 'out'}"
            roi:
              type: bbox
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
            climate:
              strategy: spatial
              interpolation_method: linear
              fallback_to_mean: true
            max_cells: 20
            """))
        return cfg_path

    def test_report_contains_per_variable_fallback_counts(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        cfg_path = self._write_cfg(tmp_path, synthetic_raster, synthetic_climate_csv)
        df = run_pipeline(cfg_path)
        run_dir = Path(df.attrs["run_dir"])
        report = json.loads((run_dir / "report.json").read_text())
        assert "interpolation_fallback" in report
        fb = report["interpolation_fallback"]
        assert "fallback_cells_by_variable" in fb
        assert set(fb["fallback_cells_by_variable"]).issuperset(
            {"mean_temp", "total_rain"}
        )
        assert isinstance(fb["fallback_cells_total"], int)

    def test_fallback_warning_above_10pct(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        caplog,
    ):
        import logging

        # Place climate stations in a tiny non-colinear triangle far from
        # the ROI so every cell lies outside the Delaunay convex hull and
        # linear interpolation returns NaN -> fallback-to-mean for 100 %.
        climate_path = tmp_path / "far_climate.csv"
        climate_path.write_text(
            "lat,lon,mean_temp,total_rain\n"
            "10.0,10.0,15.0,100.0\n"
            "10.1,10.0,16.0,110.0\n"
            "10.0,10.1,17.0,120.0\n"
        )

        caplog.set_level(logging.WARNING, logger="terraflow")
        cfg_path = self._write_cfg(tmp_path, synthetic_raster, climate_path)
        df = run_pipeline(cfg_path)
        run_dir = Path(df.attrs["run_dir"])
        report = json.loads((run_dir / "report.json").read_text())
        fb = report["interpolation_fallback"]
        assert fb["fallback_cells_total"] > 0, (
            f"Expected non-zero fallback cells when stations are far "
            f"from the raster; got report={fb!r}"
        )
        any_gt_10 = any(
            count / fb["n_cells_sampled"] > 0.10
            for count in fb["fallback_cells_by_variable"].values()
        )
        if any_gt_10:
            assert any(
                "fallback-to-mean" in rec.message
                for rec in caplog.records
                if rec.levelno == logging.WARNING
            ), f"Expected >10% fallback warning, caplog records: {caplog.text!r}"


class TestMultiBandRasterSupport:
    """Issue #42: pipeline respects ``raster_band`` config and records it."""

    def _write_multiband_raster(self, tmp_path: Path, n_bands: int = 2) -> Path:
        raster_path = tmp_path / "mb.tif"
        transform = from_origin(west=-100.05, north=40.05, xsize=0.02, ysize=0.02)
        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=5,
            width=5,
            count=n_bands,
            dtype="float32",
            crs=CRS.from_epsg(4326),
            transform=transform,
        ) as dst:
            for b in range(1, n_bands + 1):
                dst.write(np.full((5, 5), float(b * 10), dtype="float32"), b)
        return raster_path

    def _write_cfg(
        self,
        tmp_path: Path,
        raster: Path,
        climate: Path,
        *,
        band: int,
    ) -> Path:
        tmp_path.mkdir(parents=True, exist_ok=True)
        cfg_path = tmp_path / "cfg.yml"
        cfg_path.write_text(textwrap.dedent(f"""
            raster_path: "{raster}"
            raster_band: {band}
            climate_csv: "{climate}"
            output_dir: "{tmp_path / f'out_b{band}'}"
            roi:
              type: bbox
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
              w_v: 1.0
              w_t: 0.0
              w_r: 0.0
            max_cells: 10
            """))
        return cfg_path

    def test_band_selection_changes_pipeline_v_index(
        self,
        tmp_path: Path,
        synthetic_climate_csv: Path,
    ):
        raster = self._write_multiband_raster(tmp_path, n_bands=3)

        df_b1 = run_pipeline(
            self._write_cfg(tmp_path / "c1", raster, synthetic_climate_csv, band=1)
        )
        df_b2 = run_pipeline(
            self._write_cfg(tmp_path / "c2", raster, synthetic_climate_csv, band=2)
        )
        # Band 1 pixel value is 10, band 2 is 20; v_index is the raw pixel.
        assert np.allclose(df_b1["v_index"], 10.0)
        assert np.allclose(df_b2["v_index"], 20.0)

    def test_out_of_range_band_raises(
        self,
        tmp_path: Path,
        synthetic_climate_csv: Path,
    ):
        raster = self._write_multiband_raster(tmp_path, n_bands=2)
        cfg_path = self._write_cfg(tmp_path, raster, synthetic_climate_csv, band=5)
        with pytest.raises(ValueError, match="out of range"):
            run_pipeline(cfg_path)

    def test_manifest_records_selected_band(
        self,
        tmp_path: Path,
        synthetic_climate_csv: Path,
    ):
        raster = self._write_multiband_raster(tmp_path, n_bands=3)
        cfg_path = self._write_cfg(tmp_path, raster, synthetic_climate_csv, band=2)
        df = run_pipeline(cfg_path)
        run_dir = Path(df.attrs["run_dir"])
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["config"]["raster_band"] == 2


class TestCacheSchemaVersionInvalidation:
    """Issue #39: stale ``features.parquet`` with a mismatched
    ``terraflow_schema_version`` must be invalidated so the pipeline
    recomputes, rather than silently returning old artifacts."""

    def _write_cfg(self, tmp_path: Path, raster: Path, climate: Path) -> Path:
        cfg_path = tmp_path / "cfg.yml"
        cfg_path.write_text(textwrap.dedent(f"""
            raster_path: "{raster}"
            climate_csv: "{climate}"
            output_dir: "{tmp_path / 'out'}"
            roi:
              type: bbox
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
            max_cells: 5
            """))
        return cfg_path

    def test_mismatched_schema_version_triggers_rerun(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
        caplog,
    ):
        import logging

        import pyarrow.parquet as pq

        cfg_path = self._write_cfg(tmp_path, synthetic_raster, synthetic_climate_csv)
        df_first = run_pipeline(cfg_path)
        run_dir = Path(df_first.attrs["run_dir"])
        parquet_path = run_dir / "features.parquet"
        mtime_before = parquet_path.stat().st_mtime_ns

        # Rewrite the parquet with a bogus schema_version to simulate a
        # stale cache written by an older TerraFlow release.
        table = pq.read_table(parquet_path)
        stale_meta = dict(table.schema.metadata or {})
        stale_meta[b"terraflow_schema_version"] = b"0"
        table = table.replace_schema_metadata(stale_meta)
        pq.write_table(table, parquet_path, compression="snappy")

        caplog.set_level(logging.WARNING)
        df_second = run_pipeline(cfg_path)

        assert "invalidating cache" in caplog.text.lower()
        mtime_after = parquet_path.stat().st_mtime_ns
        assert mtime_after > mtime_before, (
            "features.parquet should be regenerated when schema_version "
            "is stale, but its mtime did not advance."
        )
        assert df_second.attrs["run_fingerprint"] == df_first.attrs["run_fingerprint"]

    def test_matching_schema_version_hits_cache(
        self,
        tmp_path: Path,
        synthetic_raster: Path,
        synthetic_climate_csv: Path,
    ):
        cfg_path = self._write_cfg(tmp_path, synthetic_raster, synthetic_climate_csv)
        df_first = run_pipeline(cfg_path)
        run_dir = Path(df_first.attrs["run_dir"])
        mtime_before = (run_dir / "features.parquet").stat().st_mtime_ns

        df_second = run_pipeline(cfg_path)
        mtime_after = (run_dir / "features.parquet").stat().st_mtime_ns

        assert mtime_before == mtime_after  # cache hit, not rewritten
        assert df_second.attrs["run_fingerprint"] == df_first.attrs["run_fingerprint"]


# ---------------------------------------------------------------------------
# Climate-impact orchestration (#138f) — run_pipeline auto-invocation
# ---------------------------------------------------------------------------


def _write_climate_impact_timeseries(path: Path) -> Path:
    """3 stations × 730 days of synthetic daily climate for two scenario windows."""
    import pandas as pd

    dates = pd.date_range("1991-01-01", "1992-12-31", freq="D")
    stations = [("S1", 40.0, -100.0), ("S2", 40.01, -99.99), ("S3", 40.02, -99.98)]
    rows = []
    for i, (sid, lat, lon) in enumerate(stations):
        for d in dates:
            rows.append(
                {
                    "station_id": sid,
                    "lat": lat,
                    "lon": lon,
                    "date": d,
                    "temperature_c": 15.0 + i + 5.0 * np.sin(2 * np.pi * d.dayofyear / 365),
                    "precipitation_mm": 2.0 + 0.1 * i,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_run_pipeline_writes_climate_features_when_configured(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
):
    """#138f: when temporal_aggregations + scenarios are both set, the
    pipeline auto-invokes ``run_climate_impact_features`` and writes
    ``climate_features.parquet`` alongside ``features.parquet``."""
    import pandas as pd

    ts_csv = _write_climate_impact_timeseries(tmp_path / "ts.csv")
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

        climate:
          timeseries_csv: "{ts_csv}"
          interpolation_method: linear
          temporal_aggregations:
            - kind: annual_mean
            - kind: growing_degree_days
              base_temp_c: 10.0
          scenarios:
            - name: historical
              period: [1991, 1991]
            - name: ssp245
              period: [1992, 1992]

        max_cells: 5
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df = run_pipeline(cfg_file)
    run_dir = Path(df.attrs["run_dir"])

    cf_path = run_dir / "climate_features.parquet"
    assert cf_path.exists(), "climate_features.parquet missing"

    cf = pd.read_parquet(cf_path)
    assert "cell_id" in cf.columns
    # 2 rules × 2 scenarios = 4 derived columns
    derived = [c for c in cf.columns if c != "cell_id"]
    assert len(derived) == 4, f"expected 4 derived columns, got {derived}"
    # Each derived column name encodes <rule>__<scenario>
    assert all("__" in c for c in derived)
    # Manifest output_files lists the new artifact
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "climate_features.parquet" in manifest["output_files"]


def test_run_pipeline_cache_requires_climate_features_for_climate_impact_config(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
):
    """The cached-run early-return must require climate_features.parquet
    when the config declares the climate-impact path — otherwise a stale
    historical-only cache would mask a missing artifact."""
    ts_csv = _write_climate_impact_timeseries(tmp_path / "ts.csv")
    out_dir = tmp_path / "outputs"
    cfg_content = textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
        output_dir: "{out_dir}"
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
        climate:
          timeseries_csv: "{ts_csv}"
          interpolation_method: linear
          temporal_aggregations:
            - kind: annual_mean
          scenarios:
            - name: historical
              period: [1991, 1991]
        max_cells: 5
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df_first = run_pipeline(cfg_file)
    run_dir = Path(df_first.attrs["run_dir"])
    cf_path = run_dir / "climate_features.parquet"
    assert cf_path.exists()
    cf_mtime_before = cf_path.stat().st_mtime_ns

    cf_path.unlink()  # delete the new artifact only
    df_second = run_pipeline(cfg_file)
    assert (run_dir / "climate_features.parquet").exists(), (
        "cache early-return masked missing climate_features.parquet"
    )
    cf_mtime_after = (run_dir / "climate_features.parquet").stat().st_mtime_ns
    assert cf_mtime_after >= cf_mtime_before  # regenerated
    assert df_second.attrs["run_fingerprint"] == df_first.attrs["run_fingerprint"]


def test_run_pipeline_climate_impact_relative_timeseries_csv(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
    monkeypatch,
):
    """#138f Codex P2: a relative ``climate.timeseries_csv`` must resolve
    against the config's directory, not the process cwd. Run the pipeline
    from an unrelated cwd to confirm."""
    cfg_dir = tmp_path / "cfgs"
    cfg_dir.mkdir()
    ts_csv = _write_climate_impact_timeseries(cfg_dir / "ts.csv")
    out_dir = tmp_path / "outputs"

    cfg_content = textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
        output_dir: "{out_dir}"
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
        climate:
          timeseries_csv: "{ts_csv.name}"      # RELATIVE — must resolve via cfg dir
          interpolation_method: linear
          temporal_aggregations:
            - kind: annual_mean
          scenarios:
            - name: historical
              period: [1991, 1991]
        max_cells: 5
        """)
    cfg_file = cfg_dir / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    elsewhere = tmp_path / "unrelated_cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    df = run_pipeline(cfg_file)
    run_dir = Path(df.attrs["run_dir"])
    assert (run_dir / "climate_features.parquet").exists()
