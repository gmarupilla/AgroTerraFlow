import pytest

from terraflow.utils import normalize


def test_normalize_clamps_out_of_range():
    assert normalize(150, 0, 100) == pytest.approx(1.0)
    assert normalize(-10, 0, 100) == pytest.approx(0.0)


def test_normalize_zero_range():
    assert normalize(10, 5, 5) == pytest.approx(0.0)
