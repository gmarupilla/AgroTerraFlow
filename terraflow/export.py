"""H3-indexed export adapter for TerraFlow pipeline output."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import h3

    _H3_AVAILABLE = True
except ImportError:
    _H3_AVAILABLE = False

from .config import build_config, load_config_dict
from .pipeline import _atomic_write_parquet, resolve_run_dir
from .utils import logger


def to_h3(features: pd.DataFrame, resolution: int = 8) -> pd.DataFrame:
    """Convert features DataFrame to H3-indexed DataFrame.

    Parameters
    ----------
    features : pd.DataFrame
        Pipeline output with columns: lat, lon, score, v_index, mean_temp, total_rain, label.
    resolution : int
        H3 resolution (0-15). Default 8.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by ``h3_cell`` with aggregated columns:
        score, v_index, mean_temp, total_rain, label.

    Raises
    ------
    ImportError
        If h3-py is not installed.
    ValueError
        If resolution is outside 0-15 or required columns are missing.
    """
    if not _H3_AVAILABLE:
        raise ImportError(
            "h3 is required for H3 export. Install it with: pip install terraflow-agro[h3]"
        )

    if not (0 <= resolution <= 15):
        raise ValueError(f"H3 resolution must be 0-15, got {resolution}")

    required_cols = {
        "lat",
        "lon",
        "score",
        "v_index",
        "mean_temp",
        "total_rain",
        "label",
    }
    missing = required_cols - set(features.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    features = features.copy()
    features["h3_cell"] = features.apply(
        lambda row: h3.latlng_to_cell(row["lat"], row["lon"], resolution), axis=1
    )

    numeric_cols = ["score", "v_index", "mean_temp", "total_rain"]
    numeric_agg = features.groupby("h3_cell")[numeric_cols].mean()

    label_mode = features.groupby("h3_cell")["label"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0]
    )

    result = numeric_agg.join(label_mode)
    result.index.name = "h3_cell"
    return result


def run_export(
    config_path: Path | str,
    resolution_override: int | None = None,
    format: str = "h3",
) -> Path:
    """Run H3 export on an existing pipeline run.

    Parameters
    ----------
    config_path : Path | str
        Path to YAML config file (must have an ``export:`` section).
    resolution_override : int | None
        If provided, overrides ``export.h3_resolution`` from config for the
        H3 conversion and output filename. Does not affect the run directory
        (which is determined by the on-disk config fingerprint).
    format : str
        Export format. Currently only ``"h3"`` is supported.

    Returns
    -------
    Path
        Path to the written H3 parquet artifact.

    Raises
    ------
    ValueError
        If format is unsupported, config has no ``export:`` section, or
        resolution is outside 0-15.
    FileNotFoundError
        If no pipeline run directory containing ``features.parquet`` is found.
    """
    if format != "h3":
        raise ValueError(
            f"Unsupported export format: '{format}'. Supported formats: h3"
        )

    data = load_config_dict(config_path)
    cfg = build_config(data)

    if cfg.export is None:
        raise ValueError(
            "Config file has no 'export:' section. "
            "Add an export: block with h3_resolution (0-15). "
            "See TerraFlow documentation for details."
        )

    # Effective resolution: CLI override > config value (per D-01, D-12)
    effective_resolution = (
        resolution_override
        if resolution_override is not None
        else cfg.export.h3_resolution
    )

    if not (0 <= effective_resolution <= 15):
        raise ValueError(f"H3 resolution must be 0-15, got {effective_resolution}")

    # Run dir is determined by on-disk config fingerprint (per D-07)
    run_dir = resolve_run_dir(config_path)
    features_path = run_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(
            f"No pipeline run found at {run_dir}. "
            "Run `terraflow run -c config.yml` before exporting."
        )

    logger.info(f"Running H3 export (resolution={effective_resolution}) on {run_dir}")

    df = pd.read_parquet(features_path)
    h3_df = to_h3(df, resolution=effective_resolution)

    output_path = run_dir / f"h3_resolution_{effective_resolution}.parquet"
    _atomic_write_parquet(
        output_path,
        h3_df.reset_index(),
        {"export_format": "h3", "h3_resolution": str(effective_resolution)},
    )

    logger.info(f"H3 export written to {output_path}")
    return output_path
