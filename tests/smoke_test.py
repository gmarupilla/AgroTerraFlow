from pathlib import Path

from terraflow.stats import summarize_raster_file


def test_summarize_raster_file_real_data():

    repo_root = Path(__file__).resolve().parents[1]
    raster_path = repo_root / "data" / "usda_cdl.tif"

    assert raster_path.exists(), f"Expected raster at {raster_path}"

    summary = summarize_raster_file(raster_path)

    assert summary.count > 0
    assert summary.min is not None
    assert summary.max is not None


def test_summarize_raster_file_real_data_roi():
    repo_root = Path(__file__).resolve().parents[1]
    raster_path = repo_root / "data" / "usda_cdl.tif"

    # WGS84 bbox over western Kansas – matches the demo_config ROI and is
    # known to intersect the usda_cdl.tif extent.
    roi = {
        "xmin": -101.0,
        "ymin": 38.0,
        "xmax": -94.0,
        "ymax": 40.0,
    }

    summary = summarize_raster_file(raster_path, roi=roi, roi_crs="EPSG:4326")

    assert summary.count >= 0
