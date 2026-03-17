import numpy as np

from .config import ModelParams
from .utils import normalize


def suitability_score(
    v_index: float,
    mean_temp: float,
    total_rain: float,
    params: ModelParams,
) -> float:
    """
    Compute a simple suitability score in [0, 1].

    Combines normalized vegetation index, temperature, and rainfall using
    weighted linear combination. All inputs are normalized to [0, 1] range
    based on the parameter min/max bounds, then combined using the weights.

    Parameters
    ----------
    v_index:
        Vegetation index value (typically 0-1, but can be outside range).
    mean_temp:
        Mean temperature in degrees Celsius.
    total_rain:
        Total rainfall in millimeters.
    params:
        Model parameters containing min/max bounds and weights.

    Returns
    -------
    float:
        Suitability score in [0, 1] range.

    Notes
    -----
    - Out-of-range inputs are clipped to [0, 1] during normalization
    - Weights should sum to 1.0 for proper combination
    - Final result is clipped to [0, 1] range
    """
    v_n = normalize(v_index, params.v_min, params.v_max)
    t_n = normalize(mean_temp, params.t_min, params.t_max)
    r_n = normalize(total_rain, params.r_min, params.r_max)

    score = params.w_v * v_n + params.w_t * t_n + params.w_r * r_n
    return max(0.0, min(1.0, score))


def suitability_score_array(
    v_index: "np.ndarray",
    mean_temp: "np.ndarray",
    total_rain: "np.ndarray",
    params: ModelParams,
) -> "np.ndarray":
    """Vectorized suitability scoring over numpy arrays.

    Equivalent to calling :func:`suitability_score` element-wise but operates
    on arbitrary-shape numpy arrays.  Used internally for Monte Carlo
    uncertainty propagation.

    Parameters
    ----------
    v_index:
        Vegetation index values (any shape).
    mean_temp:
        Mean temperature values in °C (same shape as *v_index*).
    total_rain:
        Total rainfall values in mm (same shape as *v_index*).
    params:
        Model parameters containing min/max bounds and weights.

    Returns
    -------
    np.ndarray:
        Suitability scores clipped to [0, 1], same shape as inputs.
    """

    def _norm(x: "np.ndarray", lo: float, hi: float) -> "np.ndarray":
        if hi == lo:
            return np.zeros_like(x, dtype=float)
        return np.clip((x - lo) / (hi - lo), 0.0, 1.0)

    score = (
        params.w_v * _norm(v_index, params.v_min, params.v_max)
        + params.w_t * _norm(mean_temp, params.t_min, params.t_max)
        + params.w_r * _norm(total_rain, params.r_min, params.r_max)
    )
    return np.clip(score, 0.0, 1.0)


def suitability_label(score: float) -> str:
    """
    Bucket suitability score into qualitative labels.

    Parameters
    ----------
    score:
        Suitability score in [0, 1] range.

    Returns
    -------
    str:
        One of 'low', 'medium', or 'high' based on score thresholds.

    Notes
    -----
    - 'low': score < 0.33
    - 'medium': 0.33 <= score < 0.66
    - 'high': score >= 0.66
    """
    if score < 0.33:
        return "low"
    if score < 0.66:
        return "medium"
    return "high"
