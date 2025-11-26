from pathlib import Path
from typing import List, Dict

import numpy as np
import pandas as pd
from rasterio.transform import xy

from .config import PipelineConfig, load_config
from .ingest import load_raster, load_climate_csv
from .geo import clip_raster_to_roi
from .model import suitability_score, suitability_label
from .utils import ensure_dir, logger


def _aggregate_climate(climate_df: pd.DataFrame) -> Dict[str, float]:
    """
    Aggregate climate data into simple summary statistics.

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


def run_pipeline(config_path: str | Path) -> pd.DataFrame:
    """Run the end-to-end pipeline and return a DataFrame of results."""
    cfg: PipelineConfig = load_config(config_path)
    logger.info("Loaded config from %s", config_path)

    raster = load_raster(cfg.raster_path)
    climate_df = load_climate_csv(cfg.climate_csv)

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

    # Aggregate climate information once; apply the same summary to all sampled cells.
    climate_summary = _aggregate_climate(climate_df)

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
    max_cells = min(cfg.max_cells, len(valid_indices))
    sampled_indices = valid_indices[:max_cells]

    records: List[Dict[str, float | int | str]] = []

    for cell_id, (row, col) in enumerate(sampled_indices):
        v_index = float(clipped_data[row, col])

        # Convert row/col to geographic coordinates using the clipped transform.
        x, y = xy(clipped_transform, row, col, offset="center")

        score = suitability_score(
            v_index=v_index,
            mean_temp=climate_summary["mean_temp"],
            total_rain=climate_summary["total_rain"],
            params=cfg.model_params,
        )
        label = suitability_label(score)

        records.append(
            {
                "cell_id": cell_id,
                "lat": y,
                "lon": x,
                "v_index": v_index,
                "mean_temp": climate_summary["mean_temp"],
                "total_rain": climate_summary["total_rain"],
                "score": score,
                "label": label,
            }
        )

    df = pd.DataFrame.from_records(records)

    out_dir = ensure_dir(cfg.output_dir)
    out_csv = out_dir / "results.csv"
    df.to_csv(out_csv, index=False)
    logger.info("Saved results to %s", out_csv)

    return df
