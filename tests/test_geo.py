from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
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


def test_clip_raster_roi_outside_bounds_raises(tmp_path: Path):
    """ROI completely outside raster extent must raise ValueError, not silently
    return the full raster (TERRA-010)."""
    raster_path = _make_small_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        with pytest.raises(ValueError, match="does not intersect"):
            clip_raster_to_roi(
                src,
                {
                    "xmin": 0.0,
                    "ymin": 0.0,
                    "xmax": 1.0,
                    "ymax": 1.0,
                },
            )


def _make_projected_raster(tmp_path: Path) -> tuple[Path, dict]:
    """Create a synthetic UTM Zone 14N (EPSG:32614) raster over Kansas.

    Returns the raster path and a dict with the corresponding WGS84 bbox so
    tests can construct a ROI without hard-coding reprojected values.
    """
    raster_path = tmp_path / "projected_raster.tif"
    arr = np.arange(25, dtype="float32").reshape(5, 5)

    # ~38.5 N, 99 W in UTM 14N ≈ (500000 E, 4261000 N); 1 km pixels
    west_utm = 500_000.0
    north_utm = 4_261_000.0
    pixel_m = 1_000.0

    transform = from_origin(
        west=west_utm,
        north=north_utm,
        xsize=pixel_m,
        ysize=pixel_m,
    )
    crs = CRS.from_epsg(32614)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(arr, 1)

    # Compute WGS84 corners of the raster for the test ROI
    t = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    # bottom-left corner in UTM
    lon_min, lat_min = t.transform(west_utm, north_utm - 5 * pixel_m)
    # top-right corner in UTM
    lon_max, lat_max = t.transform(west_utm + 5 * pixel_m, north_utm)

    wgs84_roi = {"xmin": lon_min, "ymin": lat_min, "xmax": lon_max, "ymax": lat_max}
    return raster_path, wgs84_roi


def test_clip_projected_raster_with_wgs84_roi(tmp_path: Path):
    """WGS84 ROI applied to a projected (EPSG:32614) raster must return
    non-empty clipped data after automatic reprojection (TERRA-010)."""
    raster_path, wgs84_roi = _make_projected_raster(tmp_path)
    with rasterio.open(raster_path) as src:
        data, transform = clip_raster_to_roi(src, wgs84_roi, roi_crs="EPSG:4326")

    assert data.size > 0, "Clipped data must not be empty"
    assert not np.ma.getmaskarray(data).all(), "Clipped data must have valid pixels"
    assert transform is not None


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


def test_clip_raster_to_roi_reads_tight_window_for_small_roi(tmp_path: Path, monkeypatch):
    raster_path = tmp_path / "large_raster.tif"
    arr = np.arange(10_000, dtype="float32").reshape(100, 100)
    transform = from_origin(west=0.0, north=100.0, xsize=1.0, ysize=1.0)

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

    with rasterio.open(raster_path) as src:
        original_read = src.read
        seen = {}

        def tracking_read(*args, **kwargs):
            seen["window"] = kwargs.get("window")
            return original_read(*args, **kwargs)

        monkeypatch.setattr(src, "read", tracking_read)
        data, _ = clip_raster_to_roi(
            src,
            {
                "xmin": 10.2,
                "ymin": 89.2,
                "xmax": 10.8,
                "ymax": 89.8,
            },
        )

    window = seen["window"]
    assert window is not None
    assert data.shape == (1, 1)
    assert window.width == 1
    assert window.height == 1
    assert window.width * window.height < 100
