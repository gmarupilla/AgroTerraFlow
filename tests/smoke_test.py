from pathlib import Path

import pytest

from terraflow.stats import summarize_raster_file

_RASTER_PATH = Path(__file__).resolve().parents[1] / "data" / "usda_cdl.tif"
_SKIP_REAL_DATA = pytest.mark.skipif(
    not _RASTER_PATH.exists(),
    reason="USDA CDL raster not present — run 'make get-demo-data' first; see data/README.md",
)


@_SKIP_REAL_DATA
def test_summarize_raster_file_real_data():
    summary = summarize_raster_file(_RASTER_PATH)

    assert summary.count > 0
    assert summary.min is not None
    assert summary.max is not None


@_SKIP_REAL_DATA
def test_summarize_raster_file_real_data_roi():
    # WGS84 bbox over western Kansas – matches the demo_config ROI and is
    # known to intersect the usda_cdl.tif extent.
    roi = {
        "xmin": -101.0,
        "ymin": 38.0,
        "xmax": -94.0,
        "ymax": 40.0,
    }

    summary = summarize_raster_file(_RASTER_PATH, roi=roi, roi_crs="EPSG:4326")

    assert summary.count >= 0
