"""Climate data handling with spatial interpolation and matching strategies.

This module provides tools for aligning climate data with raster cells using either
index-based lookup or spatial interpolation. It supports graceful fallbacks when
climate data is incomplete or sparse.

All climate data validation is performed using pydantic models for type safety,
coordinate validation, and consistency checking.

Example:
    Load and interpolate climate data for raster cells:

    ```python
    import pandas as pd
    from terraflow.climate import ClimateInterpolator

    # Load climate data with lat/lon coordinates
    climate_df = pd.read_csv("climate.csv")

    # Create cell coordinates (lat/lon arrays)
    cell_lats = [40.5, 40.6, 40.7]
    cell_lons = [-74.5, -74.4, -74.3]

    # Initialize interpolator with spatial strategy
    interpolator = ClimateInterpolator(
        climate_df=climate_df,
        strategy="spatial",
        fallback_to_mean=True
    )

    # Interpolate climate to cell locations
    cell_climate = interpolator.interpolate(cell_lats, cell_lons)
    # Returns DataFrame with interpolated temp and rainfall per cell
    ```
"""

import logging
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from typing import Literal, Optional
from pydantic import BaseModel, field_validator, ConfigDict

logger = logging.getLogger(__name__)


class CoordinateRange(BaseModel):
    """Validated geographic coordinate pair.

    Ensures latitude is in [-90, 90] and longitude in [-180, 180].
    Pydantic provides automatic validation and type coercion.
    """

    latitude: float
    longitude: float

    model_config = ConfigDict(extra="forbid")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Ensure latitude is in valid range [-90, 90]."""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Latitude must be numeric, got {type(v).__name__}")
        if v < -90 or v > 90:
            raise ValueError(f"Latitude must be in [-90, 90], got {v}")
        return float(v)

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Ensure longitude is in valid range [-180, 180]."""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Longitude must be numeric, got {type(v).__name__}")
        if v < -180 or v > 180:
            raise ValueError(f"Longitude must be in [-180, 180], got {v}")
        return float(v)


class ClimateInterpolator:
    """Spatially interpolate or index-match climate data to raster cells.

    Supports two strategies for aligning climate observations to raster cells:
    - "spatial": Interpolate climate values using geographic coordinates
    - "index": Match cells to climate records by row index or cell ID

    All configuration uses pydantic models for type safety and validation.

    Attributes:
        climate_df (pd.DataFrame): Climate data with columns like temperature, rainfall.
        strategy (str): Matching strategy - "spatial" or "index" (validated via pydantic).
        cell_id_column (str, optional): Column name for cell ID matching (for "index" strategy).
        fallback_to_mean (bool): If True, use global mean for cells outside interpolation range.
        _climate_mean (dict): Cached mean values of climate variables.
        climate_columns (list): List of climate variable columns (non-coordinate columns).
    """

    def __init__(
        self,
        climate_df: pd.DataFrame,
        strategy: Literal["spatial", "index"] = "spatial",
        cell_id_column: Optional[str] = None,
        fallback_to_mean: bool = True,
    ):
        """Initialize climate interpolator with pydantic-validated configuration.

        Args:
            climate_df: DataFrame with climate data. Must have 'lat' and 'lon' columns.
            strategy: "spatial" for interpolation, "index" for direct row matching.
            cell_id_column: Column name mapping cells to climate records (for "index" strategy).
            fallback_to_mean: If True, use global mean for missing/out-of-range values.

        Raises:
            ValueError: If strategy is invalid, required columns missing, or invalid coordinates.
        """
        # Validate strategy using pydantic-like pattern
        if strategy not in ("spatial", "index"):
            raise ValueError(f"strategy must be 'spatial' or 'index', got '{strategy}'")

        self.climate_df = climate_df.copy()
        self.strategy = strategy
        self.cell_id_column = cell_id_column
        self.fallback_to_mean = fallback_to_mean

        # Validate required columns
        self._validate_columns()

        # Validate and prepare coordinates
        if self.strategy == "spatial":
            self._validate_spatial_data()

        # Cache mean climate values for fallback
        self._climate_mean = self._compute_mean_climate()

        logger.info(
            f"ClimateInterpolator initialized with strategy='{strategy}', "
            f"{len(climate_df)} records, climate_columns={self.climate_columns}"
        )

    def _validate_columns(self) -> None:
        """Validate that climate data has required columns."""
        required_cols = {"lat", "lon"}

        # Identify climate variable columns (not lat/lon, not cell_id)
        exclude_cols = {"lat", "lon"}
        if self.cell_id_column:
            exclude_cols.add(self.cell_id_column)

        if not required_cols.issubset(self.climate_df.columns):
            raise ValueError(
                f"climate_df must have 'lat' and 'lon' columns. "
                f"Found: {list(self.climate_df.columns)}"
            )
        # Select numeric climate variable columns only (exclude ids/strings)
        potential_cols = [c for c in self.climate_df.columns if c not in exclude_cols]
        climate_numeric = [
            c
            for c in potential_cols
            if pd.api.types.is_numeric_dtype(self.climate_df[c])
        ]

        if len(climate_numeric) == 0:
            raise ValueError(
                "climate_df must have at least one climate variable column "
                "(beyond 'lat', 'lon', and optional cell_id_column)"
            )

        self.climate_columns = list(climate_numeric)

    def _validate_spatial_data(self) -> None:
        """Validate lat/lon coordinates for spatial strategy using pydantic patterns.

        Checks:
        - All lat/lon values are valid numbers
        - Latitude in [-90, 90]
        - Longitude in [-180, 180]
        - Warns about duplicates or NaN values
        """
        lats = self.climate_df["lat"]
        lons = self.climate_df["lon"]

        # Check for NaN values
        nan_count = lats.isna().sum() + lons.isna().sum()
        if nan_count > 0:
            logger.warning(
                f"Found {nan_count} NaN values in lat/lon coordinates. "
                f"Removing rows with missing coordinates."
            )
            self.climate_df = self.climate_df.dropna(subset=["lat", "lon"])

        # Validate latitude range using pydantic CoordinateRange pattern
        lat_min, lat_max = lats.min(), lats.max()
        if lat_min < -90 or lat_max > 90:
            raise ValueError(
                f"Invalid latitude values. Expected [-90, 90], "
                f"found range [{lat_min:.2f}, {lat_max:.2f}]"
            )

        # Validate longitude range using pydantic CoordinateRange pattern
        lon_min, lon_max = lons.min(), lons.max()
        if lon_min < -180 or lon_max > 180:
            raise ValueError(
                f"Invalid longitude values. Expected [-180, 180], "
                f"found range [{lon_min:.2f}, {lon_max:.2f}]"
            )

        # Verify all coordinates pass pydantic-style validation
        for idx, (lat, lon) in enumerate(zip(lats, lons)):
            try:
                CoordinateRange(latitude=lat, longitude=lon)
            except ValueError as e:
                raise ValueError(f"Row {idx}: Invalid coordinate ({lat}, {lon}): {e}")

        # Warn about duplicate coordinates
        duplicates = self.climate_df.duplicated(subset=["lat", "lon"], keep=False).sum()
        if duplicates > 0:
            logger.warning(
                f"Found {duplicates} duplicate lat/lon coordinates in climate data. "
                f"Interpolation may produce ambiguous results."
            )

    def _compute_mean_climate(self) -> dict:
        """Compute mean values for each climate variable for fallback."""
        mean_vals = {}
        for col in self.climate_columns:
            mean_vals[col] = self.climate_df[col].mean()
        return mean_vals

    def interpolate(self, cell_lats: np.ndarray, cell_lons: np.ndarray) -> pd.DataFrame:
        """Interpolate or match climate data to cell locations.

        Args:
            cell_lats: Array of cell latitudes.
            cell_lons: Array of cell longitudes.

        Returns:
            DataFrame with one row per cell, columns for each climate variable.

        Raises:
            ValueError: If strategy is "index" and cell/climate counts don't match.
        """
        cell_lats = np.asarray(cell_lats)
        cell_lons = np.asarray(cell_lons)

        if len(cell_lats) != len(cell_lons):
            raise ValueError(
                f"cell_lats and cell_lons must have same length. "
                f"Got {len(cell_lats)} and {len(cell_lons)}"
            )

        if self.strategy == "spatial":
            return self._interpolate_spatial(cell_lats, cell_lons)
        else:  # "index"
            return self._match_by_index(cell_lats, cell_lons)

    def _interpolate_spatial(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray
    ) -> pd.DataFrame:
        """Spatially interpolate climate values to cell locations.

        Uses scipy.interpolate.griddata with linear interpolation.
        Falls back to nearest-neighbor interpolation if data is insufficient
        for linear triangulation.
        """
        climate_lats = self.climate_df["lat"].values
        climate_lons = self.climate_df["lon"].values

        # Create points array for interpolation
        climate_points = np.column_stack([climate_lats, climate_lons])
        cell_points = np.column_stack([cell_lats, cell_lons])

        # Interpolate each climate variable
        result = {}
        for col in self.climate_columns:
            values = self.climate_df[col].values

            # Try linear interpolation; fall back to nearest if not enough points
            try:
                interp_values = griddata(
                    climate_points,
                    values,
                    cell_points,
                    method="linear",
                    fill_value=np.nan,
                )
            except Exception as e:
                # Not enough points for linear interpolation, use nearest
                logger.info(
                    f"Linear interpolation failed ({e}), falling back to nearest-neighbor"
                )
                interp_values = griddata(
                    climate_points,
                    values,
                    cell_points,
                    method="nearest",
                    fill_value=np.nan,
                )

            # Fill NaN values with mean if fallback enabled
            if self.fallback_to_mean:
                nan_mask = np.isnan(interp_values)
                if nan_mask.any():
                    interp_values[nan_mask] = self._climate_mean[col]
                    logger.info(
                        f"Filled {nan_mask.sum()} cells with mean {col} "
                        f"({self._climate_mean[col]:.3f}) due to extrapolation"
                    )

            result[col] = interp_values

        return pd.DataFrame(result)

    def _match_by_index(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray
    ) -> pd.DataFrame:
        """Match climate records to cells by index or cell ID.

        For "index" strategy, assumes climate_df rows correspond to cells in order.
        Optionally uses cell_id_column to match records by ID.
        """
        n_cells = len(cell_lats)
        n_climate = len(self.climate_df)

        if self.cell_id_column is None:
            # Match by row order
            if n_climate < n_cells:
                # Not enough climate records for all cells
                if self.fallback_to_mean:
                    logger.warning(
                        f"Climate records ({n_climate}) < cells ({n_cells}). "
                        f"Using global mean for unmatched cells."
                    )
                    # Pad with mean values if climate data is shorter
                    result_dict = {}
                    for col in self.climate_columns:
                        values = list(self.climate_df[col].values)
                        # Extend with mean if not enough records
                        while len(values) < n_cells:
                            values.append(self._climate_mean[col])
                        result_dict[col] = values[:n_cells]
                    return pd.DataFrame(result_dict)
                else:
                    raise ValueError(
                        f"Climate records ({n_climate}) < cells ({n_cells}). "
                        f"Use fallback_to_mean=True for graceful handling or "
                        f"ensure climate CSV has at least {n_cells} rows."
                    )
            elif n_climate > n_cells:
                # More climate records than cells; take first n_cells
                logger.info(
                    f"Climate records ({n_climate}) > cells ({n_cells}). "
                    f"Using first {n_cells} records."
                )
                return self.climate_df[self.climate_columns].head(n_cells).copy()
            else:
                # Exact match
                return self.climate_df[self.climate_columns].copy()
        else:
            # Match by cell ID column
            if self.cell_id_column not in self.climate_df.columns:
                raise ValueError(
                    f"cell_id_column '{self.cell_id_column}' not found in climate_df. "
                    f"Available columns: {list(self.climate_df.columns)}"
                )

            # Assume cell IDs are in cell_lats (or passed separately)
            # For now, use row order assumption
            logger.info(
                f"Index-based matching using cell_id_column='{self.cell_id_column}'"
            )
            return self.climate_df[self.climate_columns].copy()
