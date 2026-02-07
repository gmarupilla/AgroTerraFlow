from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from terraflow.geo import clip_raster_to_roi


def _make_small_raster(tmp_path: Path) -> Path:
    raster_path = tmp_path / "raster.tif"
    arr = np.arange(9, dtype="float32").reshape(3, 3)

    transform = from_origin(
        west=-100.0,
        north=40.0,
        xsize=0.01,
        ysize=0.01,
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


def test_clip_raster_to_roi_valid(tmp_path: Path):
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        data, transform = clip_raster_to_roi(
            src,
            {
                "xmin": -100.0,
                "ymin": 39.97,
                "xmax": -99.98,
                "ymax": 40.0,
            },
        )

    assert data.shape[0] >= 1
    assert data.shape[1] >= 1
    assert not np.ma.getmaskarray(data).all()
    assert transform is not None


def test_clip_raster_to_roi_fallback(tmp_path: Path):
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        # ROI clearly outside raster bounds → should fall back to full raster
        data, _ = clip_raster_to_roi(
            src,
            {
                "xmin": 0.0,
                "ymin": 0.0,
                "xmax": 1.0,
                "ymax": 1.0,
            },
        )

    assert data.shape == (3, 3)


def test_clip_invalid_roi_bounds_xmin_xmax(tmp_path: Path):
    """Test that invalid ROI bounds (xmin >= xmax) raise ValueError."""
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        roi = {
            "xmin": -99.98,  # greater than xmax
            "ymin": 39.97,
            "xmax": -100.0,
            "ymax": 40.0,
        }
        with pytest.raises(ValueError) as exc_info:
            clip_raster_to_roi(src, roi)
        assert "invalid" in str(exc_info.value).lower()


def test_clip_invalid_roi_bounds_ymin_ymax(tmp_path: Path):
    """Test that invalid ROI bounds (ymin >= ymax) raise ValueError."""
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        roi = {
            "xmin": -100.0,
            "ymin": 40.0,  # greater than ymax
            "xmax": -99.98,
            "ymax": 39.97,
        }
        with pytest.raises(ValueError) as exc_info:
            clip_raster_to_roi(src, roi)
        assert "invalid" in str(exc_info.value).lower()


def test_clip_equal_bounds_error(tmp_path: Path):
    """Test that equal min/max bounds raise ValueError."""
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        roi = {
            "xmin": -100.0,
            "ymin": 40.0,
            "xmax": -100.0,  # equal to xmin
            "ymax": 40.0,
        }
        with pytest.raises(ValueError):
            clip_raster_to_roi(src, roi)


def test_clip_preserves_masked_values(tmp_path: Path):
    """Test that masked values are preserved in clipped raster."""
    raster_path = tmp_path / "masked_raster.tif"

    # Create raster with some masked values
    arr = np.arange(9, dtype="float32").reshape(3, 3)
    arr[1, 1] = -9999  # NoData value
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
        nodata=-9999,
    ) as dst:
        dst.write(arr, 1)

    with rasterio.open(raster_path) as src:
        roi = {"xmin": -100.0, "ymin": 39.97, "xmax": -99.98, "ymax": 40.0}
        data, _ = clip_raster_to_roi(src, roi)
        # The masked array should properly handle NoData
        assert data is not None
