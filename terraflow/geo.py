from typing import Any, Dict, Tuple

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.io import DatasetReader
from rasterio.windows import from_bounds
from rasterio.windows import Window

from .utils import logger


def clip_raster_to_roi(
    raster: DatasetReader,
    roi: Dict[str, Any],
    roi_crs: str = "EPSG:4326",
) -> Tuple[np.ma.MaskedArray, rasterio.Affine]:
    """
    Clip a raster to the region of interest and return data & transform.

    Parameters
    ----------
    raster:
        Open rasterio dataset.
    roi:
        Dictionary with keys: xmin, ymin, xmax, ymax.  Coordinates must be
        in the CRS specified by *roi_crs* (default EPSG:4326 / WGS 84).
    roi_crs:
        EPSG code or WKT string for the CRS of the ROI coordinates.
        Defaults to ``"EPSG:4326"`` (latitude/longitude degrees).  When the
        raster is in a different CRS the ROI is automatically reprojected
        before clipping.

    Returns
    -------
    data:
        A masked array (band 1) containing the clipped raster values.
    transform:
        Affine transform corresponding to the clipped window.

    Raises
    ------
    ValueError:
        If raster does not have band 1, ROI bounds are invalid, or the
        (reprojected) ROI does not intersect the raster extent.
    """
    # Validate that band 1 exists
    if raster.count < 1:
        raise ValueError("Raster has no bands. Cannot read band 1.")

    # Validate ROI bounds before any reprojection
    if roi["xmin"] >= roi["xmax"] or roi["ymin"] >= roi["ymax"]:
        raise ValueError(
            f"Invalid ROI bounds: xmin={roi['xmin']}, xmax={roi['xmax']}, "
            f"ymin={roi['ymin']}, ymax={roi['ymax']}. "
            f"Require xmin < xmax and ymin < ymax."
        )

    xmin, ymin, xmax, ymax = roi["xmin"], roi["ymin"], roi["xmax"], roi["ymax"]

    # Reproject ROI bounds to raster CRS when they differ.
    raster_crs = raster.crs
    src_crs = CRS.from_user_input(roi_crs)
    if src_crs != raster_crs:
        transformer = Transformer.from_crs(src_crs, raster_crs, always_xy=True)
        # Transform all 4 corners so non-linear projections are handled correctly,
        # then take the axis-aligned bounding box of the results.
        corners_x = [xmin, xmin, xmax, xmax]
        corners_y = [ymin, ymax, ymin, ymax]
        xs, ys = transformer.transform(corners_x, corners_y)
        xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)
        logger.info(
            "Reprojected ROI from %s to raster CRS %s: "
            "xmin=%.2f ymin=%.2f xmax=%.2f ymax=%.2f",
            roi_crs,
            raster_crs.to_epsg() or "custom",
            xmin,
            ymin,
            xmax,
            ymax,
        )

    # Compute rasterio window from the (reprojected) bounds.
    try:
        window: Window = from_bounds(
            xmin, ymin, xmax, ymax, transform=raster.transform
        )
    except Exception as e:
        raise ValueError(
            f"Could not compute raster window for ROI bounds "
            f"({xmin:.4f}, {ymin:.4f}, {xmax:.4f}, {ymax:.4f}): {e}. "
            f"Check roi_crs='{roi_crs}' and that the ROI overlaps the raster."
        ) from e

    # Guard against degenerate windows (NaN dimensions) that arise when
    # reprojected bounds are numerically invalid (e.g. coordinates outside
    # the valid domain of the target CRS).
    import math
    if math.isnan(window.width) or math.isnan(window.height):
        raise ValueError(
            f"ROI bounds ({xmin}, {ymin}, {xmax}, {ymax}) produced a "
            f"degenerate window after reprojection. "
            f"Check that roi_crs='{roi_crs}' is correct and that the ROI "
            f"coordinates are valid in that CRS."
        )

    # Read the windowed data.
    data = raster.read(1, window=window, masked=True)
    transform = raster.window_transform(window)

    if data.size == 0:
        raise ValueError(
            f"ROI does not intersect the raster (raster extent: {raster.bounds}). "
            f"Verify that roi_crs='{roi_crs}' matches the coordinate system of "
            f"your xmin/ymin/xmax/ymax values."
        )

    return data, transform
