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
    Load and validate climate data from CSV.

    Parameters
    ----------
    path:
        Path to the CSV file. Must contain 'lat' and 'lon' columns
        for spatial interpolation, plus climate variables
        (e.g., 'mean_temp', 'total_rain').

    Returns
    -------
    pd.DataFrame:
        Climate data with validated coordinates and variables.

    Raises
    ------
    FileNotFoundError:
        If the file does not exist.
    pd.errors.ParserError:
        If the CSV is malformed.
    ValueError:
        If required columns are missing, coordinates are invalid,
        or climate data has NaN values in critical fields.

    Notes
    -----
    Validates:
    - File existence
    - Required 'lat' and 'lon' columns
    - Latitude range [-90, 90]
    - Longitude range [-180, 180]
    - At least one climate variable column (not lat/lon)
    - NaN values in coordinates (drops rows with missing lat/lon)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Climate CSV file not found: {path}")

    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded climate CSV from {path} with {len(df)} rows")
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(f"Failed to parse CSV file {path}: {e}") from e

    # Validate required columns
    required_cols = {"lat", "lon"}
    if not required_cols.issubset(df.columns):
        raise ValueError(
            f"Climate CSV must contain 'lat' and 'lon' columns. "
            f"Found columns: {list(df.columns)}"
        )

    # Identify climate variable columns (not lat/lon)
    climate_cols = set(df.columns) - {"lat", "lon"}
    if len(climate_cols) == 0:
        raise ValueError(
            "Climate CSV must have at least one climate variable column "
            "(beyond 'lat' and 'lon')"
        )

    logger.info(f"Climate variables: {sorted(climate_cols)}")

    # Remove rows with missing lat/lon
    initial_len = len(df)
    df = df.dropna(subset=["lat", "lon"])
    if len(df) < initial_len:
        logger.warning(
            f"Dropped {initial_len - len(df)} rows with missing lat/lon coordinates"
        )

    # Validate latitude range
    if (df["lat"] < -90).any() or (df["lat"] > 90).any():
        bad_lats = df[(df["lat"] < -90) | (df["lat"] > 90)]
        raise ValueError(
            f"Invalid latitude values found. Expected [-90, 90]. "
            f"Found range [{df['lat'].min():.2f}, {df['lat'].max():.2f}]. "
            f"Bad values: {bad_lats['lat'].unique()}"
        )

    # Validate longitude range
    if (df["lon"] < -180).any() or (df["lon"] > 180).any():
        bad_lons = df[(df["lon"] < -180) | (df["lon"] > 180)]
        raise ValueError(
            f"Invalid longitude values found. Expected [-180, 180]. "
            f"Found range [{df['lon'].min():.2f}, {df['lon'].max():.2f}]. "
            f"Bad values: {bad_lons['lon'].unique()}"
        )

    # Warn about NaN values in climate variables
    nan_counts = df[list(climate_cols)].isna().sum()
    if nan_counts.any():
        logger.warning(
            f"Found NaN values in climate variables: {nan_counts[nan_counts > 0].to_dict()}"
        )

    # Warn about duplicate coordinates
    duplicates = df.duplicated(subset=["lat", "lon"], keep=False).sum()
    if duplicates > 0:
        logger.warning(f"Found {duplicates} records with duplicate lat/lon coordinates")

    if len(df) == 0:
        raise ValueError("Climate CSV is empty or contains only invalid rows")

    logger.info(f"Climate CSV validated successfully: {len(df)} valid records")
    return df
