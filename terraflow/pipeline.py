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
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import xy

from .config import PipelineConfig, build_config, load_config_dict
from .core.run_identity import (
    canonicalize_config,
    compute_run_fingerprint,
    fingerprint_file,
    hash_roi_geometry,
)
from .ingest import build_data_catalog, load_raster, load_climate_csv
from .geo import clip_raster_to_roi
from .model import suitability_score, suitability_label
from .climate import ClimateInterpolator
from .utils import ensure_dir, logger

# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

#: Tidy/wide schema for features.parquet (v1).
#:
#: Rationale for wide format: each *row* is one sampled cell (the natural
#: observation unit); each *column* is one feature.  This matches the output
#: contract of rasterstats, GeoPandas zonal_stats, and standard GIS tool
#: pipelines.  Adding new climate variables in future releases appends columns
#: and is backward-compatible via nullable columns.  The ``run_id`` column
#: allows joining across runs and multi-run longitudinal datasets.
FEATURES_SCHEMA_VERSION = "1"
FEATURES_COLUMNS_ORDERED = [
    "run_id",       # str   — run_fingerprint (links to manifest.json)
    "cell_id",      # int64 — 0-based sampled-cell index (stable within a run)
    "lat",          # float64 — WGS84 latitude (degrees N), always geographic
    "lon",          # float64 — WGS84 longitude (degrees E), always geographic
    "v_index",      # float64 — raster band-1 value (vegetation/crop index)
    "mean_temp",    # float64 — interpolated mean temperature (°C)
    "total_rain",   # float64 — interpolated total rainfall (mm)
    "score",        # float64 — composite suitability score in [0.0, 1.0]
    "label",        # str    — categorical: "low" / "medium" / "high"
]

MANIFEST_SCHEMA_VERSION = "1"
REPORT_SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Internal helpers — path resolution
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Deprecated helper (kept for backward-compat; used by existing tests)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Atomic I/O helpers
# ---------------------------------------------------------------------------


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
    # Merge custom schema version metadata into existing Parquet metadata.
    existing_meta = table.schema.metadata or {}
    merged_meta = {
        **existing_meta,
        b"terraflow_schema_version": FEATURES_SCHEMA_VERSION.encode(),
        **{
            k.encode() if isinstance(k, str) else k: v.encode()
            if isinstance(v, str)
            else v
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


# ---------------------------------------------------------------------------
# Git SHA helper (optional; gracefully omitted when unavailable)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------


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

    # Resolve relative input/output paths against the config file's directory.
    for _key in ("raster_path", "climate_csv", "output_dir"):
        if _key in config_dict and config_dict[_key] is not None:
            _p = Path(str(config_dict[_key]))
            if not _p.is_absolute():
                config_dict[_key] = str((config_dir / _p).resolve())

    cfg: PipelineConfig = build_config(config_dict)
    logger.info("Loaded config from %s", config_path)

    # --- Run identity -------------------------------------------------------
    config_bytes_hash = hashlib.sha256(canonicalize_config(config_dict)).hexdigest()
    roi_hash = _resolve_roi_hash(config_dict, config_dir)
    input_paths = _collect_input_paths(config_dict, config_dir)
    input_fps = [fingerprint_file(str(path)) for path in input_paths]
    run_fingerprint = compute_run_fingerprint(config_dict, roi_hash, input_fps)
    logger.info(
        "Computed run fingerprint %s (config=%s, inputs=%d)",
        run_fingerprint,
        config_bytes_hash,
        len(input_fps),
    )

    # --- Run directory -------------------------------------------------------
    output_dir = ensure_dir(cfg.output_dir)
    run_dir = ensure_dir(output_dir / "runs" / run_fingerprint)

    _required_artifacts = [
        run_dir / "features.parquet",
        run_dir / "manifest.json",
        run_dir / "report.json",
    ]
    if all(p.exists() for p in _required_artifacts):
        logger.info(
            "Detected identical run %s — all artifacts present, returning cached result.",
            run_fingerprint,
        )
        df = pd.read_parquet(run_dir / "features.parquet")
        df.attrs["run_fingerprint"] = run_fingerprint
        df.attrs["run_dir"] = str(run_dir)
        return df

    # --- DataCatalog (metadata only, no pixel reads) -------------------------
    _t_catalog_start = time.perf_counter()
    catalog = build_data_catalog(cfg.raster_path, cfg.climate_csv)
    _t_catalog = time.perf_counter() - _t_catalog_start

    # --- Load inputs ---------------------------------------------------------
    _t_load_start = time.perf_counter()
    raster = load_raster(cfg.raster_path)
    raster_crs = raster.crs
    try:
        climate_df = load_climate_csv(cfg.climate_csv)
    except Exception:
        raster.close()
        raise
    _t_load = time.perf_counter() - _t_load_start

    logger.info(
        "Loaded raster: %s (CRS: EPSG:%s)",
        cfg.raster_path,
        raster_crs.to_epsg() or "custom",
    )
    logger.info("Loaded climate data: %s", cfg.climate_csv)

    # --- Clip raster to ROI --------------------------------------------------
    _t_clip_start = time.perf_counter()
    clipped_data, clipped_transform = clip_raster_to_roi(
        raster,
        cfg.roi.model_dump(),
        roi_crs=cfg.roi.roi_crs,
    )
    _t_clip = time.perf_counter() - _t_clip_start
    logger.info("Clipped raster to ROI")

    # Coverage metrics --------------------------------------------------------
    rows: int
    cols: int
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

    # --- Climate interpolator ------------------------------------------------
    interpolator = ClimateInterpolator(
        climate_df=climate_df,
        strategy=cfg.climate.strategy,
        cell_id_column=cfg.climate.cell_id_column,
        fallback_to_mean=cfg.climate.fallback_to_mean,
    )
    logger.info(
        "Initialized climate interpolator with strategy='%s'", cfg.climate.strategy
    )

    # --- Sample cells --------------------------------------------------------
    import random

    max_cells = min(cfg.max_cells, n_valid_cells)
    sampled_indices = random.sample(valid_indices, max_cells)
    logger.info(
        "Sampled %d cells from %d valid cells in ROI", max_cells, n_valid_cells
    )

    # Pre-compute cell centre coordinates in native raster CRS.
    _native_xs: List[float] = []
    _native_ys: List[float] = []
    for row, col in sampled_indices:
        x, y = xy(clipped_transform, row, col, offset="center")
        _native_xs.append(float(x))
        _native_ys.append(float(y))

    # Reproject to WGS84 (EPSG:4326).
    _wgs84 = CRS.from_epsg(4326)
    if raster_crs != _wgs84:
        _coord_tf = Transformer.from_crs(raster_crs, _wgs84, always_xy=True)
        _lons, _lats = _coord_tf.transform(_native_xs, _native_ys)
        cell_lons: List[float] = list(_lons)
        cell_lats: List[float] = list(_lats)
    else:
        cell_lons = _native_xs
        cell_lats = _native_ys

    # --- Climate interpolation -----------------------------------------------
    _t_interp_start = time.perf_counter()
    cell_climate_df = interpolator.interpolate(np.array(cell_lats), np.array(cell_lons))
    _t_interp = time.perf_counter() - _t_interp_start
    logger.info(
        "Interpolated climate for %d cells using strategy='%s'",
        len(sampled_indices),
        cfg.climate.strategy,
    )

    # --- Score cells ---------------------------------------------------------
    _t_score_start = time.perf_counter()
    records: List[Dict[str, Any]] = []

    for cell_id, (row, col) in enumerate(sampled_indices):
        v_index = float(clipped_data[row, col])
        lat = cell_lats[cell_id]
        lon = cell_lons[cell_id]
        mean_temp = float(cell_climate_df.iloc[cell_id]["mean_temp"])
        total_rain = float(cell_climate_df.iloc[cell_id]["total_rain"])

        score = suitability_score(
            v_index=v_index,
            mean_temp=mean_temp,
            total_rain=total_rain,
            params=cfg.model_params,
        )
        label = suitability_label(score)

        records.append(
            {
                "run_id": run_fingerprint,
                "cell_id": cell_id,
                "lat": lat,
                "lon": lon,
                "v_index": v_index,
                "mean_temp": mean_temp,
                "total_rain": total_rain,
                "score": score,
                "label": label,
            }
        )

    df = pd.DataFrame.from_records(records)
    # Enforce stable column order from schema contract.
    df = df[FEATURES_COLUMNS_ORDERED]
    _t_score = time.perf_counter() - _t_score_start

    raster.close()
    logger.info("Closed raster dataset")

    # --- Write artifacts atomically ------------------------------------------
    _t_write_start = time.perf_counter()

    # 1. features.parquet (canonical output)
    _atomic_write_parquet(
        run_dir / "features.parquet",
        df,
        schema_meta={"run_fingerprint": run_fingerprint},
    )

    # 2. results.csv (backward-compat; same data, same directory)
    _atomic_write_text(run_dir / "results.csv", df.to_csv(index=False))

    # 3. manifest.json
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
        run_dir / "manifest.json",
        json.dumps(manifest, indent=2, default=str),
    )

    # 4. report.json
    raster_data_for_report = clipped_data.compressed().astype("float64")
    climate_var_cols = [c for c in climate_df.columns if c not in ("lat", "lon")]
    climate_var_stats: Dict[str, Any] = {}
    for var in climate_var_cols:
        col = climate_df[var].dropna()
        climate_var_stats[var] = {
            "mean": float(col.mean()) if len(col) else None,
            "min": float(col.min()) if len(col) else None,
            "max": float(col.max()) if len(col) else None,
            "n_nodata": int(climate_df[var].isna().sum()),
        }

    scores_arr = df["score"].to_numpy()
    _t_total = time.perf_counter() - _t_total_start
    _t_write = time.perf_counter() - _t_write_start

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
            "count": int(raster_data_for_report.size),
            "mean": float(raster_data_for_report.mean()) if raster_data_for_report.size else None,
            "std": float(raster_data_for_report.std(ddof=1)) if raster_data_for_report.size > 1 else 0.0,
            "min": float(raster_data_for_report.min()) if raster_data_for_report.size else None,
            "max": float(raster_data_for_report.max()) if raster_data_for_report.size else None,
        },
        "climate_stats": {
            "n_rows": len(climate_df),
            "variables": climate_var_stats,
        },
        "n_cells_sampled": len(records),
        "score_stats": {
            "mean": float(scores_arr.mean()) if len(scores_arr) else None,
            "std": float(scores_arr.std(ddof=1)) if len(scores_arr) > 1 else 0.0,
            "min": float(scores_arr.min()) if len(scores_arr) else None,
            "max": float(scores_arr.max()) if len(scores_arr) else None,
        },
        "timings_sec": {
            "build_catalog": round(_t_catalog, 4),
            "load_inputs": round(_t_load, 4),
            "clip_roi": round(_t_clip, 4),
            "interpolate_climate": round(_t_interp, 4),
            "score_cells": round(_t_score, 4),
            "write_outputs": round(_t_write, 4),
            "total": round(_t_total, 4),
        },
    }
    _atomic_write_text(
        run_dir / "report.json",
        json.dumps(report, indent=2, default=str),
    )

    logger.info(
        "Artifacts written to %s (fingerprint=%s, cells=%d, total=%.2fs)",
        run_dir,
        run_fingerprint,
        len(records),
        _t_total,
    )

    df.attrs["run_fingerprint"] = run_fingerprint
    df.attrs["run_dir"] = str(run_dir)
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
