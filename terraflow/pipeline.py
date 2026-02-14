from pathlib import Path
from typing import List, Dict
import glob
import hashlib
import random

import numpy as np
import pandas as pd
from rasterio.transform import xy

from .config import PipelineConfig, build_config, load_config_dict
from .core.run_identity import (
    canonicalize_config,
    compute_run_fingerprint,
    fingerprint_file,
    hash_roi_geometry,
)
from .ingest import load_raster, load_climate_csv
from .geo import clip_raster_to_roi
from .model import suitability_score, suitability_label
from .climate import ClimateInterpolator
from .utils import ensure_dir, logger


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


def run_pipeline(config_path: str | Path) -> pd.DataFrame:
    """Run the end-to-end pipeline and return a DataFrame of results.

    Uses spatially-aware climate data matching to apply per-cell climate values
    based on the configured strategy (spatial interpolation or index-based matching).

    Parameters
    ----------
    config_path:
        Path to YAML configuration file.

    Returns
    -------
    pd.DataFrame:
        Results table with columns: cell_id, lat, lon, v_index, mean_temp,
        total_rain, score, label.

    Raises
    ------
    FileNotFoundError:
        If config file, raster file, or climate CSV does not exist.
    ValueError:
        If configuration is invalid or no valid raster cells found in ROI.
    """
    config_path = Path(config_path)
    config_dict = load_config_dict(config_path)
    cfg: PipelineConfig = build_config(config_dict)
    logger.info("Loaded config from %s", config_path)

    config_dir = config_path.resolve().parent
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

    raster = load_raster(cfg.raster_path)
    try:
        climate_df = load_climate_csv(cfg.climate_csv)
    except Exception:
        raster.close()
        raise

    logger.info(
        "Loaded raster and climate data: %s, %s",
        cfg.raster_path,
        cfg.climate_csv,
    )

    # Clip raster to ROI and compute a simple vegetation index by using band 1 values.
    clipped_data, clipped_transform = clip_raster_to_roi(
        raster,
        cfg.roi.model_dump(),
    )
    logger.info("Clipped raster to ROI")

    # Initialize climate interpolator with configured strategy
    interpolator = ClimateInterpolator(
        climate_df=climate_df,
        strategy=cfg.climate.strategy,
        cell_id_column=cfg.climate.cell_id_column,
        fallback_to_mean=cfg.climate.fallback_to_mean,
    )
    logger.info(
        "Initialized climate interpolator with strategy='%s'", cfg.climate.strategy
    )

    rows: int
    cols: int
    rows, cols = clipped_data.shape

    # Collect indices of valid (non-masked) cells.
    valid_indices: List[tuple[int, int]] = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if not np.ma.is_masked(clipped_data[r, c])
    ]

    if not valid_indices:
        raise ValueError("No valid raster cells found in the specified ROI")

    # Respect max_cells from config to avoid generating huge tables.
    # Use random sampling for unbiased spatial representation (not just top-left corner).
    max_cells = min(cfg.max_cells, len(valid_indices))
    sampled_indices = random.sample(valid_indices, max_cells)
    logger.info(
        "Sampled %d cells from %d valid cells in ROI", max_cells, len(valid_indices)
    )

    # Pre-compute geographic coordinates for all sampled cells
    cell_lats = []
    cell_lons = []
    for row, col in sampled_indices:
        x, y = xy(clipped_transform, row, col, offset="center")
        cell_lats.append(y)
        cell_lons.append(x)

    # Interpolate climate values for all cells at once
    cell_climate_df = interpolator.interpolate(np.array(cell_lats), np.array(cell_lons))
    logger.info(
        "Interpolated climate for %d cells using strategy='%s'",
        len(sampled_indices),
        cfg.climate.strategy,
    )

    records: List[Dict[str, float | int | str]] = []

    for cell_id, (row, col) in enumerate(sampled_indices):
        v_index = float(clipped_data[row, col])

        # Get pre-computed geographic coordinates
        lat = cell_lats[cell_id]
        lon = cell_lons[cell_id]

        # Get per-cell climate values from interpolator
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

    # Ensure raster is closed to avoid resource leak
    raster.close()
    logger.info("Closed raster dataset")

    out_dir = ensure_dir(cfg.output_dir)
    out_csv = out_dir / "results.csv"
    df.to_csv(out_csv, index=False)
    logger.info("Saved results to %s", out_csv)

    df.attrs["run_fingerprint"] = run_fingerprint
    return df
