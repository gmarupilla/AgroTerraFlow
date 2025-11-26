import logging
from pathlib import Path

logger = logging.getLogger("terraflow")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def ensure_dir(path: str | Path) -> Path:
    """Create directory if it doesn't exist and return it as a Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def normalize(x: float, xmin: float, xmax: float) -> float:
    """Normalize x into [0,1] given min/max, with safe clamping."""
    if xmax == xmin:
        return 0.0
    val = (x - xmin) / (xmax - xmin)
    return max(0.0, min(1.0, val))
