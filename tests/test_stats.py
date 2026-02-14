from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
import pytest

from terraflow.stats import (
    RasterSummary,
    summarize_raster,
    summarize_raster_file,
    compare_rasters,
    batch_summarize,
)


def _create_dummy_raster(tmp_path: Path, values: np.ndarray, name: str) -> Path:
    path = tmp_path / name
    h, w = values.shape
    transform = from_origin(0, 10, 1, 1)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=values.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(values, 1)

    return path


def test_raster_summary_from_array_basic():
    arr = np.ma.array([1, 2, 3, 4], mask=[0, 0, 0, 0])
    summary = RasterSummary.from_array(arr)

    assert summary.count == 4
    assert summary.mean == 2.5
    assert summary.min == 1.0
    assert summary.max == 4.0
    assert summary.std is not None


def test_raster_summary_single_value_std_zero():
    arr = np.ma.array([5], mask=[0])
    summary = RasterSummary.from_array(arr)

    assert summary.count == 1
    assert summary.std == 0.0


def test_summarize_raster_and_file(tmp_path: Path):
    values = np.arange(9, dtype="float32").reshape(3, 3)
    raster_path = _create_dummy_raster(tmp_path, values, "base.tif")

    with rasterio.open(raster_path) as ds:
        summary = summarize_raster(ds)

    assert summary.count == 9
    assert summary.min == 0.0
    assert summary.max == 8.0

    summary2 = summarize_raster_file(raster_path)
    assert summary2.count == summary.count


def test_compare_rasters_difference(tmp_path: Path):
    base = np.ones((3, 3), dtype="float32")
    doubled = base * 2

    path_a = _create_dummy_raster(tmp_path, base, "base.tif")
    path_b = _create_dummy_raster(tmp_path, doubled, "doubled.tif")

    with rasterio.open(path_a) as ds_a, rasterio.open(path_b) as ds_b:
        diff, summary = compare_rasters(ds_a, ds_b, mode="difference")

    assert diff.shape == base.shape
    assert np.allclose(diff.compressed(), -1.0)
    assert summary.min == -1.0
    assert summary.max == -1.0


def test_compare_rasters_ratio(tmp_path: Path):
    base = np.ones((3, 3), dtype="float32")
    doubled = base * 2

    path_a = _create_dummy_raster(tmp_path, base, "base.tif")
    path_b = _create_dummy_raster(tmp_path, doubled, "doubled.tif")

    with rasterio.open(path_a) as ds_a, rasterio.open(path_b) as ds_b:
        ratio, summary = compare_rasters(ds_a, ds_b, mode="ratio")

    assert np.allclose(ratio.compressed(), 0.5)
    assert summary.min == 0.5
    assert summary.max == 0.5


def test_compare_rasters_shape_mismatch(tmp_path: Path):
    a = np.ones((2, 2), dtype="float32")
    b = np.ones((3, 3), dtype="float32")

    path_a = _create_dummy_raster(tmp_path, a, "a.tif")
    path_b = _create_dummy_raster(tmp_path, b, "b.tif")

    with rasterio.open(path_a) as ds_a, rasterio.open(path_b) as ds_b:
        with pytest.raises(ValueError, match="Raster shapes differ"):
            compare_rasters(ds_a, ds_b, mode="difference")


def test_compare_rasters_invalid_mode(tmp_path: Path):
    base = np.ones((2, 2), dtype="float32")
    path = _create_dummy_raster(tmp_path, base, "base.tif")

    with rasterio.open(path) as ds_a, rasterio.open(path) as ds_b:
        with pytest.raises(ValueError, match="Unsupported mode"):
            compare_rasters(ds_a, ds_b, mode="invalid")  # type: ignore[arg-type]


def test_batch_summarize(tmp_path: Path):
    a = np.ones((2, 2), dtype="float32")
    b = np.ones((2, 2), dtype="float32") * 3

    path_a = _create_dummy_raster(tmp_path, a, "alpha.tif")
    path_b = _create_dummy_raster(tmp_path, b, "beta.tif")

    summaries = batch_summarize([path_a, path_b])

    assert set(summaries.keys()) == {"alpha", "beta"}
    assert summaries["alpha"].mean == 1.0
    assert summaries["beta"].mean == 3.0
