from terraflow.utils import normalize


def test_normalize_clamps_out_of_range():
    assert normalize(150, 0, 100) == 1.0
    assert normalize(-10, 0, 100) == 0.0


def test_normalize_zero_range():
    assert normalize(10, 5, 5) == 0.0
