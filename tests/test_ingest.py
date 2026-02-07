"""Tests for error handling in the ingest module."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from terraflow.ingest import load_raster, load_climate_csv


class TestLoadRaster:
    """Tests for load_raster function."""

    def test_load_valid_raster(self, tmp_path: Path):
        """Test loading a valid GeoTIFF raster."""
        # Create a valid raster
        raster_path = tmp_path / "valid_raster.tif"
        arr = np.arange(25, dtype="float32").reshape(5, 5)
        transform = from_origin(west=-100.0, north=40.0, xsize=0.01, ysize=0.01)

        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype=arr.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(arr, 1)

        # Load the raster
        dataset = load_raster(raster_path)
        assert dataset is not None
        assert dataset.count >= 1
        dataset.close()

    def test_load_nonexistent_raster(self, tmp_path: Path):
        """Test that loading nonexistent raster raises FileNotFoundError."""
        nonexistent_path = tmp_path / "nonexistent.tif"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_raster(nonexistent_path)

        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_raster(self, tmp_path: Path):
        """Test that loading invalid raster file raises appropriate error."""
        invalid_file = tmp_path / "invalid.tif"
        invalid_file.write_text("This is not a raster file")

        with pytest.raises(Exception):  # RasterioIOError
            dataset = load_raster(invalid_file)
            dataset.close()

    def test_raster_resource_closed_properly(self, tmp_path: Path):
        """Test that raster file handle can be closed without error."""
        raster_path = tmp_path / "test_raster.tif"
        arr = np.arange(9, dtype="float32").reshape(3, 3)
        transform = from_origin(west=0.0, north=0.0, xsize=1.0, ysize=1.0)

        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype=arr.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(arr, 1)

        # Load and close
        dataset = load_raster(raster_path)
        dataset.close()  # Should not raise


class TestLoadClimateCSV:
    """Tests for load_climate_csv function."""

    def test_load_valid_csv(self, tmp_path: Path):
        """Test loading a valid climate CSV with lat/lon."""
        csv_path = tmp_path / "climate.csv"
        df = pd.DataFrame(
            {
                "lat": [40.0, 40.1, 40.2],
                "lon": [-74.0, -74.1, -74.2],
                "mean_temp": [15.0, 16.0, 14.5],
                "total_rain": [100.0, 110.0, 95.0],
            }
        )
        df.to_csv(csv_path, index=False)

        loaded_df = load_climate_csv(csv_path)
        assert len(loaded_df) == 3
        assert "lat" in loaded_df.columns
        assert "lon" in loaded_df.columns
        assert "mean_temp" in loaded_df.columns
        assert "total_rain" in loaded_df.columns

    def test_load_nonexistent_csv(self, tmp_path: Path):
        """Test that loading nonexistent CSV raises FileNotFoundError."""
        nonexistent_path = tmp_path / "nonexistent.csv"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_climate_csv(nonexistent_path)

        assert "not found" in str(exc_info.value).lower()

    def test_load_malformed_csv(self, tmp_path: Path):
        """Test that truly malformed CSV raises appropriate error."""
        csv_path = tmp_path / "malformed.csv"
        # Write truly invalid CSV bytes
        csv_path.write_bytes(b"\x80\x81\x82\x83")

        with pytest.raises(Exception):  # ParserError or UnicodeDecodeError
            load_climate_csv(csv_path)

    def test_load_empty_csv(self, tmp_path: Path):
        """Test loading empty CSV file."""
        csv_path = tmp_path / "empty.csv"
        df = pd.DataFrame({"lat": [], "lon": [], "mean_temp": [], "total_rain": []})
        df.to_csv(csv_path, index=False)

        with pytest.raises(ValueError, match="is empty"):
            load_climate_csv(csv_path)

    def test_load_csv_with_extra_columns(self, tmp_path: Path):
        """Test loading CSV with extra columns beyond required ones."""
        csv_path = tmp_path / "climate_extra.csv"
        df = pd.DataFrame(
            {
                "lat": [40.0],
                "lon": [-74.0],
                "mean_temp": [15.0],
                "total_rain": [100.0],
                "extra_col": ["value"],
            }
        )
        df.to_csv(csv_path, index=False)

        loaded_df = load_climate_csv(csv_path)
        assert len(loaded_df) == 1
        assert len(loaded_df.columns) == 5
