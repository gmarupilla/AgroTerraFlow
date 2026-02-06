from typing import Dict, Tuple

import numpy as np
import rasterio
from rasterio.io import DatasetReader
from rasterio.windows import from_bounds
from rasterio.windows import Window


def clip_raster_to_roi(
    raster: DatasetReader,
    roi: Dict[str, float],
) -> Tuple[np.ma.MaskedArray, rasterio.Affine]:
    """
    Clip a raster to the region of interest and return data & transform.

    Parameters
    ----------
    raster:
        Open rasterio dataset.
    roi:
        Dictionary with keys: xmin, ymin, xmax, ymax (in the raster CRS).

    Returns
    -------
    data:
        A masked array (band 1) containing the clipped raster values.
    transform:
        Affine transform corresponding to the clipped window.

    Raises
    ------
    ValueError:
        If raster does not have band 1 or if ROI bounds are invalid.

    Notes
    -----
    If the ROI does not intersect the raster (for example, due to a CRS
    mismatch or out-of-bounds coordinates), this function gracefully falls
    back to returning the full raster band and its original transform.
    """
    # Validate that band 1 exists
    if raster.count < 1:
        raise ValueError(f"Raster has no bands. Cannot read band 1.")
    
    # Validate ROI bounds
    if roi["xmin"] >= roi["xmax"] or roi["ymin"] >= roi["ymax"]:
        raise ValueError(
            f"Invalid ROI bounds: xmin={roi['xmin']}, xmax={roi['xmax']}, "
            f"ymin={roi['ymin']}, ymax={roi['ymax']}. "
            f"Require xmin < xmax and ymin < ymax."
        )
    
    # Default: read full raster
    full_data = raster.read(1, masked=True)
    full_transform = raster.transform

    # Try to compute a window from the ROI bounds
    try:
        window: Window = from_bounds(
            roi["xmin"],
            roi["ymin"],
            roi["xmax"],
            roi["ymax"],
            transform=raster.transform,
        )
    except (IndexError, ValueError) as e:
        # If ROI doesn't intersect raster, return full raster
        from .utils import logger
        logger.warning(
            f"ROI does not intersect raster or invalid bounds: {e}. "
            f"Returning full raster."
        )
        return full_data, full_transform

    # Read the windowed data
    data = raster.read(1, window=window, masked=True)
    transform = raster.window_transform(window)

    # If all values are masked or the window is effectively empty,
    # fall back to the full raster.
    if data.size == 0 or np.ma.getmaskarray(data).all():
        return full_data, full_transform

    return data, transform
