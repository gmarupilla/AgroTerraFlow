from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin


@pytest.fixture
def synthetic_climate_csv_dense(tmp_path: Path) -> Path:
    """Climate CSV with 8 stations — enough for kriging (≥ MIN_KRIGING_STATIONS=5)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "synthetic_climate_dense.csv"

    # 2×4 grid of stations spanning the synthetic raster extent
    df = pd.DataFrame(
        {
            "lat": [39.97, 39.97, 39.97, 39.97, 40.00, 40.00, 40.00, 40.00],
            "lon": [-100.03, -100.01, -99.99, -99.97, -100.03, -100.01, -99.99, -99.97],
            "mean_temp": [17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0],
            "total_rain": [90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0],
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def synthetic_raster(tmp_path: Path) -> Path:
    """Create a small synthetic GeoTIFF raster for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    raster_path = data_dir / "synthetic_raster.tif"

    # 5x5 synthetic grid with values 0..24
    arr = np.arange(25, dtype="float32").reshape(5, 5)

    transform = from_origin(
        west=-100.0,  # origin lon
        north=40.0,  # origin lat
        xsize=0.01,  # pixel width
        ysize=0.01,  # pixel height
    )

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

    return raster_path


@pytest.fixture
def synthetic_climate_csv(tmp_path: Path) -> Path:
    """Create a small synthetic climate CSV for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "synthetic_climate.csv"

    df = pd.DataFrame(
        {
            "lat": [40.0, 40.01, 40.02],
            "lon": [-100.0, -99.99, -99.98],
            "mean_temp": [18.0, 19.0, 20.0],
            "total_rain": [100.0, 120.0, 140.0],
        }
    )
    df.to_csv(csv_path, index=False)

    return csv_path


@pytest.fixture
def synthetic_climate_csv_sparse(tmp_path: Path) -> Path:
    """Climate CSV with only 2 stations — below MIN_KRIGING_STATIONS=5 threshold."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "synthetic_climate_sparse.csv"
    df = pd.DataFrame(
        {
            "lat": [40.0, 40.01],
            "lon": [-100.0, -99.99],
            "mean_temp": [18.0, 20.0],
            "total_rain": [100.0, 120.0],
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path
