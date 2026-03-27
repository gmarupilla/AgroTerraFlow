"""Climate data handling with spatial interpolation and matching strategies.

This module provides tools for aligning climate data with raster cells using
index-based lookup or spatial interpolation.  Three spatial methods are
supported:

* **linear** (default) — Delaunay-triangulation linear interpolation via
  ``scipy.interpolate.griddata``.  Fast, zero extra dependencies, no
  uncertainty estimate.
* **kriging** — Ordinary Kriging via ``pykrige``.  Geostatistically optimal
  (Best Linear Unbiased Predictor) with automatic variogram model selection
  (spherical / exponential / Gaussian) based on Leave-One-Out Cross-Validation
  (LOOCV).  Returns per-cell prediction standard deviation as
  ``{var}_krig_std`` columns.  Requires ≥ ``MIN_KRIGING_STATIONS`` stations.
* **idw** — Inverse Distance Weighting (power=2).  Faster than kriging, no
  extra dependencies beyond numpy, no uncertainty estimate.

Cross-validation (LOOCV) is computed at initialisation time for the kriging
method and stored in ``ClimateInterpolator.cv_metrics``.  The pipeline writes
these metrics to ``report.json`` under ``interpolation_cv``.

Example
-------
.. code-block:: python

    import pandas as pd
    from terraflow.climate import ClimateInterpolator

    climate_df = pd.read_csv("climate.csv")
    cell_lats = [40.5, 40.6, 40.7]
    cell_lons = [-74.5, -74.4, -74.3]

    interpolator = ClimateInterpolator(
        climate_df=climate_df,
        strategy="spatial",
        interpolation_method="kriging",
        fallback_to_mean=True,
    )
    cell_climate = interpolator.interpolate(cell_lats, cell_lons)
    # Returns DataFrame with mean_temp, total_rain,
    # mean_temp_krig_std, total_rain_krig_std columns.
"""

from __future__ import annotations

import logging
from typing import Dict, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator
from scipy.interpolate import griddata

logger = logging.getLogger(__name__)

#: Minimum number of climate stations required for kriging.
#: Below this threshold the tool falls back to linear interpolation and
#: logs a warning.  Variogram estimation is unreliable with very sparse
#: networks (fewer than 5 stations yields < 10 lag pairs).
MIN_KRIGING_STATIONS: int = 5

#: Variogram models tried during automatic model selection.
_VARIOGRAM_MODELS: Tuple[str, ...] = ("spherical", "exponential", "gaussian")


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

    Supports two top-level strategies for aligning climate observations to
    raster cells:

    * ``"spatial"`` — interpolate from weather-station coordinates to cell
      centroids.  Three algorithms are available via ``interpolation_method``:
      ``"linear"`` (default), ``"kriging"``, ``"idw"``.
    * ``"index"`` — match cells to climate records by row order or cell ID.

    When ``interpolation_method="kriging"``, the interpolator:

    1. Selects the best variogram model (spherical / exponential / Gaussian)
       by Leave-One-Out Cross-Validation (LOOCV) RMSE on the first climate
       variable.
    2. Stores per-variable LOOCV RMSE and MAE in ``cv_metrics``.
    3. Returns ``{var}_krig_std`` columns alongside the point estimates.

    Attributes
    ----------
    climate_df : pd.DataFrame
        Climate data with ``lat``, ``lon``, and numeric variable columns.
    strategy : str
        Top-level matching strategy (``"spatial"`` or ``"index"``).
    interpolation_method : str
        Spatial algorithm (``"linear"``, ``"kriging"``, or ``"idw"``).
        Only used when ``strategy="spatial"``.
    cell_id_column : str or None
        Optional column for explicit cell-ID matching (``"index"`` strategy).
    fallback_to_mean : bool
        If True, replace NaN predictions with the global variable mean.
    cv_metrics : dict
        LOOCV results populated at init when ``interpolation_method="kriging"``.
        Empty dict for other methods.
    climate_columns : list[str]
        Numeric climate variable columns (excludes ``lat``, ``lon``,
        ``cell_id_column``).
    """

    def __init__(
        self,
        climate_df: pd.DataFrame,
        strategy: Literal["spatial", "index"] = "spatial",
        interpolation_method: Literal["linear", "kriging", "idw"] = "linear",
        cell_id_column: Optional[str] = None,
        fallback_to_mean: bool = True,
    ):
        """Initialise the interpolator and (for kriging) select variogram model.

        Parameters
        ----------
        climate_df:
            DataFrame with climate data.  Must have ``lat`` and ``lon``
            columns.
        strategy:
            ``"spatial"`` for coordinate-based interpolation; ``"index"``
            for direct row/ID matching.
        interpolation_method:
            Spatial interpolation algorithm.  ``"linear"`` uses
            ``scipy.griddata``; ``"kriging"`` uses PyKrige OrdinaryKriging
            with automatic variogram model selection; ``"idw"`` uses inverse
            distance weighting.  Only relevant when ``strategy="spatial"``.
        cell_id_column:
            Column name for cell-ID matching (``"index"`` strategy only).
        fallback_to_mean:
            Replace NaN / extrapolated values with the global variable mean.

        Raises
        ------
        ValueError
            If ``strategy`` or ``interpolation_method`` is invalid, required
            columns are missing, or coordinate ranges are violated.
        ImportError
            If ``interpolation_method="kriging"`` and PyKrige is not installed.
        """
        if strategy not in ("spatial", "index"):
            raise ValueError(f"strategy must be 'spatial' or 'index', got '{strategy}'")
        if interpolation_method not in ("linear", "kriging", "idw"):
            raise ValueError(
                f"interpolation_method must be 'linear', 'kriging', or 'idw', "
                f"got '{interpolation_method}'"
            )

        self.climate_df = climate_df.copy()
        self.strategy = strategy
        self.interpolation_method = interpolation_method
        self.cell_id_column = cell_id_column
        self.fallback_to_mean = fallback_to_mean
        self.cv_metrics: Dict = {}
        self._krig_variogram_model: str = "spherical"  # overwritten by _init_kriging
        self.variogram_params: dict = {}

        self._validate_columns()

        if self.strategy == "spatial":
            self._validate_spatial_data()

        self._climate_mean = self._compute_mean_climate()

        if self.strategy == "spatial" and self.interpolation_method == "kriging":
            self._init_kriging()

        logger.info(
            "ClimateInterpolator initialised: strategy='%s', "
            "interpolation_method='%s', records=%d, variables=%s",
            strategy,
            interpolation_method,
            len(self.climate_df),
            self.climate_columns,
        )

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _validate_columns(self) -> None:
        """Validate that climate data has required columns."""
        required_cols = {"lat", "lon"}
        exclude_cols = {"lat", "lon"}
        if self.cell_id_column:
            exclude_cols.add(self.cell_id_column)

        if not required_cols.issubset(self.climate_df.columns):
            raise ValueError(
                f"climate_df must have 'lat' and 'lon' columns. "
                f"Found: {list(self.climate_df.columns)}"
            )
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
        """Validate lat/lon coordinates for spatial strategy."""
        lats = self.climate_df["lat"]
        lons = self.climate_df["lon"]

        nan_count = lats.isna().sum() + lons.isna().sum()
        if nan_count > 0:
            logger.warning(
                "Found %d NaN values in lat/lon coordinates. "
                "Removing rows with missing coordinates.",
                nan_count,
            )
            self.climate_df = self.climate_df.dropna(subset=["lat", "lon"])

        lat_min, lat_max = lats.min(), lats.max()
        if lat_min < -90 or lat_max > 90:
            raise ValueError(
                f"Invalid latitude values. Expected [-90, 90], "
                f"found range [{lat_min:.2f}, {lat_max:.2f}]"
            )

        lon_min, lon_max = lons.min(), lons.max()
        if lon_min < -180 or lon_max > 180:
            raise ValueError(
                f"Invalid longitude values. Expected [-180, 180], "
                f"found range [{lon_min:.2f}, {lon_max:.2f}]"
            )

        for idx, (lat, lon) in enumerate(zip(lats, lons)):
            try:
                CoordinateRange(latitude=lat, longitude=lon)
            except ValueError as e:
                raise ValueError(f"Row {idx}: Invalid coordinate ({lat}, {lon}): {e}") from e

        duplicates = self.climate_df.duplicated(subset=["lat", "lon"], keep=False).sum()
        if duplicates > 0:
            logger.warning(
                "Found %d duplicate lat/lon coordinates in climate data. "
                "Interpolation may produce ambiguous results.",
                duplicates,
            )

    def _compute_mean_climate(self) -> dict:
        """Cache mean values of each climate variable for fallback use."""
        return {col: float(self.climate_df[col].mean()) for col in self.climate_columns}

    # ------------------------------------------------------------------
    # Kriging initialisation: variogram selection + LOOCV
    # ------------------------------------------------------------------

    def _init_kriging(self) -> None:
        """Select the best variogram model via LOOCV and compute CV metrics.

        If fewer than ``MIN_KRIGING_STATIONS`` stations are available, falls
        back to ``"linear"`` interpolation with a warning.

        Side effects
        ------------
        Sets ``self._krig_variogram_model`` and populates ``self.cv_metrics``.
        """
        import importlib.util

        if importlib.util.find_spec("pykrige") is None:
            raise ImportError(
                "PyKrige is required for kriging interpolation. "
                "Install with: pip install pykrige"
            )

        n = len(self.climate_df)
        if n < MIN_KRIGING_STATIONS:
            logger.warning(
                "Only %d climate stations available; kriging requires ≥%d. "
                "Falling back to linear interpolation.",
                n,
                MIN_KRIGING_STATIONS,
            )
            self.interpolation_method = "linear"
            return

        lons = self.climate_df["lon"].values.astype(float)
        lats = self.climate_df["lat"].values.astype(float)

        # --- Variogram model selection on the first climate variable ----------
        primary_var = self.climate_columns[0]
        vals_primary = self.climate_df[primary_var].values.astype(float)

        best_model: Optional[str] = None
        best_rmse = np.inf

        for model in _VARIOGRAM_MODELS:
            try:
                rmse, _ = self._loocv(lons, lats, vals_primary, model)
                logger.debug("Variogram '%s': LOOCV RMSE=%.4f (%s)", model, rmse, primary_var)
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_model = model
            except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                logger.debug("Variogram model '%s' failed during selection: %s", model, exc)

        if best_model is None:
            logger.warning(
                "All variogram models failed LOOCV; falling back to linear interpolation."
            )
            self.interpolation_method = "linear"
            return

        self._krig_variogram_model = best_model
        logger.info(
            "Kriging variogram selected: '%s' (LOOCV RMSE=%.4f for '%s')",
            best_model,
            best_rmse,
            primary_var,
        )

        # Extract variogram parameters from a full-data fit with the selected model.
        from pykrige.ok import OrdinaryKriging

        _ok_full = OrdinaryKriging(
            lons, lats, vals_primary,
            variogram_model=best_model,
            verbose=False,
            enable_plotting=False,
        )
        p = _ok_full.variogram_model_parameters  # [psill, range, nugget]
        self.variogram_params = {
            "model": best_model,
            "psill": round(float(p[0]), 6),
            "nugget": round(float(p[2]), 6),
            "sill": round(float(p[0]) + float(p[2]), 6),
            "range_": round(float(p[1]), 6),
            "range_units": "degrees_geographic",
        }

        # --- Full LOOCV for all variables with the selected model -------------
        cv_per_var: Dict = {}
        for var in self.climate_columns:
            vals = self.climate_df[var].values.astype(float)
            try:
                rmse, mae = self._loocv(lons, lats, vals, best_model)
                cv_per_var[var] = {
                    "rmse": round(float(rmse), 6),
                    "mae": round(float(mae), 6),
                    "n_stations": int(n),
                }
            except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                logger.warning("LOOCV failed for variable '%s': %s", var, exc)
                cv_per_var[var] = {"rmse": None, "mae": None, "n_stations": int(n)}

        self.cv_metrics = {
            "method": "loocv",
            "variogram_model": best_model,
            "per_variable": cv_per_var,
        }

    def _loocv(
        self, lons: np.ndarray, lats: np.ndarray, vals: np.ndarray, model: str
    ) -> Tuple[float, float]:
        """Return (RMSE, MAE) via Leave-One-Out Cross-Validation for a variogram model."""
        from pykrige.ok import OrdinaryKriging

        errors = []
        for i in range(len(vals)):
            ok = OrdinaryKriging(
                np.delete(lons, i),
                np.delete(lats, i),
                np.delete(vals, i),
                variogram_model=model,
                verbose=False,
                enable_plotting=False,
            )
            pred, _ = ok.execute("points", np.array([lons[i]]), np.array([lats[i]]))
            errors.append(float(pred[0]) - vals[i])
        errs = np.array(errors)
        return float(np.sqrt(np.mean(errs**2))), float(np.mean(np.abs(errs)))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def interpolate(self, cell_lats: np.ndarray, cell_lons: np.ndarray) -> pd.DataFrame:
        """Interpolate or match climate data to cell locations.

        Parameters
        ----------
        cell_lats:
            Array of cell latitudes (WGS84).
        cell_lons:
            Array of cell longitudes (WGS84).

        Returns
        -------
        pd.DataFrame
            One row per cell, columns for each climate variable.  When
            ``interpolation_method="kriging"``, additional
            ``{var}_krig_std`` columns are included (prediction standard
            deviation from the kriging variance).

        Raises
        ------
        ValueError
            If array lengths do not match.
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
        else:
            return self._match_by_index(cell_lats, cell_lons)

    # ------------------------------------------------------------------
    # Spatial interpolation dispatch
    # ------------------------------------------------------------------

    def _interpolate_spatial(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray
    ) -> pd.DataFrame:
        if self.interpolation_method == "kriging":
            return self._interpolate_kriging(cell_lats, cell_lons)
        elif self.interpolation_method == "idw":
            return self._interpolate_idw(cell_lats, cell_lons)
        else:
            return self._interpolate_linear(cell_lats, cell_lons)

    def _interpolate_linear(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray
    ) -> pd.DataFrame:
        """Delaunay-triangulation linear interpolation (scipy.griddata).

        Falls back to nearest-neighbour when fewer than 3 points are
        available; applies global mean fallback for extrapolated NaNs.
        """
        climate_lats = self.climate_df["lat"].values
        climate_lons = self.climate_df["lon"].values
        climate_points = np.column_stack([climate_lats, climate_lons])
        cell_points = np.column_stack([cell_lats, cell_lons])

        result = {}
        for col in self.climate_columns:
            values = self.climate_df[col].values
            try:
                interp_values = griddata(
                    climate_points,
                    values,
                    cell_points,
                    method="linear",
                    fill_value=np.nan,
                )
            except (ValueError, RuntimeError) as exc:
                logger.info(
                    "Linear interpolation failed (%s), falling back to nearest-neighbor",
                    exc,
                )
                interp_values = griddata(
                    climate_points,
                    values,
                    cell_points,
                    method="nearest",
                    fill_value=np.nan,
                )

            if self.fallback_to_mean:
                nan_mask = np.isnan(interp_values)
                if nan_mask.any():
                    interp_values[nan_mask] = self._climate_mean[col]
                    logger.info(
                        "Filled %d cells with mean %s (%.3f) due to extrapolation",
                        nan_mask.sum(),
                        col,
                        self._climate_mean[col],
                    )
            result[col] = interp_values

        return pd.DataFrame(result)

    def _interpolate_kriging(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray
    ) -> pd.DataFrame:
        """Ordinary Kriging interpolation with per-cell uncertainty.

        Uses the variogram model selected during ``_init_kriging``.  Returns
        one ``{var}_krig_std`` column per climate variable (kriging prediction
        standard deviation = sqrt of kriging variance).
        """
        from pykrige.ok import OrdinaryKriging

        lons_src = self.climate_df["lon"].values.astype(float)
        lats_src = self.climate_df["lat"].values.astype(float)
        cell_lons_arr = np.asarray(cell_lons, dtype=float)
        cell_lats_arr = np.asarray(cell_lats, dtype=float)

        result = {}
        for var in self.climate_columns:
            vals = self.climate_df[var].values.astype(float)

            ok = OrdinaryKriging(
                lons_src,
                lats_src,
                vals,
                variogram_model=self._krig_variogram_model,
                verbose=False,
                enable_plotting=False,
            )
            z_pred, sigma_sq = ok.execute("points", cell_lons_arr, cell_lats_arr)

            # sigma_sq can have small numerical negatives near station locations
            krig_std = np.sqrt(np.maximum(np.asarray(sigma_sq, dtype=float), 0.0))
            z_pred_arr = np.asarray(z_pred, dtype=float)

            if self.fallback_to_mean:
                nan_mask = np.isnan(z_pred_arr)
                if nan_mask.any():
                    z_pred_arr[nan_mask] = self._climate_mean[var]
                    logger.info(
                        "Filled %d NaN kriging predictions with mean %s",
                        nan_mask.sum(),
                        var,
                    )

            result[var] = z_pred_arr
            result[f"{var}_krig_std"] = krig_std

        return pd.DataFrame(result)

    def _interpolate_idw(
        self, cell_lats: np.ndarray, cell_lons: np.ndarray, power: float = 2.0
    ) -> pd.DataFrame:
        """Inverse Distance Weighting interpolation (power=2).

        No uncertainty estimate.  Handles the exact-station-coincidence case
        by returning the station value directly.
        """
        lons_src = self.climate_df["lon"].values.astype(float)
        lats_src = self.climate_df["lat"].values.astype(float)
        cell_lons_arr = np.asarray(cell_lons, dtype=float)
        cell_lats_arr = np.asarray(cell_lats, dtype=float)

        result = {}
        for var in self.climate_columns:
            vals = self.climate_df[var].values.astype(float)
            interp_values = np.empty(len(cell_lats_arr), dtype=float)

            for i, (clat, clon) in enumerate(zip(cell_lats_arr, cell_lons_arr)):
                dists = np.sqrt((lats_src - clat) ** 2 + (lons_src - clon) ** 2)
                zero_mask = dists < 1e-10
                if zero_mask.any():
                    # Cell coincides with a station — return exact value
                    interp_values[i] = vals[np.argmax(zero_mask)]
                else:
                    weights = 1.0 / (dists ** power)
                    interp_values[i] = np.sum(weights * vals) / np.sum(weights)

            if self.fallback_to_mean:
                nan_mask = np.isnan(interp_values)
                if nan_mask.any():
                    interp_values[nan_mask] = self._climate_mean[var]

            result[var] = interp_values

        return pd.DataFrame(result)

    # ------------------------------------------------------------------
    # Index-based matching
    # ------------------------------------------------------------------

    def _match_by_index(
        self, cell_lats: np.ndarray, _cell_lons: np.ndarray
    ) -> pd.DataFrame:
        """Match climate records to cells by row index or cell ID."""
        n_cells = len(cell_lats)
        n_climate = len(self.climate_df)

        if self.cell_id_column is None:
            if n_climate < n_cells:
                if self.fallback_to_mean:
                    logger.warning(
                        "Climate records (%d) < cells (%d). "
                        "Using global mean for unmatched cells.",
                        n_climate,
                        n_cells,
                    )
                    result_dict = {}
                    for col in self.climate_columns:
                        values = list(self.climate_df[col].values)
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
                logger.info(
                    "Climate records (%d) > cells (%d). Using first %d records.",
                    n_climate,
                    n_cells,
                    n_cells,
                )
                return self.climate_df[self.climate_columns].head(n_cells).copy()
            else:
                return self.climate_df[self.climate_columns].copy()
        else:
            if self.cell_id_column not in self.climate_df.columns:
                raise ValueError(
                    f"cell_id_column '{self.cell_id_column}' not found in climate_df. "
                    f"Available columns: {list(self.climate_df.columns)}"
                )
            logger.info(
                "Index-based matching using cell_id_column='%s'", self.cell_id_column
            )
            return self.climate_df[self.climate_columns].copy()
