"""Tests for terraflow.sensitivity — Sobol' and Morris sensitivity analysis."""
from __future__ import annotations

import json
import re

import pytest
from pathlib import Path

from terraflow.sensitivity import run_sensitivity


@pytest.fixture
def sensitivity_config_path(tmp_path: Path) -> Path:
    """Create a minimal config.yml with sensitivity section for testing."""
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake_raster.tif"
climate_csv: "{tmp_path}/fake_climate.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
sensitivity:
  w_v:
    low: 0.2
    high: 0.5
  w_t:
    low: 0.2
    high: 0.5
  w_r:
    low: 0.1
    high: 0.4
  n_samples: 64
  method: both
""",
        encoding="utf-8",
    )
    return cfg


def _write_config(tmp_path: Path, method: str, n_samples: int = 64) -> Path:
    """Write a minimal config with the given method override."""
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake_raster.tif"
climate_csv: "{tmp_path}/fake_climate.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
sensitivity:
  w_v:
    low: 0.2
    high: 0.5
  w_t:
    low: 0.2
    high: 0.5
  w_r:
    low: 0.1
    high: 0.4
  n_samples: {n_samples}
  method: {method}
""",
        encoding="utf-8",
    )
    return cfg


def test_sobol_produces_s1_st(tmp_path: Path) -> None:
    """run_sensitivity with method=sobol returns report with S1 and ST keys for w_v, w_t, w_r."""
    cfg_path = _write_config(tmp_path, method="sobol")
    run_sensitivity(cfg_path)
    report_path = tmp_path / "outputs" / "sensitivity_report.json"
    assert report_path.exists(), "sensitivity_report.json must be written"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert "sobol" in report, "sobol key must be present for method=sobol"
    sobol = report["sobol"]

    assert "S1" in sobol, "sobol.S1 must be present"
    assert "ST" in sobol, "sobol.ST must be present"
    assert "S1_conf" in sobol, "sobol.S1_conf must be present"
    assert "ST_conf" in sobol, "sobol.ST_conf must be present"

    expected_params = {"w_v", "w_t", "w_r"}
    assert set(sobol["S1"].keys()) == expected_params
    assert set(sobol["ST"].keys()) == expected_params


def test_sobol_index_bounds(tmp_path: Path) -> None:
    """S1 values in [-0.5, 1.5], ST >= 0, confidence intervals >= 0."""
    cfg_path = _write_config(tmp_path, method="sobol", n_samples=64)
    run_sensitivity(cfg_path)
    report = json.loads((tmp_path / "outputs" / "sensitivity_report.json").read_text(encoding="utf-8"))
    sobol = report["sobol"]

    for name in ("w_v", "w_t", "w_r"):
        s1 = sobol["S1"][name]
        st = sobol["ST"][name]
        s1_conf = sobol["S1_conf"][name]
        st_conf = sobol["ST_conf"][name]

        assert isinstance(s1, float), f"S1[{name}] must be float"
        assert -0.5 <= s1 <= 1.5, f"S1[{name}]={s1} outside expected range"
        assert st >= 0.0, f"ST[{name}]={st} must be non-negative"
        assert s1_conf >= 0.0, f"S1_conf[{name}]={s1_conf} must be non-negative"
        assert st_conf >= 0.0, f"ST_conf[{name}]={st_conf} must be non-negative"


def test_morris_produces_mu_star(tmp_path: Path) -> None:
    """run_sensitivity with method=morris produces mu_star, mu, sigma keys."""
    cfg_path = _write_config(tmp_path, method="morris")
    run_sensitivity(cfg_path)
    report = json.loads((tmp_path / "outputs" / "sensitivity_report.json").read_text(encoding="utf-8"))

    assert "morris" in report, "morris key must be present for method=morris"
    morris = report["morris"]

    assert "mu_star" in morris, "morris.mu_star must be present"
    assert "mu" in morris, "morris.mu must be present"
    assert "sigma" in morris, "morris.sigma must be present"

    expected_params = {"w_v", "w_t", "w_r"}
    assert set(morris["mu_star"].keys()) == expected_params

    for name in ("w_v", "w_t", "w_r"):
        assert morris["mu_star"][name] >= 0.0, f"mu_star[{name}] must be >= 0"


def test_report_json_schema(tmp_path: Path) -> None:
    """sensitivity_report.json contains required top-level schema keys."""
    cfg_path = _write_config(tmp_path, method="both")
    run_sensitivity(cfg_path)
    report = json.loads((tmp_path / "outputs" / "sensitivity_report.json").read_text(encoding="utf-8"))

    required_keys = {"schema_version", "method", "n_samples", "parameters", "bounds"}
    for key in required_keys:
        assert key in report, f"Top-level key '{key}' missing from sensitivity_report.json"

    assert report["parameters"] == ["w_v", "w_t", "w_r"]
    assert report["method"] == "both"
    assert report["n_samples"] == 64
    assert "sobol" in report
    assert "morris" in report


def test_report_written_to_output_dir(sensitivity_config_path: Path, tmp_path: Path) -> None:
    """sensitivity_report.json is written to the output_dir path from config."""
    run_sensitivity(sensitivity_config_path)
    report_path = tmp_path / "outputs" / "sensitivity_report.json"
    assert report_path.exists(), "sensitivity_report.json must exist in output_dir"
    # Must be valid JSON
    content = report_path.read_text(encoding="utf-8")
    json.loads(content)  # raises if not valid JSON


def test_method_both_produces_sobol_and_morris(tmp_path: Path) -> None:
    """method=both produces both sobol and morris blocks in report."""
    cfg_path = _write_config(tmp_path, method="both")
    run_sensitivity(cfg_path)
    report = json.loads((tmp_path / "outputs" / "sensitivity_report.json").read_text(encoding="utf-8"))
    assert "sobol" in report, "sobol block must be present for method=both"
    assert "morris" in report, "morris block must be present for method=both"


def test_missing_sensitivity_section_raises(tmp_path: Path) -> None:
    """Config without sensitivity: section raises ValueError containing 'sensitivity'."""
    cfg = tmp_path / "config_no_sens.yml"
    cfg.write_text(
        f"""
raster_path: "{tmp_path}/fake_raster.tif"
climate_csv: "{tmp_path}/fake_climate.csv"
output_dir: "{tmp_path}/outputs"
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=re.compile("sensitivity", re.IGNORECASE)):
        run_sensitivity(cfg)
