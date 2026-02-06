"""Utility functions for TerraFlow."""

import logging
from pathlib import Path

logger = logging.getLogger("terraflow")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def ensure_dir(path: str | Path) -> Path:
    """
    Create directory if it doesn't exist and return it as a Path.
    
    Parameters
    ----------
    path:
        Directory path to create.
    
    Returns
    -------
    Path:
        The created (or existing) directory path.
    
    Raises
    ------
    OSError:
        If the directory cannot be created (e.g., permission error).
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def normalize(x: float, xmin: float, xmax: float) -> float:
    """
    Normalize x into [0, 1] given min/max bounds with safe clamping.
    
    Maps values in the range [xmin, xmax] to [0, 1]. Values outside this
    range are clipped to the [0, 1] bounds.
    
    Parameters
    ----------
    x:
        Value to normalize.
    xmin:
        Minimum bound of the range.
    xmax:
        Maximum bound of the range.
    
    Returns
    -------
    float:
        Normalized value in [0, 1].
    
    Notes
    -----
    - If xmin == xmax, returns 0.0 (no gradient to normalize)
    - Results are always clamped to [0, 1] range
    
    Examples
    --------
    >>> normalize(50, 0, 100)
    0.5
    >>> normalize(150, 0, 100)
    1.0
    >>> normalize(-10, 0, 100)
    0.0
    """
    if xmax == xmin:
        return 0.0
    val = (x - xmin) / (xmax - xmin)
    return max(0.0, min(1.0, val))
