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

    roi = {
        "xmin": 0,
        "ymin": 0,
        "xmax": 1000,
        "ymax": 1000,
    }

    summary = summarize_raster_file(raster_path, roi=roi)

    assert summary.count >= 0
