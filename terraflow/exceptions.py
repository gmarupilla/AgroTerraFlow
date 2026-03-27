"""Custom exception types for TerraFlow."""

from pyproj.exceptions import CRSError


class CRSMismatchError(CRSError):
    """Raised when raster CRS and climate data CRS are incompatible.

    Attributes
    ----------
    raster_crs : str
        WKT or authority string of the raster CRS (or 'None').
    climate_crs : str
        WKT or authority string of the expected climate CRS.
    """

    pass
