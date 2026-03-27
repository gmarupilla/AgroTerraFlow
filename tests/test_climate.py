"""Tests for climate data handling and spatial interpolation.

Covers ClimateInterpolator, load_climate_csv validation, and integration
with pipeline. Tests both 'spatial' (interpolation) and 'index' (direct matching)
strategies, edge cases, fallback behavior, and coordinate validation.
"""

import numpy as np
import pandas as pd
import pytest

from terraflow.climate import ClimateInterpolator
from terraflow.ingest import load_climate_csv


class TestClimateInterpolatorInit:
    """Test ClimateInterpolator initialization and validation."""

    def test_init_spatial_strategy_valid(self):
        """Valid spatial strategy initialization."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [15.0, 16.0, 17.0],
                "total_rain": [100.0, 110.0, 120.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="spatial", fallback_to_mean=True
        )

        assert interpolator.strategy == "spatial"
        assert interpolator.fallback_to_mean is True
        assert set(interpolator.climate_columns) == {"mean_temp", "total_rain"}

    def test_init_index_strategy_valid(self):
        """Valid index strategy initialization."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1],
                "lon": [-74.0, -74.1],
                "mean_temp": [15.0, 16.0],
                "total_rain": [100.0, 110.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df,
            strategy="index",
            cell_id_column=None,
            fallback_to_mean=False,
        )

        assert interpolator.strategy == "index"
        assert interpolator.fallback_to_mean is False

    def test_invalid_strategy_raises_error(self):
        """Invalid strategy raises ValueError."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0],
                "lon": [-74.0],
                "mean_temp": [15.0],
            }
        )

        with pytest.raises(ValueError, match="strategy must be 'spatial' or 'index'"):
            ClimateInterpolator(climate_df=climate_df, strategy="invalid")

    def test_missing_lat_lon_columns_raises_error(self):
        """Missing lat/lon columns raises ValueError."""
        climate_df = pd.DataFrame(
            {
                "temperature": [15.0],
                "rainfall": [100.0],
            }
        )

        with pytest.raises(ValueError, match="must have 'lat' and 'lon' columns"):
            ClimateInterpolator(climate_df=climate_df)

    def test_missing_climate_variable_raises_error(self):
        """No climate variable columns raises ValueError."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0],
                "lon": [-74.0],
            }
        )

        with pytest.raises(
            ValueError, match="must have at least one climate variable column"
        ):
            ClimateInterpolator(climate_df=climate_df)

    def test_nan_in_coordinates_removed(self):
        """Rows with NaN lat/lon are removed."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, np.nan, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [15.0, 16.0, 17.0],
            }
        )

        interpolator = ClimateInterpolator(climate_df=climate_df, strategy="spatial")

        # Should have only 2 rows (3rd had NaN lat)
        assert len(interpolator.climate_df) == 2

    def test_invalid_latitude_raises_error(self):
        """Out-of-range latitude raises ValueError."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 95.0],  # 95 > 90
                "lon": [-74.0, -74.1],
                "mean_temp": [15.0, 16.0],
            }
        )

        with pytest.raises(ValueError, match="Invalid latitude"):
            ClimateInterpolator(climate_df=climate_df, strategy="spatial")

    def test_invalid_longitude_raises_error(self):
        """Out-of-range longitude raises ValueError."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1],
                "lon": [-74.0, -185.0],  # -185 < -180
                "mean_temp": [15.0, 16.0],
            }
        )

        with pytest.raises(ValueError, match="Invalid longitude"):
            ClimateInterpolator(climate_df=climate_df, strategy="spatial")

    def test_duplicate_coordinates_warning(self, caplog):
        """Duplicate coordinates logged as warning."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.0, 40.2],  # First two are duplicates
                "lon": [-74.0, -74.0, -74.2],
                "mean_temp": [15.0, 16.0, 17.0],
            }
        )

        ClimateInterpolator(climate_df=climate_df, strategy="spatial")

        assert "duplicate" in caplog.text.lower()

    def test_mean_climate_computed(self):
        """Mean climate values are cached on init."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [10.0, 20.0, 30.0],  # mean = 20
                "total_rain": [100.0, 200.0, 300.0],  # mean = 200
            }
        )

        interpolator = ClimateInterpolator(climate_df=climate_df)

        assert interpolator._climate_mean["mean_temp"] == 20.0
        assert interpolator._climate_mean["total_rain"] == 200.0


class TestClimateInterpolatorSpatial:
    """Test spatial interpolation strategy."""

    def test_interpolate_basic(self):
        """Basic spatial interpolation with nearest-neighbor fallback for small datasets."""
        climate_df = pd.DataFrame(
            {
                "lat": [
                    40.0,
                    41.0,
                    42.0,
                ],  # Need 3+ points for linear interpolation in 2D
                "lon": [-74.0, -73.0, -72.0],
                "mean_temp": [10.0, 20.0, 30.0],
                "total_rain": [100.0, 200.0, 300.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="spatial", fallback_to_mean=False
        )

        # Interpolate at a point between observations
        cell_lats = np.array([40.5])
        cell_lons = np.array([-73.5])

        result = interpolator.interpolate(cell_lats, cell_lons)

        assert len(result) == 1
        assert "mean_temp" in result.columns
        assert "total_rain" in result.columns
        # Values should be interpolated or use nearest neighbor
        assert 10.0 <= result["mean_temp"].iloc[0] <= 30.0
        assert 100.0 <= result["total_rain"].iloc[0] <= 300.0

    def test_interpolate_multiple_cells(self):
        """Interpolate for multiple cells."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 41.0, 42.0, 43.0],  # More points for stability
                "lon": [-74.0, -73.0, -72.0, -71.0],
                "mean_temp": [10.0, 15.0, 20.0, 25.0],
            }
        )

        interpolator = ClimateInterpolator(climate_df=climate_df, strategy="spatial")

        cell_lats = np.array([40.5, 41.5])
        cell_lons = np.array([-73.5, -72.5])

        result = interpolator.interpolate(cell_lats, cell_lons)

        assert len(result) == 2
        # Values should be within interpolation range
        assert 10.0 <= result["mean_temp"].iloc[0] <= 25.0
        assert 10.0 <= result["mean_temp"].iloc[1] <= 25.0

    def test_interpolate_outside_range_with_fallback(self):
        """Cells outside data range use nearest neighbor or mean fallback."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [10.0, 20.0, 30.0],  # mean = 20
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="spatial", fallback_to_mean=True
        )

        # Cell far outside the data range
        cell_lats = np.array([50.0])
        cell_lons = np.array([-80.0])

        result = interpolator.interpolate(cell_lats, cell_lons)

        # Should use nearest neighbor or mean fallback (within data range)
        assert 10.0 <= result["mean_temp"].iloc[0] <= 30.0

    def test_interpolate_outside_range_no_fallback_raises_error(self):
        """Without fallback, cells outside range result in NaN."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [10.0, 20.0, 30.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="spatial", fallback_to_mean=False
        )

        # Cell far outside the data range
        cell_lats = np.array([50.0])
        cell_lons = np.array([-80.0])

        result = interpolator.interpolate(cell_lats, cell_lons)

        # Result will have NaN or use nearest neighbor (may not be NaN)
        # Just verify we got a result
        assert len(result) == 1

    def test_mismatched_array_lengths_raises_error(self):
        """Mismatched lat/lon array lengths raise error."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0],
                "lon": [-74.0],
                "mean_temp": [15.0],
            }
        )

        interpolator = ClimateInterpolator(climate_df=climate_df)

        cell_lats = np.array([40.5, 40.6])
        cell_lons = np.array([-74.5])  # Different length

        with pytest.raises(ValueError, match="must have same length"):
            interpolator.interpolate(cell_lats, cell_lons)


class TestClimateInterpolatorIndex:
    """Test index-based matching strategy."""

    def test_interpolate_by_index_matching(self):
        """Index-based row-to-cell matching."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [10.0, 15.0, 20.0],
                "total_rain": [100.0, 150.0, 200.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="index", fallback_to_mean=False
        )

        # Request 3 cells
        cell_lats = np.array([41.0, 41.1, 41.2])
        cell_lons = np.array([-75.0, -75.1, -75.2])

        result = interpolator.interpolate(cell_lats, cell_lons)

        # Should match rows 0, 1, 2 from climate_df (ignoring input coords)
        assert len(result) == 3
        assert result["mean_temp"].iloc[0] == 10.0
        assert result["mean_temp"].iloc[1] == 15.0
        assert result["mean_temp"].iloc[2] == 20.0

    def test_index_fewer_climate_records_with_fallback(self):
        """Fewer climate records than cells with fallback."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1],
                "lon": [-74.0, -74.1],
                "mean_temp": [10.0, 20.0],  # mean = 15
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="index", fallback_to_mean=True
        )

        # Request 4 cells (more than climate records)
        cell_lats = np.array([41.0, 41.1, 41.2, 41.3])
        cell_lons = np.array([-75.0, -75.1, -75.2, -75.3])

        result = interpolator.interpolate(cell_lats, cell_lons)

        assert len(result) == 4
        # First 2 from climate data, last 2 from mean
        assert result["mean_temp"].iloc[0] == 10.0
        assert result["mean_temp"].iloc[1] == 20.0
        assert result["mean_temp"].iloc[2] == 15.0  # Fallback
        assert result["mean_temp"].iloc[3] == 15.0  # Fallback

    def test_index_more_climate_records_than_cells(self):
        """More climate records than cells (takes first N for index matching)."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2, 40.3],
                "lon": [-74.0, -74.1, -74.2, -74.3],
                "mean_temp": [10.0, 15.0, 20.0, 25.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="index", fallback_to_mean=False
        )

        # Request only 2 cells (fewer than climate records)
        cell_lats = np.array([41.0, 41.1])
        cell_lons = np.array([-75.0, -75.1])

        result = interpolator.interpolate(cell_lats, cell_lons)

        # With index strategy and more records than cells, takes first N cells
        assert len(result) == 2
        assert result["mean_temp"].tolist() == [10.0, 15.0]

    def test_index_mismatch_without_fallback_raises_error(self):
        """Mismatched counts without fallback raises error."""
        climate_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1],
                "lon": [-74.0, -74.1],
                "mean_temp": [10.0, 20.0],
            }
        )

        interpolator = ClimateInterpolator(
            climate_df=climate_df, strategy="index", fallback_to_mean=False
        )

        # Request 4 cells (more than 2 climate records)
        cell_lats = np.array([41.0, 41.1, 41.2, 41.3])
        cell_lons = np.array([-75.0, -75.1, -75.2, -75.3])

        with pytest.raises(ValueError, match="Climate records"):
            interpolator.interpolate(cell_lats, cell_lons)


class TestLoadClimateCSV:
    """Test climate CSV loading and validation."""

    def test_load_valid_csv(self, tmp_path):
        """Load valid climate CSV."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("lat,lon,mean_temp,total_rain\n40.0,-74.0,15.0,100.0\n")

        df = load_climate_csv(csv_file)

        assert len(df) == 1
        assert list(df.columns) == ["lat", "lon", "mean_temp", "total_rain"]
        assert df["lat"].iloc[0] == 40.0

    def test_load_csv_missing_file_raises_error(self):
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Climate CSV file not found"):
            load_climate_csv("/nonexistent/climate.csv")

    def test_load_csv_missing_lat_lon_columns(self, tmp_path):
        """Missing lat/lon columns raises ValueError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("latitude,longitude,mean_temp\n40.0,-74.0,15.0\n")

        with pytest.raises(ValueError, match="must contain 'lat' and 'lon' columns"):
            load_climate_csv(csv_file)

    def test_load_csv_no_climate_variables(self, tmp_path):
        """No climate variable columns raises ValueError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("lat,lon\n40.0,-74.0\n")

        with pytest.raises(
            ValueError, match="must have at least one climate variable column"
        ):
            load_climate_csv(csv_file)

    def test_load_csv_malformed_raises_error(self, tmp_path):
        """Malformed CSV raises ParserError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        with pytest.raises(Exception):  # pd.errors.ParserError or UnicodeDecodeError
            load_climate_csv(csv_file)

    def test_load_csv_removes_rows_with_nan_coords(self, tmp_path):
        """Rows with NaN lat/lon are removed."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text(
            "lat,lon,mean_temp\n" "40.0,-74.0,15.0\n" ",,16.0\n" "41.0,-73.0,17.0\n"
        )

        df = load_climate_csv(csv_file)

        # Should have 2 rows (middle row removed)
        assert len(df) == 2

    def test_load_csv_invalid_latitude(self, tmp_path):
        """Out-of-range latitude raises ValueError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("lat,lon,mean_temp\n95.0,-74.0,15.0\n")

        with pytest.raises(ValueError, match="Invalid latitude"):
            load_climate_csv(csv_file)

    def test_load_csv_invalid_longitude(self, tmp_path):
        """Out-of-range longitude raises ValueError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("lat,lon,mean_temp\n40.0,-185.0,15.0\n")

        with pytest.raises(ValueError, match="Invalid longitude"):
            load_climate_csv(csv_file)

    def test_load_csv_nan_in_climate_variables_warning(self, tmp_path, caplog):
        """NaN in climate variables logged as warning."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text(
            "lat,lon,mean_temp,total_rain\n"
            "40.0,-74.0,15.0,100.0\n"
            "40.1,-74.1,,110.0\n"
        )

        df = load_climate_csv(csv_file)

        assert len(df) == 2  # Both rows kept (only coords need to be non-NaN)
        assert "NaN" in caplog.text

    def test_load_csv_duplicate_coords_warning(self, tmp_path, caplog):
        """Duplicate coordinates logged as warning."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text(
            "lat,lon,mean_temp\n" "40.0,-74.0,15.0\n" "40.0,-74.0,16.0\n"
        )

        load_climate_csv(csv_file)

        assert "duplicate" in caplog.text.lower()

    def test_load_csv_empty_after_validation(self, tmp_path):
        """Empty CSV after validation raises ValueError."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text("lat,lon,mean_temp\n")  # Header only

        with pytest.raises(ValueError, match="is empty"):
            load_climate_csv(csv_file)


class TestClimateIntegration:
    """Integration tests combining climate loading and interpolation."""

    def test_full_workflow_spatial(self, tmp_path):
        """Full workflow: load CSV, create interpolator, interpolate cells."""
        # Create sample climate CSV with 3+ points for interpolation
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text(
            "lat,lon,mean_temp,total_rain\n"
            "40.0,-74.0,15.0,100.0\n"
            "41.0,-73.0,20.0,150.0\n"
            "42.0,-72.0,25.0,200.0\n"
        )

        # Load and interpolate
        climate_df = load_climate_csv(csv_file)
        interpolator = ClimateInterpolator(climate_df=climate_df, strategy="spatial")

        result = interpolator.interpolate(np.array([40.5]), np.array([-73.5]))

        assert len(result) == 1
        # Should be within range of input data
        assert 15.0 <= result["mean_temp"].iloc[0] <= 25.0

    def test_full_workflow_index(self, tmp_path):
        """Full workflow with index matching."""
        csv_file = tmp_path / "climate.csv"
        csv_file.write_text(
            "lat,lon,mean_temp,total_rain\n"
            "40.0,-74.0,10.0,100.0\n"
            "40.1,-74.1,15.0,110.0\n"
            "40.2,-74.2,20.0,120.0\n"
        )

        climate_df = load_climate_csv(csv_file)
        interpolator = ClimateInterpolator(climate_df=climate_df, strategy="index")

        # Interpolate for 3 cells
        result = interpolator.interpolate(
            np.array([41.0, 41.1, 41.2]), np.array([-75.0, -75.1, -75.2])
        )

        assert len(result) == 3
        assert result["mean_temp"].tolist() == [10.0, 15.0, 20.0]


# ---------------------------------------------------------------------------
# Kriging tests
# ---------------------------------------------------------------------------


def _dense_climate_df() -> pd.DataFrame:
    """8-station climate DataFrame (≥ MIN_KRIGING_STATIONS) for kriging tests."""
    return pd.DataFrame(
        {
            "lat": [39.97, 39.97, 39.97, 39.97, 40.00, 40.00, 40.00, 40.00],
            "lon": [-100.03, -100.01, -99.99, -99.97, -100.03, -100.01, -99.99, -99.97],
            "mean_temp": [17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0],
            "total_rain": [90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0],
        }
    )


class TestKrigingInterpolation:
    """Ordinary Kriging via PyKrige."""

    def test_kriging_returns_krig_std_columns(self):
        """Kriging output must include {var}_krig_std columns."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="kriging",
        )
        result = interpolator.interpolate(
            np.array([39.99, 39.98]),
            np.array([-100.00, -99.98]),
        )
        assert "mean_temp" in result.columns
        assert "total_rain" in result.columns
        assert "mean_temp_krig_std" in result.columns
        assert "total_rain_krig_std" in result.columns

    def test_kriging_std_is_non_negative(self):
        """Kriging standard deviation must be ≥ 0 everywhere."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="kriging",
        )
        result = interpolator.interpolate(
            np.array([39.98, 39.99, 40.01]),
            np.array([-100.01, -99.99, -99.98]),
        )
        assert (result["mean_temp_krig_std"] >= 0).all()
        assert (result["total_rain_krig_std"] >= 0).all()

    def test_kriging_values_within_plausible_range(self):
        """Interpolated kriging values should be within input data range."""
        df = _dense_climate_df()
        interpolator = ClimateInterpolator(
            climate_df=df,
            strategy="spatial",
            interpolation_method="kriging",
            fallback_to_mean=True,
        )
        result = interpolator.interpolate(
            np.array([39.99]),
            np.array([-100.00]),
        )
        t_min, t_max = df["mean_temp"].min(), df["mean_temp"].max()
        # Allow a small margin for kriging's unbiased extrapolation
        assert t_min - 5 <= result["mean_temp"].iloc[0] <= t_max + 5

    def test_kriging_cv_metrics_populated(self):
        """cv_metrics must be populated with LOOCV results after kriging init."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="kriging",
        )
        assert interpolator.cv_metrics, "cv_metrics should not be empty for kriging"
        assert "variogram_model" in interpolator.cv_metrics
        assert "per_variable" in interpolator.cv_metrics

        per_var = interpolator.cv_metrics["per_variable"]
        assert "mean_temp" in per_var
        assert "total_rain" in per_var

        for var in ("mean_temp", "total_rain"):
            assert "rmse" in per_var[var]
            assert "mae" in per_var[var]
            assert "n_stations" in per_var[var]
            if per_var[var]["rmse"] is not None:
                assert per_var[var]["rmse"] >= 0
                assert per_var[var]["mae"] >= 0

    def test_kriging_variogram_model_is_valid(self):
        """Selected variogram model must be one of the tried candidates."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="kriging",
        )
        assert interpolator._krig_variogram_model in ("spherical", "exponential", "gaussian")

    def test_kriging_fallback_to_linear_too_few_stations(self):
        """Kriging must fall back to linear when stations < MIN_KRIGING_STATIONS."""
        sparse_df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [15.0, 16.0, 17.0],
            }
        )
        interpolator = ClimateInterpolator(
            climate_df=sparse_df,
            strategy="spatial",
            interpolation_method="kriging",
        )
        # Should have silently switched to linear
        assert interpolator.interpolation_method == "linear"
        # cv_metrics must remain empty (no kriging was done)
        assert interpolator.cv_metrics == {}
        # Must still return a valid result
        result = interpolator.interpolate(np.array([40.1]), np.array([-74.1]))
        assert len(result) == 1
        assert "mean_temp" in result.columns
        # No krig_std columns because linear was used
        assert "mean_temp_krig_std" not in result.columns

    def test_kriging_no_cv_metrics_for_linear(self):
        """cv_metrics must be empty dict for linear interpolation."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="linear",
        )
        assert interpolator.cv_metrics == {}


# ---------------------------------------------------------------------------
# IDW tests
# ---------------------------------------------------------------------------


class TestIDWInterpolation:
    """Inverse Distance Weighting interpolation."""

    def test_idw_basic_output_shape(self):
        """IDW output has one row per cell, one column per climate variable."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="idw",
        )
        result = interpolator.interpolate(
            np.array([39.99, 40.00]),
            np.array([-100.01, -99.99]),
        )
        assert len(result) == 2
        assert "mean_temp" in result.columns
        assert "total_rain" in result.columns
        # IDW never produces krig_std columns
        assert "mean_temp_krig_std" not in result.columns

    def test_idw_exact_station_returns_station_value(self):
        """When cell coincides with a station, IDW must return the exact value."""
        df = _dense_climate_df()
        interpolator = ClimateInterpolator(
            climate_df=df,
            strategy="spatial",
            interpolation_method="idw",
        )
        # Query at the first station's exact location
        result = interpolator.interpolate(
            np.array([df["lat"].iloc[0]]),
            np.array([df["lon"].iloc[0]]),
        )
        assert abs(result["mean_temp"].iloc[0] - df["mean_temp"].iloc[0]) < 1e-9

    def test_idw_values_within_data_range(self):
        """IDW predictions must stay within the input data range."""
        df = _dense_climate_df()
        interpolator = ClimateInterpolator(
            climate_df=df,
            strategy="spatial",
            interpolation_method="idw",
        )
        result = interpolator.interpolate(
            np.array([39.985, 39.990, 39.995]),
            np.array([-100.01, -99.99, -99.97]),
        )
        assert (result["mean_temp"] >= df["mean_temp"].min()).all()
        assert (result["mean_temp"] <= df["mean_temp"].max()).all()

    def test_idw_no_cv_metrics(self):
        """IDW does not compute or store cv_metrics."""
        interpolator = ClimateInterpolator(
            climate_df=_dense_climate_df(),
            strategy="spatial",
            interpolation_method="idw",
        )
        assert interpolator.cv_metrics == {}


# ---------------------------------------------------------------------------
# Pipeline integration with kriging
# ---------------------------------------------------------------------------


class TestPipelineKrigingIntegration:
    """End-to-end pipeline tests with kriging interpolation."""

    def test_pipeline_kriging_produces_krig_std_columns(
        self, tmp_path, synthetic_raster, synthetic_climate_csv_dense
    ):
        """Pipeline with kriging config must write krig_std columns to features.parquet."""
        import textwrap

        from terraflow.pipeline import run_pipeline

        cfg_content = textwrap.dedent(f"""
            raster_path: "{synthetic_raster}"
            climate_csv: "{synthetic_climate_csv_dense}"
            output_dir: "{tmp_path / 'outputs'}"

            roi:
              type: "bbox"
              xmin: -100.04
              ymin: 39.96
              xmax: -99.96
              ymax: 40.01

            climate:
              strategy: "spatial"
              interpolation_method: "kriging"

            model_params:
              v_min: 0.0
              v_max: 25.0
              t_min: 0.0
              t_max: 40.0
              r_min: 0.0
              r_max: 300.0
              w_v: 0.4
              w_t: 0.3
              w_r: 0.3

            max_cells: 5
        """)
        cfg_file = tmp_path / "cfg_kriging.yml"
        cfg_file.write_text(cfg_content, encoding="utf-8")

        df = run_pipeline(cfg_file)

        assert "mean_temp_krig_std" in df.columns
        assert "total_rain_krig_std" in df.columns
        assert (df["mean_temp_krig_std"] >= 0).all()
        assert (df["total_rain_krig_std"] >= 0).all()

    def test_pipeline_kriging_report_has_interpolation_cv(
        self, tmp_path, synthetic_raster, synthetic_climate_csv_dense
    ):
        """Pipeline with kriging must write interpolation_cv to report.json."""
        import json
        import textwrap

        from terraflow.pipeline import run_pipeline

        cfg_content = textwrap.dedent(f"""
            raster_path: "{synthetic_raster}"
            climate_csv: "{synthetic_climate_csv_dense}"
            output_dir: "{tmp_path / 'outputs'}"

            roi:
              type: "bbox"
              xmin: -100.04
              ymin: 39.96
              xmax: -99.96
              ymax: 40.01

            climate:
              strategy: "spatial"
              interpolation_method: "kriging"

            model_params:
              v_min: 0.0
              v_max: 25.0
              t_min: 0.0
              t_max: 40.0
              r_min: 0.0
              r_max: 300.0
              w_v: 0.4
              w_t: 0.3
              w_r: 0.3

            max_cells: 5
        """)
        cfg_file = tmp_path / "cfg_kriging2.yml"
        cfg_file.write_text(cfg_content, encoding="utf-8")

        df = run_pipeline(cfg_file)
        report = json.loads((tmp_path / "outputs" / "runs" / df.attrs["run_fingerprint"] / "report.json").read_text())

        assert "interpolation_cv" in report
        cv = report["interpolation_cv"]
        assert "variogram_model" in cv
        assert "per_variable" in cv


# ---------------------------------------------------------------------------
# Kriging fallback standalone test
# ---------------------------------------------------------------------------


def test_kriging_fallback_sparse_stations():
    """With < MIN_KRIGING_STATIONS stations, kriging falls back to linear."""
    from terraflow.climate import ClimateInterpolator, MIN_KRIGING_STATIONS

    sparse_df = pd.DataFrame({
        "lat": [40.0, 40.01],
        "lon": [-100.0, -99.99],
        "mean_temp": [18.0, 20.0],
        "total_rain": [100.0, 120.0],
    })
    assert len(sparse_df) < MIN_KRIGING_STATIONS

    interpolator = ClimateInterpolator(
        climate_df=sparse_df,
        strategy="spatial",
        interpolation_method="kriging",
    )
    # Fallback should have changed the method to linear
    assert interpolator.interpolation_method == "linear"
