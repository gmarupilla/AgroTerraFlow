from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Literal, Optional, Tuple

import numpy as np
import rasterio
from pydantic import BaseModel, Field
from rasterio.io import DatasetReader

from .geo import clip_raster_to_roi


class RasterSummary(BaseModel):
    """
    Summary statistics for a single-band raster (or ROI subset).

    This model is Pydantic-based so it can be safely serialized to JSON/YAML
    and used in downstream reporting or auditing.
    """

    count: int = Field(..., ge=0, description="Number of valid (unmasked) cells.")
    mean: Optional[float] = Field(
        default=None, description="Mean of the valid cells, if any."
    )
    std: Optional[float] = Field(
        default=None,
        ge=0,
        description="Sample standard deviation (ddof=1) of the valid cells.",
    )
    min: Optional[float] = Field(default=None, description="Minimum valid value.")
    max: Optional[float] = Field(default=None, description="Maximum valid value.")

    @classmethod
    def from_array(cls, arr: np.ma.MaskedArray) -> "RasterSummary":
        """
        Build a RasterSummary from a masked array.
        Entirely masked arrays yield count=0 and all other fields None.
        """
        if arr.count() == 0:
            return cls(count=0, mean=None, std=None, min=None, max=None)

        data = arr.compressed().astype("float64")
        if data.size == 1:
            std_val: Optional[float] = 0.0
        else:
            std_val = float(data.std(ddof=1))

        return cls(
            count=int(data.size),
            mean=float(data.mean()),
            std=std_val,
            min=float(data.min()),
            max=float(data.max()),
        )


class ClimateSummary(BaseModel):
    """
    Simple summary describing climate inputs used for a pipeline run.
    """

    variables: Dict[str, float] = Field(
        default_factory=dict,
        description="Aggregated climate variables (e.g., mean_temp, total_rainfall).",
    )
    n_rows: int = Field(
        default=0, ge=0, description="Number of rows in the input climate CSV."
    )


class RunReport(BaseModel):
    """
    Lightweight, serializable report of a TerraFlow run.

    This is intentionally generic: it does not depend on the internal
    dataframe schema, only on aggregated summaries.
    """

    config_path: Path = Field(description="Path to the configuration file used.")
    raster_path: Path = Field(description="Path to the raster file used.")
    roi: Dict[str, float] = Field(
        description="ROI dictionary with xmin, ymin, xmax, ymax in raster CRS."
    )

    raster_summary: RasterSummary
    climate_summary: ClimateSummary

    n_cells_sampled: int = Field(
        ge=0, description="Number of cells sampled within the ROI."
    )

    @property
    def is_empty_roi(self) -> bool:
        """Convenience flag: True if the ROI resulted in no valid cells."""
        return self.raster_summary.count == 0


def summarize_raster(
    raster: DatasetReader,
    roi: Optional[Dict[str, float]] = None,
    roi_crs: Optional[str] = None,
) -> RasterSummary:
    """
    Compute summary statistics for band 1 of a raster, optionally clipped to an ROI.

    Parameters
    ----------
    raster:
        Open rasterio dataset.
    roi:
        Optional dict with keys xmin, ymin, xmax, ymax.  Coordinates must be
        in the CRS given by *roi_crs*.  When *roi_crs* is ``None`` the
        coordinates are assumed to be in the raster's native CRS.
    roi_crs:
        EPSG code or WKT string for the CRS of the ROI coordinates.  When
        ``None`` (default) the raster's own CRS is used so that native-CRS
        coordinates are accepted without reprojection.
    """
    if roi is not None:
        _roi_crs = roi_crs if roi_crs is not None else raster.crs.to_string()
        data, _ = clip_raster_to_roi(raster, roi, roi_crs=_roi_crs)
    else:
        data = raster.read(1, masked=True)

    return RasterSummary.from_array(data)


def summarize_raster_file(
    raster_path: str | Path,
    roi: Optional[Dict[str, float]] = None,
    roi_crs: Optional[str] = None,
) -> RasterSummary:
    """
    Convenience wrapper: open a raster, summarize it, and close it.

    Parameters
    ----------
    raster_path:
        Path to the raster file.
    roi:
        Optional ROI dict; see :func:`summarize_raster` for details.
    roi_crs:
        CRS of the ROI coordinates; see :func:`summarize_raster` for details.
    """
    raster_path = Path(raster_path)

    with rasterio.open(raster_path) as ds:
        return summarize_raster(ds, roi=roi, roi_crs=roi_crs)


def compare_rasters(
    raster_a: DatasetReader,
    raster_b: DatasetReader,
    roi: Optional[Dict[str, float]] = None,
    roi_crs: Optional[str] = None,
    mode: Literal["difference", "ratio"] = "difference",
) -> Tuple[np.ma.MaskedArray, RasterSummary]:
    """
    Compare two rasters over an optional ROI and return the resulting array
    plus summary statistics.

    Parameters
    ----------
    raster_a, raster_b:
        Open rasterio datasets with the same shape/transform.
    roi:
        Optional ROI dict with keys xmin, ymin, xmax, ymax.  Coordinates must
        be in the CRS given by *roi_crs*.
    roi_crs:
        CRS of the ROI coordinates.  When ``None`` (default) the native CRS of
        *raster_a* is used.
    mode:
        - "difference": compute (a - b)
        - "ratio": compute a / b for non-zero pixels in b
    """
    if roi is not None:
        _roi_crs_a = roi_crs if roi_crs is not None else raster_a.crs.to_string()
        _roi_crs_b = roi_crs if roi_crs is not None else raster_b.crs.to_string()
        arr_a, _ = clip_raster_to_roi(raster_a, roi, roi_crs=_roi_crs_a)
        arr_b, _ = clip_raster_to_roi(raster_b, roi, roi_crs=_roi_crs_b)
    else:
        arr_a = raster_a.read(1, masked=True)
        arr_b = raster_b.read(1, masked=True)

    if arr_a.shape != arr_b.shape:
        raise ValueError(
            f"Raster shapes differ: {arr_a.shape} vs {arr_b.shape}. "
            "Ensure rasters are aligned before comparison."
        )

    if mode == "difference":
        result = arr_a - arr_b
    elif mode == "ratio":
        result = np.ma.divide(arr_a, arr_b)
    else:
        raise ValueError(f"Unsupported mode: {mode!r}")

    return result, RasterSummary.from_array(result)


def batch_summarize(
    raster_paths: Iterable[str | Path],
    roi: Optional[Dict[str, float]] = None,
    roi_crs: Optional[str] = None,
) -> Dict[str, RasterSummary]:
    """
    Summarize a collection of rasters and return a mapping from file stem
    to RasterSummary instances.

    Parameters
    ----------
    raster_paths:
        Iterable of paths to raster files.
    roi:
        Optional ROI dict; see :func:`summarize_raster` for details.
    roi_crs:
        CRS of the ROI coordinates; see :func:`summarize_raster` for details.
    """
    summaries: Dict[str, RasterSummary] = {}

    for path in raster_paths:
        path = Path(path)
        summaries[path.stem] = summarize_raster_file(path, roi=roi, roi_crs=roi_crs)

    return summaries
