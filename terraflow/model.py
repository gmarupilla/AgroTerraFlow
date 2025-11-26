from .config import ModelParams
from .utils import normalize


def suitability_score(
    v_index: float,
    mean_temp: float,
    total_rain: float,
    params: ModelParams,
) -> float:
    """Compute a simple suitability score in [0,1]."""
    v_n = normalize(v_index, params.v_min, params.v_max)
    t_n = normalize(mean_temp, params.t_min, params.t_max)
    r_n = normalize(total_rain, params.r_min, params.r_max)

    score = params.w_v * v_n + params.w_t * t_n + params.w_r * r_n
    return max(0.0, min(1.0, score))


def suitability_label(score: float) -> str:
    """Bucket score into qualitative labels."""
    if score < 0.33:
        return "low"
    if score < 0.66:
        return "medium"
    return "high"
