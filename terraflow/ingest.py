from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd
import rasterio
from pydantic import BaseModel
from rasterio.io import DatasetReader

from .utils import logger

# ---------------------------------------------------------------------------
# DataCatalog — lightweight metadata contract for ingest layer
# ---------------------------------------------------------------------------
# Architecture boundary: this module resolves datasets from local files,
# checks availability/coverage, and collects metadata.  It MUST NOT
# orchestrate pipeline steps or write final features.
# ---------------------------------------------------------------------------


class RasterLayer(BaseModel):
    """Metadata for a single raster input layer."""

    layer_name: str
    """Logical name for this layer (e.g. 'soil', 'vegetation')."""
    path: str
    """Resolved absolute path to the raster file."""
    crs: str
    """CRS as a proj-string or EPSG code (e.g. 'EPSG:4326')."""
    bounds: tuple[float, float, float, float]
    """Spatial extent in native CRS: (left, bottom, right, top)."""
    nodata: Optional[float]
    """Nodata sentinel value, or ``None`` if unset in the file."""
    dtype: str
    """Numpy dtype string of band 1 (e.g. 'float32')."""
    shape: tuple[int, int]
    """Raster grid dimensions (height, width)."""
    sha256: Optional[str] = None
    """SHA-256 hex digest of the file contents (content fingerprint)."""


class ClimateLayer(BaseModel):
    """Metadata for a single climate/tabular input layer."""

    path: str
    """Resolved absolute path to the CSV file."""
    n_rows: int
    """Row count after coordinate validation and NaN-dropping."""
    variables: list[str]
    """Climate variable column names (excludes 'lat' and 'lon')."""
    lat_range: tuple[float, float]
    """Observed latitude range: (min, max)."""
    lon_range: tuple[float, float]
    """Observed longitude range: (min, max)."""
    sha256: Optional[str] = None
    """SHA-256 hex digest of the file contents (content fingerprint)."""


class DataCatalog(BaseModel):
    """Immutable metadata snapshot of all resolved input datasets.

    Produced by :func:`build_data_catalog` after local file resolution and
    availability checks.  The pipeline orchestrator depends *only* on
    ``DataCatalog`` — not on dataset-specific glob logic.

    The catalog does NOT read raster pixel data or orchestrate any pipeline
    step; it is a pure metadata/provenance object.
    """

    raster_layers: list[RasterLayer] = []
    climate_layers: list[ClimateLayer] = []

    def to_provenance(self) -> dict:
        """Serialise to a plain dict suitable for ``manifest.json``."""
        return self.model_dump()

    def raster_by_name(self, layer_name: str) -> Optional[RasterLayer]:
        """Return the first ``RasterLayer`` matching *layer_name*, or ``None``."""
        for layer in self.raster_layers:
            if layer.layer_name == layer_name:
                return layer
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path, chunk_size: int = 8_388_608) -> str:
    """Return SHA-256 hex digest of a file's contents."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_data_catalog(
    raster_path: str | Path,
    climate_csv_path: str | Path,
    *,
    raster_layer_name: str = "primary",
) -> DataCatalog:
    """Resolve local input files, collect metadata, and return a DataCatalog.

    This function performs availability checks, reads raster metadata (CRS,
    bounds, nodata, shape), parses climate CSV headers, and computes SHA-256
    fingerprints.  It does **not** load raster pixel arrays or orchestrate any
    downstream step.

    Parameters
    ----------
    raster_path:
        Absolute or resolvable path to the input GeoTIFF raster.
    climate_csv_path:
        Absolute or resolvable path to the climate CSV.
    raster_layer_name:
        Logical name assigned to the raster in the catalog (default
        ``"primary"``).

    Returns
    -------
    DataCatalog
        Immutable metadata snapshot for use in provenance writing.

    Raises
    ------
    FileNotFoundError
        If either input file does not exist.
    ValueError
        If the CSV is missing required coordinate columns.
    """
    raster_path = Path(raster_path).resolve()
    climate_csv_path = Path(climate_csv_path).resolve()

    if not raster_path.exists():
        raise FileNotFoundError(f"Raster not found: {raster_path}")
    if not climate_csv_path.exists():
        raise FileNotFoundError(f"Climate CSV not found: {climate_csv_path}")

    # --- Raster metadata (no pixel reads) -----------------------------------
    with rasterio.open(raster_path) as ds:
        crs_str = ds.crs.to_string() if ds.crs is not None else "unknown"
        bounds = (ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top)
        nodata_val = float(ds.nodata) if ds.nodata is not None else None
        dtype_str = str(ds.dtypes[0])
        shape = (ds.height, ds.width)

    raster_sha = _sha256_file(raster_path)

    raster_layer = RasterLayer(
        layer_name=raster_layer_name,
        path=str(raster_path),
        crs=crs_str,
        bounds=bounds,
        nodata=nodata_val,
        dtype=dtype_str,
        shape=shape,
        sha256=raster_sha,
    )

    # --- Climate CSV metadata (header + coordinate scan only) ---------------
    climate_df_header = pd.read_csv(climate_csv_path, nrows=0)
    cols = list(climate_df_header.columns)
    if "lat" not in cols or "lon" not in cols:
        raise ValueError(
            f"Climate CSV missing required 'lat'/'lon' columns. Found: {cols}"
        )
    climate_vars = [c for c in cols if c not in ("lat", "lon")]

    # Read only lat/lon for range computation (lightweight).
    coord_df = pd.read_csv(climate_csv_path, usecols=["lat", "lon"]).dropna()
    n_rows = len(coord_df)
    lat_range = (float(coord_df["lat"].min()), float(coord_df["lat"].max()))
    lon_range = (float(coord_df["lon"].min()), float(coord_df["lon"].max()))

    climate_sha = _sha256_file(climate_csv_path)

    climate_layer = ClimateLayer(
        path=str(climate_csv_path),
        n_rows=n_rows,
        variables=sorted(climate_vars),
        lat_range=lat_range,
        lon_range=lon_range,
        sha256=climate_sha,
    )

    logger.info(
        f"DataCatalog built: raster={raster_path.name} (CRS {crs_str}, shape {shape}), "
        f"climate={climate_csv_path.name} ({n_rows} rows, vars={climate_vars})"
    )

    return DataCatalog(
        raster_layers=[raster_layer],
        climate_layers=[climate_layer],
    )


# ---------------------------------------------------------------------------
# Low-level loaders (kept for backward compatibility)
# ---------------------------------------------------------------------------


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
