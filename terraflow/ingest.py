from pathlib import Path

import pandas as pd
import rasterio
from rasterio.io import DatasetReader

from .utils import logger


def load_raster(path: str | Path) -> DatasetReader:
    """
    Load a raster dataset (e.g., GeoTIFF).

    Parameters
    ----------
    path:
        Path to the raster file.

    Returns
    -------
    DatasetReader:
        Open rasterio dataset. Caller is responsible for closing the dataset
        using a context manager or calling .close().

    Raises
    ------
    FileNotFoundError:
        If the file does not exist.
    rasterio.errors.RasterioIOError:
        If the file cannot be opened as a raster.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Raster file not found: {path}")
    
    try:
        dataset = rasterio.open(path)
        logger.info(f"Loaded raster from {path}")
        return dataset
    except rasterio.errors.RasterioIOError as e:
        raise rasterio.errors.RasterioIOError(
            f"Failed to open raster file {path}: {e}"
        ) from e


def load_climate_csv(path: str | Path) -> pd.DataFrame:
    """
    Load climate data from CSV.

    Parameters
    ----------
    path:
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame:
        Climate data with columns like 'mean_temp' and 'total_rain'.

    Raises
    ------
    FileNotFoundError:
        If the file does not exist.
    pd.errors.ParserError:
        If the CSV is malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Climate CSV file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded climate CSV from {path} with {len(df)} rows")
        return df
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(
            f"Failed to parse CSV file {path}: {e}"
        ) from e
