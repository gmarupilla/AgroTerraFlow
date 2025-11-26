from terraflow.config import ModelParams
from terraflow.model import suitability_score, suitability_label


def _default_params() -> ModelParams:
    return ModelParams(
        v_min=0.0,
        v_max=255.0,
        t_min=0.0,
        t_max=40.0,
        r_min=0.0,
        r_max=300.0,
        w_v=0.4,
        w_t=0.3,
        w_r=0.3,
    )


def test_suitability_score_range():
    params = _default_params()

    score = suitability_score(
        v_index=128.0,
        mean_temp=20.0,
        total_rain=150.0,
        params=params,
    )
    assert 0.0 <= score <= 1.0


def test_suitability_label_buckets():
    assert suitability_label(0.0) == "low"
    assert suitability_label(0.2) == "low"
    assert suitability_label(0.5) == "medium"
    assert suitability_label(0.65) == "medium"
    assert suitability_label(0.9) == "high"


def test_suitability_monotonic_in_v_index():
    params = _default_params()

    low = suitability_score(10.0, 20.0, 150.0, params)
    high = suitability_score(200.0, 20.0, 150.0, params)

    assert high >= low
