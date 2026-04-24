"""Pipeline orchestration for TerraFlow.

All outputs are written atomically to::

    output_dir/runs/<run_fingerprint>/

Every run produces exactly three artifacts:

* ``features.parquet`` — per-cell suitability features (tidy/wide schema v1)
* ``manifest.json``    — config snapshot, run identity, input provenance
* ``report.json``      — QA summaries, coverage metrics, step timings

A backward-compatible ``results.csv`` is also written to the same run
directory so that callers relying on the previous output path can migrate
at their own pace.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from pyproj.exceptions import CRSError as _PyProjCRSError
from rasterio.crs import CRS
from rasterio.transform import xy

from .climate import ClimateInterpolator
from .config import PipelineConfig, build_config, load_config_dict
from .core.run_identity import (
    canonicalize_config,
    compute_run_fingerprint,
    fingerprint_file,
    hash_roi_geometry,
)
from .exceptions import CRSMismatchError
from .geo import clip_raster_to_roi
from .ingest import build_data_catalog, load_climate_csv, load_raster
from .model import suitability_label, suitability_score, suitability_score_array
from .utils import ensure_dir, logger

#: Tidy/wide schema for features.parquet (v1).
FEATURES_SCHEMA_VERSION = "1"
FEATURES_COLUMNS_ORDERED = [
    "run_id",  # str   — run_fingerprint (links to manifest.json)
    "cell_id",  # int64 — 0-based sampled-cell index (stable within a run)
    "lat",  # float64 — WGS84 latitude (degrees N), always geographic
    "lon",  # float64 — WGS84 longitude (degrees E), always geographic
    "v_index",  # float64 — raster band-1 value (vegetation/crop index)
    "mean_temp",  # float64 — interpolated mean temperature (°C)
    "total_rain",  # float64 — interpolated total rainfall (mm)
    "score",  # float64 — composite suitability score in [0.0, 1.0]
    "label",  # str    — categorical: "low" / "medium" / "high"
]

MANIFEST_SCHEMA_VERSION = "1"
REPORT_SCHEMA_VERSION = "1"


def _expand_input_paths(path_value: str, config_dir: Path) -> List[Path]:
    has_glob = any(char in path_value for char in "*?[")
    if has_glob:
        matches = [
            Path(p) for p in glob.glob(str(config_dir / path_value), recursive=True)
        ]
        if not matches:
            raise FileNotFoundError(f"No files match input pattern: {path_value}")
        return matches

    path = Path(path_value)
    if not path.is_absolute():
        path = config_dir / path
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return [path]


def _collect_input_paths(config_dict: dict, config_dir: Path) -> List[Path]:
    raw_values: List[str] = []

    def add_value(value: object) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for item in value:
                add_value(item)
        elif isinstance(value, (str, Path)):
            raw_values.append(str(value))

    for key in ("raster_path", "soil_raster_path"):
        if key in config_dict:
            add_value(config_dict[key])

    if "climate_csv" in config_dict:
        add_value(config_dict["climate_csv"])

    climate_config = config_dict.get("climate")
    for key in (
        "climate_rasters",
        "climate_raster_glob",
        "climate_stack_glob",
        "climate_raster_paths",
        "weather_rasters",
        "weather_raster_glob",
    ):
        if key in config_dict:
            add_value(config_dict[key])
        if isinstance(climate_config, dict) and key in climate_config:
            add_value(climate_config[key])

    roi_config = config_dict.get("roi")
    if isinstance(roi_config, dict):
        for key in ("geojson_path", "path", "file", "roi_path"):
            if key in roi_config:
                add_value(roi_config[key])
    if "roi_path" in config_dict:
        add_value(config_dict["roi_path"])

    paths: List[Path] = []
    for raw in raw_values:
        paths.extend(_expand_input_paths(raw, config_dir))

    def sort_key(path: Path) -> str:
        try:
            return path.resolve().relative_to(config_dir.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    ordered = sorted(paths, key=sort_key)
    seen: set[Path] = set()
    deduped: List[Path] = []
    for path in ordered:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def _resolve_roi_hash(config_dict: dict, config_dir: Path) -> str:
    roi_config = config_dict.get("roi")
    if isinstance(roi_config, dict):
        if roi_config.get("type") == "bbox":
            return hash_roi_geometry(roi_config)
        for key in ("geojson_path", "path", "file", "roi_path"):
            if key in roi_config:
                roi_path = roi_config[key]
                if isinstance(roi_path, Path):
                    roi_path = str(roi_path)
                if not isinstance(roi_path, str):
                    raise ValueError("ROI path must be a string")
                roi_file = Path(roi_path)
                if not roi_file.is_absolute():
                    roi_file = config_dir / roi_file
                return hash_roi_geometry(str(roi_file))

    if "roi_path" in config_dict:
        roi_path = config_dict["roi_path"]
        if isinstance(roi_path, Path):
            roi_path = str(roi_path)
        if not isinstance(roi_path, str):
            raise ValueError("ROI path must be a string")
        roi_file = Path(roi_path)
        if not roi_file.is_absolute():
            roi_file = config_dir / roi_file
        return hash_roi_geometry(str(roi_file))

    raise ValueError("ROI configuration missing or unsupported")


def resolve_run_dir(config_path: Path | str) -> Path:
    """Return the run directory for a given config without running the pipeline.

    Uses the same fingerprint computation as ``run_pipeline()`` so that
    ``terraflow validate`` always targets the correct run, not the most
    recently modified one.

    Parameters
    ----------
    config_path:
        Path to a TerraFlow YAML config file.

    Returns
    -------
    Path:
        ``output_dir/runs/<fingerprint>`` — may not exist if the pipeline
        has not been run yet.
    """
    config_path = Path(config_path)
    config_dict = load_config_dict(config_path)
    config_dir = config_path.resolve().parent

    for _key in ("raster_path", "climate_csv", "output_dir"):
        if _key in config_dict and config_dict[_key] is not None:
            _p = Path(str(config_dict[_key]))
            if not _p.is_absolute():
                config_dict[_key] = str((config_dir / _p).resolve())

    cfg: PipelineConfig = build_config(config_dict)
    roi_hash = _resolve_roi_hash(config_dict, config_dir)
    input_paths = _collect_input_paths(config_dict, config_dir)
    input_fps = [fingerprint_file(str(p)) for p in input_paths]
    run_fingerprint = compute_run_fingerprint(config_dict, roi_hash, input_fps)

    output_dir = Path(cfg.output_dir)
    return output_dir / "runs" / run_fingerprint


def _aggregate_climate(climate_df: pd.DataFrame) -> Dict[str, float]:
    """
    Aggregate climate data into simple summary statistics (deprecated).

    .. deprecated::
        Use ClimateInterpolator instead for per-cell climate values.

    For now, we use the overall mean temperature and total rainfall.
    This keeps the logic transparent while avoiding hardcoded constants.
    """
    result: Dict[str, float] = {}

    if "mean_temp" in climate_df.columns:
        result["mean_temp"] = float(climate_df["mean_temp"].mean())
    else:
        raise ValueError("Climate CSV must contain a 'mean_temp' column")

    if "total_rain" in climate_df.columns:
        result["total_rain"] = float(climate_df["total_rain"].mean())
    else:
        raise ValueError("Climate CSV must contain a 'total_rain' column")

    return result


def _atomic_write_text(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (write-to-tmp, rename)."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        Path(tmp).rename(path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _atomic_write_parquet(path: Path, df: pd.DataFrame, schema_meta: dict) -> None:
    """Write *df* to *path* as Parquet atomically with custom schema metadata."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, preserve_index=False)
    existing_meta = table.schema.metadata or {}
    merged_meta = {
        **existing_meta,
        b"terraflow_schema_version": FEATURES_SCHEMA_VERSION.encode(),
        **{
            k.encode() if isinstance(k, str) else k: (
                v.encode() if isinstance(v, str) else v
            )
            for k, v in schema_meta.items()
        },
    }
    table = table.replace_schema_metadata(merged_meta)

    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp.parquet")
    os.close(fd)
    try:
        pq.write_table(table, tmp, compression="snappy")
        Path(tmp).rename(path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_features_schema_version(path: Path) -> Optional[str]:
    """Return the ``terraflow_schema_version`` embedded in a Parquet file.

    Returns ``None`` if the file is unreadable or the metadata key is absent.
    Reading only the schema (not the column data) is cheap — a few KB at
    most — and lets cache invalidation happen without materialising the
    DataFrame (#39).
    """
    try:
        import pyarrow.parquet as pq

        schema = pq.read_schema(path)
        meta = schema.metadata or {}
        raw = meta.get(b"terraflow_schema_version")
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception as exc:  # noqa: BLE001 — cache corruption shouldn't crash the run
        logger.warning(
            "Could not read schema version from %s (%s); treating cache as stale.",
            path,
            exc,
        )
        return None


def _get_git_sha() -> Optional[str]:
    """Return the current HEAD SHA, or ``None`` if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _project_cells_to_wgs84(
    sampled_indices: List[tuple[int, int]],
    clipped_transform: rasterio.Affine,
    raster_crs: CRS,
) -> tuple[List[float], List[float]]:
    """Return (cell_lats, cell_lons) in WGS84 for the sampled cell grid positions."""
    native_xs: List[float] = []
    native_ys: List[float] = []
    for row, col in sampled_indices:
        x, y = xy(clipped_transform, row, col, offset="center")
        native_xs.append(float(x))
        native_ys.append(float(y))

    wgs84 = CRS.from_epsg(4326)
    if raster_crs != wgs84:
        coord_tf = Transformer.from_crs(raster_crs, wgs84, always_xy=True)
        lons, lats = coord_tf.transform(native_xs, native_ys)
        return list(lats), list(lons)
    return native_ys, native_xs  # native_xs=lon, native_ys=lat


def _score_cells(
    clipped_data: np.ma.MaskedArray,
    sampled_indices: List[tuple[int, int]],
    cell_lats: List[float],
    cell_lons: List[float],
    cell_climate_df: pd.DataFrame,
    cfg: PipelineConfig,
    run_fingerprint: str,
) -> tuple[pd.DataFrame, List[str]]:
    """Score each sampled cell and return (features DataFrame, kriging std col names)."""
    krig_std_cols = [c for c in cell_climate_df.columns if c.endswith("_krig_std")]
    records: List[Dict[str, Any]] = []

    for cell_id, (row, col) in enumerate(sampled_indices):
        v_index = float(clipped_data[row, col])
        mean_temp = float(cell_climate_df.iloc[cell_id]["mean_temp"])
        total_rain = float(cell_climate_df.iloc[cell_id]["total_rain"])
        score = suitability_score(
            v_index=v_index,
            mean_temp=mean_temp,
            total_rain=total_rain,
            params=cfg.model_params,
        )
        record: Dict[str, Any] = {
            "run_id": run_fingerprint,
            "cell_id": cell_id,
            "lat": cell_lats[cell_id],
            "lon": cell_lons[cell_id],
            "v_index": v_index,
            "mean_temp": mean_temp,
            "total_rain": total_rain,
            "score": score,
            "label": suitability_label(score),
        }
        for ksc in krig_std_cols:
            record[ksc] = float(cell_climate_df.iloc[cell_id][ksc])
        records.append(record)

    df = pd.DataFrame.from_records(records)
    return df, krig_std_cols


def _apply_monte_carlo(
    df: pd.DataFrame,
    krig_std_cols: List[str],
    cfg: PipelineConfig,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, List[str]]:
    """Add Monte Carlo CI columns to *df* if configured; returns updated df and new col names.

    Requires uncertainty_samples > 0 and kriging std columns present.
    Perturbs mean_temp and total_rain using per-cell kriging std, then scores
    each draw to derive 5th/95th percentile confidence intervals on the
    suitability score.
    """
    n_mc = cfg.model_params.uncertainty_samples
    if n_mc <= 0 or not krig_std_cols:
        if n_mc > 0:
            logger.warning(
                f"uncertainty_samples={n_mc} but no kriging std columns available; "
                "skipping Monte Carlo. Set interpolation_method='kriging' to enable."
            )
        return df, []

    n_cells = len(df)
    v_arr = df["v_index"].to_numpy()
    temp_arr = df["mean_temp"].to_numpy()
    rain_arr = df["total_rain"].to_numpy()
    # Clip std to ≥ 0 (kriging variance is non-negative but may have
    # tiny floating-point negatives at station locations).
    temp_std = np.maximum(df["mean_temp_krig_std"].to_numpy(), 0.0)
    rain_std = np.maximum(df["total_rain_krig_std"].to_numpy(), 0.0)

    # Shape: (n_cells, n_mc) — rng continues deterministic stream.
    temp_mc = rng.normal(temp_arr[:, None], temp_std[:, None], (n_cells, n_mc))
    rain_mc = rng.normal(rain_arr[:, None], rain_std[:, None], (n_cells, n_mc))
    # v_index has no per-cell uncertainty estimate; broadcast constant.
    v_mc = np.broadcast_to(v_arr[:, None], (n_cells, n_mc))

    scores_mc = suitability_score_array(v_mc, temp_mc, rain_mc, cfg.model_params)
    df["score_ci_low"] = np.percentile(scores_mc, 5, axis=1)
    df["score_ci_high"] = np.percentile(scores_mc, 95, axis=1)
    logger.info(
        f"Monte Carlo uncertainty propagation complete: {n_mc} samples per cell"
    )
    return df, ["score_ci_low", "score_ci_high"]


def _build_report(
    run_fingerprint: str,
    clipped_data: np.ma.MaskedArray,
    climate_df: pd.DataFrame,
    df: pd.DataFrame,
    n_cells_sampled: int,
    n_total_cells: int,
    n_valid_cells: int,
    n_nodata_cells: int,
    interpolator: "ClimateInterpolator",
    mc_ci_cols: List[str],
    n_mc: int,
    timings: Dict[str, float],
) -> Dict[str, Any]:
    """Build the report.json payload."""
    raster_vals = clipped_data.compressed().astype("float64")
    climate_var_cols = [c for c in climate_df.columns if c not in ("lat", "lon")]
    climate_var_stats: Dict[str, Any] = {
        var: {
            "mean": float(col.mean()) if len(col := climate_df[var].dropna()) else None,
            "min": float(col.min()) if len(col) else None,
            "max": float(col.max()) if len(col) else None,
            "n_nodata": int(climate_df[var].isna().sum()),
        }
        for var in climate_var_cols
    }
    scores_arr = df["score"].to_numpy()

    report: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_fingerprint": run_fingerprint,
        "coverage": {
            "n_raster_cells_total": n_total_cells,
            "n_roi_valid_cells": n_valid_cells,
            "n_roi_nodata_cells": n_nodata_cells,
            "roi_coverage_fraction": (
                round(n_valid_cells / n_total_cells, 6) if n_total_cells else 0.0
            ),
            "roi_nodata_fraction": (
                round(n_nodata_cells / n_total_cells, 6) if n_total_cells else 0.0
            ),
        },
        "raster_stats": {
            "count": int(raster_vals.size),
            "mean": float(raster_vals.mean()) if raster_vals.size else None,
            "std": float(raster_vals.std(ddof=1)) if raster_vals.size > 1 else 0.0,
            "min": float(raster_vals.min()) if raster_vals.size else None,
            "max": float(raster_vals.max()) if raster_vals.size else None,
        },
        "climate_stats": {"n_rows": len(climate_df), "variables": climate_var_stats},
        "n_cells_sampled": n_cells_sampled,
        "score_stats": {
            "mean": float(scores_arr.mean()) if len(scores_arr) else None,
            "std": float(scores_arr.std(ddof=1)) if len(scores_arr) > 1 else 0.0,
            "min": float(scores_arr.min()) if len(scores_arr) else None,
            "max": float(scores_arr.max()) if len(scores_arr) else None,
        },
        "timings_sec": timings,
    }

    if interpolator.cv_metrics:
        report["kriging_loocv"] = {
            var: round(stats["rmse"], 6)
            for var, stats in interpolator.cv_metrics.get("per_variable", {}).items()
            if stats.get("rmse") is not None
        }
        report["interpolation_cv"] = interpolator.cv_metrics

    if interpolator.variogram_params:
        report["kriging_diagnostics"] = interpolator.variogram_params

    if interpolator.fallback_to_mean:
        fallback_by_var = dict(interpolator.fallback_cells_by_variable)
        total_fallback = int(sum(fallback_by_var.values()))
        report["interpolation_fallback"] = {
            "fallback_cells_by_variable": fallback_by_var,
            "fallback_cells_total": total_fallback,
            "n_cells_sampled": int(n_cells_sampled),
        }
        if n_cells_sampled > 0:
            for var, count in fallback_by_var.items():
                ratio = count / n_cells_sampled
                if ratio > 0.10:
                    logger.warning(
                        "Variable '%s' required fallback-to-mean for %d/%d cells "
                        "(%.1f%%); spatial coverage is poor for this variable (#38).",
                        var,
                        count,
                        n_cells_sampled,
                        ratio * 100,
                    )

    if mc_ci_cols:
        ci_low = df["score_ci_low"].to_numpy()
        ci_high = df["score_ci_high"].to_numpy()
        report["uncertainty"] = {
            "method": "monte_carlo",
            "n_samples": n_mc,
            "perturbed_variables": ["mean_temp", "total_rain"],
            "ci_low_pct": 5,
            "ci_high_pct": 95,
            "score_ci_low_mean": float(ci_low.mean()),
            "score_ci_high_mean": float(ci_high.mean()),
            "mean_ci_width": float((ci_high - ci_low).mean()),
        }

    return report


def run_pipeline(config_path: str | Path) -> pd.DataFrame:
    """Run the end-to-end pipeline and return a DataFrame of results.

    Uses spatially-aware climate data matching to apply per-cell climate values
    based on the configured strategy (spatial interpolation or index-based
    matching).

    Parameters
    ----------
    config_path:
        Path to YAML configuration file.

    Returns
    -------
    pd.DataFrame:
        Results table with columns: run_id, cell_id, lat, lon, v_index,
        mean_temp, total_rain, score, label.  ``df.attrs["run_fingerprint"]``
        is set so callers can locate the run directory.

    Raises
    ------
    FileNotFoundError:
        If config file, raster file, or climate CSV does not exist.
    ValueError:
        If configuration is invalid or no valid raster cells found in ROI.

    Notes
    -----
    All artifacts are written atomically under::

        output_dir/runs/<run_fingerprint>/

    If that directory already contains all three required artifacts
    (``features.parquet``, ``manifest.json``, ``report.json``) the pipeline
    detects the identical run and returns early (no-op rerun).
    """
    _t_total_start = time.perf_counter()
    config_path = Path(config_path)
    config_dict = load_config_dict(config_path)
    config_dir = config_path.resolve().parent

    for _key in ("raster_path", "climate_csv", "output_dir"):
        if _key in config_dict and config_dict[_key] is not None:
            _p = Path(str(config_dict[_key]))
            if not _p.is_absolute():
                config_dict[_key] = str((config_dir / _p).resolve())

    cfg: PipelineConfig = build_config(config_dict)
    logger.info(f"Loaded config from {config_path}")
    config_bytes_hash = hashlib.sha256(canonicalize_config(config_dict)).hexdigest()
    roi_hash = _resolve_roi_hash(config_dict, config_dir)
    input_paths = _collect_input_paths(config_dict, config_dir)
    input_fps = [fingerprint_file(str(path)) for path in input_paths]
    run_fingerprint = compute_run_fingerprint(config_dict, roi_hash, input_fps)
    logger.info(
        f"Computed run fingerprint {run_fingerprint} (config={config_bytes_hash}, inputs={len(input_fps)})"
    )

    output_dir = ensure_dir(cfg.output_dir)
    run_dir = ensure_dir(output_dir / "runs" / run_fingerprint)

    _required_artifacts = [
        run_dir / "features.parquet",
        run_dir / "manifest.json",
        run_dir / "report.json",
    ]
    if all(p.exists() for p in _required_artifacts):
        cached_version = _read_features_schema_version(run_dir / "features.parquet")
        if cached_version == FEATURES_SCHEMA_VERSION:
            logger.info(
                f"Detected identical run {run_fingerprint} — all artifacts present, returning cached result."
            )
            df = pd.read_parquet(run_dir / "features.parquet")
            df.attrs["run_fingerprint"] = run_fingerprint
            df.attrs["run_dir"] = str(run_dir)
            return df
        logger.warning(
            "Cached features.parquet at %s has schema_version=%r but current "
            "FEATURES_SCHEMA_VERSION=%r; invalidating cache and recomputing (#39).",
            run_dir,
            cached_version,
            FEATURES_SCHEMA_VERSION,
        )

    _t_catalog_start = time.perf_counter()
    catalog = build_data_catalog(cfg.raster_path, cfg.climate_csv)
    _t_catalog = time.perf_counter() - _t_catalog_start

    _t_load_start = time.perf_counter()
    raster = load_raster(cfg.raster_path)
    raster_crs = raster.crs
    try:
        climate_df = load_climate_csv(cfg.climate_csv)
    except Exception:
        raster.close()
        raise
    _t_load = time.perf_counter() - _t_load_start

    _crs_str = (
        f"EPSG:{raster_crs.to_epsg()}"
        if raster_crs is not None and raster_crs.to_epsg()
        else (str(raster_crs) if raster_crs else "None")
    )
    logger.info(f"Loaded raster: {cfg.raster_path} (CRS: {_crs_str})")
    logger.info(f"Loaded climate data: {cfg.climate_csv}")

    _climate_crs = CRS.from_epsg(4326)
    _climate_crs_str = "EPSG:4326"
    if raster_crs is None:
        raise CRSMismatchError(
            f"Raster '{cfg.raster_path}' has no CRS (raster_crs=None). "
            f"Expected a raster reprojectable to climate CRS '{_climate_crs_str}'."
        )
    try:
        Transformer.from_crs(raster_crs, _climate_crs, always_xy=True)
    except _PyProjCRSError as exc:
        raise CRSMismatchError(
            f"Raster CRS '{raster_crs.to_string()}' is incompatible with "
            f"climate CRS '{_climate_crs_str}': {exc}"
        ) from exc

    _t_clip_start = time.perf_counter()
    clipped_data, clipped_transform = clip_raster_to_roi(
        raster,
        cfg.roi.model_dump(),
        roi_crs=cfg.roi.roi_crs,
        band=cfg.raster_band,
    )
    _t_clip = time.perf_counter() - _t_clip_start
    logger.info("Clipped raster to ROI")

    rows, cols = clipped_data.shape
    n_total_cells = rows * cols
    valid_indices: List[tuple[int, int]] = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if not np.ma.is_masked(clipped_data[r, c])
    ]
    n_valid_cells = len(valid_indices)
    n_nodata_cells = n_total_cells - n_valid_cells

    if not valid_indices:
        raise ValueError("No valid raster cells found in the specified ROI")

    interpolator = ClimateInterpolator(
        climate_df=climate_df,
        strategy=cfg.climate.strategy,
        interpolation_method=cfg.climate.interpolation_method,
        variogram_mode=cfg.climate.variogram_mode,
        cell_id_column=cfg.climate.cell_id_column,
        fallback_to_mean=cfg.climate.fallback_to_mean,
    )
    logger.info(
        f"Initialized climate interpolator with strategy='{cfg.climate.strategy}', method='{interpolator.interpolation_method}'"
    )

    # Derive a deterministic seed from the run fingerprint so that cell
    # selection is bit-reproducible across independent executions with
    # identical inputs — closing the reproducibility gap from v0.2.1.
    _fp_seed = int.from_bytes(
        hashlib.sha256(run_fingerprint.encode()).digest()[:8], "little"
    )
    rng = np.random.default_rng(_fp_seed)
    max_cells = min(cfg.max_cells, n_valid_cells)
    _sample_idx = rng.choice(n_valid_cells, size=max_cells, replace=False)
    sampled_indices = [valid_indices[i] for i in _sample_idx]
    logger.info(f"Sampled {max_cells} cells from {n_valid_cells} valid cells in ROI")

    cell_lats, cell_lons = _project_cells_to_wgs84(
        sampled_indices, clipped_transform, raster_crs
    )

    _t_interp_start = time.perf_counter()
    cell_climate_df = interpolator.interpolate(np.array(cell_lats), np.array(cell_lons))
    _t_interp = time.perf_counter() - _t_interp_start
    logger.info(
        f"Interpolated climate for {len(sampled_indices)} cells using strategy='{cfg.climate.strategy}'"
    )

    _t_score_start = time.perf_counter()
    df, krig_std_cols = _score_cells(
        clipped_data,
        sampled_indices,
        cell_lats,
        cell_lons,
        cell_climate_df,
        cfg,
        run_fingerprint,
    )
    df, mc_ci_cols = _apply_monte_carlo(df, krig_std_cols, cfg, rng)
    df = df[FEATURES_COLUMNS_ORDERED + krig_std_cols + mc_ci_cols]
    _t_score = time.perf_counter() - _t_score_start

    raster.close()
    logger.info("Closed raster dataset")

    _t_write_start = time.perf_counter()

    _atomic_write_parquet(
        run_dir / "features.parquet",
        df,
        schema_meta={"run_fingerprint": run_fingerprint},
    )
    _atomic_write_text(run_dir / "results.csv", df.to_csv(index=False))

    git_sha = _get_git_sha()
    input_fp_records = [
        {
            "path": fp["path"],
            "sha256": fp["sha256"],
            "size_bytes": fp["size_bytes"],
            # mtime kept for human-readable provenance; NOT part of fingerprint
            "mtime": fp.get("mtime"),
        }
        for fp in input_fps
    ]
    manifest: Dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_fingerprint": run_fingerprint,
        "code_version": _get_package_version(),
        "git_sha": git_sha,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config_dict,
        "input_fingerprints": input_fp_records,
        "catalog": catalog.to_provenance(),
        "output_files": [
            "features.parquet",
            "results.csv",
            "manifest.json",
            "report.json",
        ],
    }
    _atomic_write_text(
        run_dir / "manifest.json", json.dumps(manifest, indent=2, default=str)
    )

    _t_total = time.perf_counter() - _t_total_start
    _t_write = time.perf_counter() - _t_write_start

    timings = {
        "build_catalog": round(_t_catalog, 4),
        "load_inputs": round(_t_load, 4),
        "clip_roi": round(_t_clip, 4),
        "interpolate_climate": round(_t_interp, 4),
        "score_cells": round(_t_score, 4),
        "write_outputs": round(_t_write, 4),
        "total": round(_t_total, 4),
    }
    report = _build_report(
        run_fingerprint,
        clipped_data,
        climate_df,
        df,
        n_cells_sampled=len(df),
        n_total_cells=n_total_cells,
        n_valid_cells=n_valid_cells,
        n_nodata_cells=n_nodata_cells,
        interpolator=interpolator,
        mc_ci_cols=mc_ci_cols,
        n_mc=cfg.model_params.uncertainty_samples,
        timings=timings,
    )
    _atomic_write_text(
        run_dir / "report.json", json.dumps(report, indent=2, default=str)
    )

    logger.info(
        f"Artifacts written to {run_dir} (fingerprint={run_fingerprint}, cells={len(df)}, total={_t_total:.2f}s)"
    )

    df.attrs["run_fingerprint"] = run_fingerprint
    df.attrs["run_dir"] = str(run_dir)
    return df


def _get_package_version() -> str:
    try:
        from importlib.metadata import version

        return version("terraflow-agro")
    except Exception:
        try:
            from . import __version__

            return __version__
        except Exception:
            return "unknown"
