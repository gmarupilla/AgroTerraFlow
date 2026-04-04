"""H3-indexed export adapter for TerraFlow pipeline output."""
from __future__ import annotations

import pandas as pd

try:
    import h3

    _H3_AVAILABLE = True
except ImportError:
    _H3_AVAILABLE = False


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
        raise ImportError("h3 is required for H3 export. Install it with: pip install terraflow[h3]")

    if not (0 <= resolution <= 15):
        raise ValueError(f"H3 resolution must be 0-15, got {resolution}")

    required_cols = {"lat", "lon", "score", "v_index", "mean_temp", "total_rain", "label"}
    missing = required_cols - set(features.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    features = features.copy()
    features["h3_cell"] = features.apply(lambda row: h3.latlng_to_cell(row["lat"], row["lon"], resolution), axis=1)

    numeric_cols = ["score", "v_index", "mean_temp", "total_rain"]
    numeric_agg = features.groupby("h3_cell")[numeric_cols].mean()

    label_mode = features.groupby("h3_cell")["label"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0]
    )

    result = numeric_agg.join(label_mode)
    result.index.name = "h3_cell"
    return result
