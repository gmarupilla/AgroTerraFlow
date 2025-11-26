from pathlib import Path

import pandas as pd
import rasterio
from rasterio.io import DatasetReader


def load_raster(path: str | Path) -> DatasetReader:
    """Load a raster dataset (e.g., GeoTIFF)."""
    return rasterio.open(path)


def load_climate_csv(path: str | Path) -> pd.DataFrame:
    """Load climate data from CSV."""
    return pd.read_csv(path)
