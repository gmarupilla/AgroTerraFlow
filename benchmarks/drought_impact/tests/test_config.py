import pytest

from drought_impact.config import BenchmarkConfig, RmaSource, build_config


def test_defaults_are_six_state_corn():
    cfg = BenchmarkConfig()
    cfg.validate_all()
    assert set(cfg.states) == {"17", "18", "19", "27", "29", "31"}
    assert cfg.crop == "CORN"
    assert cfg.season_start_doy < cfg.cutoff_doy


def test_rma_source_url_for():
    src = RmaSource()
    url = src.url_for(2012)
    assert url.endswith("colsom_2012.zip")


def test_rma_source_template_requires_year():
    with pytest.raises(ValueError):
        RmaSource(filename_template="colsom.zip")


def test_validate_all_rejects_bad_window():
    cfg = BenchmarkConfig(season_start_doy=200, cutoff_doy=100)
    with pytest.raises(ValueError):
        cfg.validate_all()


def test_validate_all_rejects_test_year_out_of_range():
    cfg = BenchmarkConfig(year_min=2000, year_max=2010, temporal_test_years=[2012])
    with pytest.raises(ValueError):
        cfg.validate_all()


def test_extra_fields_forbidden():
    with pytest.raises(ValueError):
        build_config({"crop": "CORN", "unexpected_key": 1})


def test_fingerprint_dict_stable_and_order_independent():
    a = BenchmarkConfig(states=["17", "19"]).as_fingerprint_dict()
    b = BenchmarkConfig(states=["19", "17"]).as_fingerprint_dict()
    assert a == b  # states sorted → order independent
