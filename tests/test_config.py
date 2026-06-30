import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from terraflow.config import load_config


def test_load_config_tmp(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.raster_path.name == "usda_cdl.tif"
    assert cfg.model_params.w_v == pytest.approx(0.4)
    assert cfg.roi.type == "bbox"


def test_load_config_empty_file(tmp_path: Path):
    cfg_file = tmp_path / "empty.yml"
    cfg_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        load_config(cfg_file)


def test_load_config_invalid_yaml(tmp_path: Path):
    cfg_file = tmp_path / "bad.yml"
    cfg_file.write_text("raster_path: [", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse YAML"):
        load_config(cfg_file)


def test_load_config_invalid_weights(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.5
          w_t: 0.5
          w_r: 0.5
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Weights must sum"):
        load_config(cfg_file)


def test_load_config_invalid_roi_bounds(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 10.0
          ymin: 0.0
          xmax: 0.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with pytest.raises(ValueError, match="xmin"):
        load_config(cfg_file)


def test_load_config_invalid_max_cells(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        max_cells: -5
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with pytest.raises(ValueError, match="max_cells"):
        load_config(cfg_file)


def test_load_config_invalid_raster_band(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        raster_band: 0
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with pytest.raises(ValueError, match="raster_band"):
        load_config(cfg_file)


def test_load_config_kriging_variogram_mode(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        climate:
          strategy: "spatial"
          interpolation_method: "kriging"
          variogram_mode: "extended"
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.climate.variogram_mode == "extended"


# ---------------------------------------------------------------------------
# TemporalAggregation + Scenario + ClimateConfig.temporal_aggregations / scenarios
# (issue #138 — climate-impact flagship)
# ---------------------------------------------------------------------------


def test_temporal_aggregation_annual_mean_no_params():
    from terraflow.config import TemporalAggregation

    cfg = TemporalAggregation(kind="annual_mean")
    assert cfg.kind == "annual_mean"


def test_temporal_aggregation_seasonal_mean_requires_months():
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError, match="months"):
        TemporalAggregation(kind="seasonal_mean")
    cfg = TemporalAggregation(kind="seasonal_mean", months=[4, 5, 6, 7, 8, 9])
    assert cfg.months == [4, 5, 6, 7, 8, 9]


@pytest.mark.parametrize("bad_months", [[0], [13], [1, 12, 13], []])
def test_temporal_aggregation_rejects_invalid_months(bad_months):
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError):
        TemporalAggregation(kind="seasonal_mean", months=bad_months)


def test_temporal_aggregation_gdd_requires_base_temp():
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError, match="base_temp_c"):
        TemporalAggregation(kind="growing_degree_days")
    cfg = TemporalAggregation(kind="growing_degree_days", base_temp_c=10.0)
    assert cfg.base_temp_c == pytest.approx(10.0)


def test_temporal_aggregation_frost_days_requires_threshold():
    from terraflow.config import TemporalAggregation

    cfg = TemporalAggregation(kind="frost_days", threshold_c=0.0)
    assert cfg.threshold_c == pytest.approx(0.0)
    with pytest.raises(ValidationError, match="threshold_c"):
        TemporalAggregation(kind="frost_days")


def test_temporal_aggregation_heat_stress_days_requires_threshold():
    from terraflow.config import TemporalAggregation

    cfg = TemporalAggregation(kind="heat_stress_days", threshold_c=35.0)
    assert cfg.threshold_c == pytest.approx(35.0)


def test_temporal_aggregation_precip_percentile_validates_range():
    from terraflow.config import TemporalAggregation

    cfg = TemporalAggregation(kind="precip_percentile", percentile=95.0)
    assert cfg.percentile == pytest.approx(95.0)
    with pytest.raises(ValidationError):
        TemporalAggregation(kind="precip_percentile", percentile=110.0)
    with pytest.raises(ValidationError):
        TemporalAggregation(kind="precip_percentile", percentile=-1.0)


def test_temporal_aggregation_spei_requires_positive_timescale():
    from terraflow.config import TemporalAggregation

    cfg = TemporalAggregation(kind="spei", timescale_months=3)
    assert cfg.timescale_months == 3
    with pytest.raises(ValidationError):
        TemporalAggregation(kind="spei", timescale_months=0)
    with pytest.raises(ValidationError):
        TemporalAggregation(kind="spei", timescale_months=-1)


def test_temporal_aggregation_rejects_unrelated_params():
    """A kind cannot carry fields belonging to a different kind."""
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError, match="does not accept"):
        TemporalAggregation(kind="annual_mean", months=[1, 2, 3])
    with pytest.raises(ValidationError, match="does not accept"):
        TemporalAggregation(
            kind="growing_degree_days", base_temp_c=10.0, percentile=50.0
        )


def test_temporal_aggregation_rejects_bad_kind():
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError):
        TemporalAggregation(kind="bogus")


def test_temporal_aggregation_rejects_unknown_keys():
    from terraflow.config import TemporalAggregation

    with pytest.raises(ValidationError):
        TemporalAggregation(kind="annual_mean", bogus_key="x")


def test_scenario_valid_minimal():
    from terraflow.config import Scenario

    s = Scenario(name="historical", period=[1991, 2020])
    assert s.name == "historical"
    assert s.period == [1991, 2020]


@pytest.mark.parametrize(
    "bad_period",
    [[], [2000], [2020, 1990], [1700, 1800], [2050, 2300]],
)
def test_scenario_rejects_invalid_period(bad_period):
    from terraflow.config import Scenario

    with pytest.raises(ValidationError):
        Scenario(name="x", period=bad_period)


def test_scenario_rejects_empty_name():
    from terraflow.config import Scenario

    with pytest.raises(ValidationError):
        Scenario(name="", period=[2000, 2010])
    with pytest.raises(ValidationError):
        Scenario(name="   ", period=[2000, 2010])


def test_climate_config_defaults_empty_lists():
    from terraflow.config import ClimateConfig

    cfg = ClimateConfig()
    assert cfg.temporal_aggregations == []
    assert cfg.scenarios == []


def test_climate_config_temporal_aggregations_require_scenarios(tmp_path: Path):
    """When temporal_aggregations is non-empty, scenarios must also be non-empty."""
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        climate:
          temporal_aggregations:
            - kind: annual_mean
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")
    with pytest.raises(ValueError, match="scenarios"):
        load_config(cfg_file)


def test_climate_config_scenarios_must_have_unique_names(tmp_path: Path):
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        climate:
          scenarios:
            - { name: historical, period: [1991, 2020] }
            - { name: historical, period: [2000, 2010] }
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")
    with pytest.raises(ValueError, match="unique names"):
        load_config(cfg_file)


def test_pipeline_config_rejects_climate_impact_without_timeseries_csv(
    tmp_path: Path,
):
    """#138e gate: aggregations require a timeseries_csv input.

    Previously raised NotImplementedError under the #138a gate; now the
    engine ships (#138e) and the gate is a clean ValueError when the user
    forgets the new input field.
    """
    cfg_content = textwrap.dedent("""
        raster_path: "data/usda_cdl.tif"
        climate_csv: "data/demo_climate.csv"
        output_dir: "outputs/demo_run"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 10.0
          ymax: 10.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        climate:
          temporal_aggregations:
            - kind: annual_mean
            - kind: seasonal_mean
              months: [4, 5, 6, 7, 8, 9]
            - kind: growing_degree_days
              base_temp_c: 10.0
            - kind: frost_days
              threshold_c: 0.0
            - kind: heat_stress_days
              threshold_c: 35.0
            - kind: precip_percentile
              percentile: 95.0
            - kind: spei
              timescale_months: 3
          scenarios:
            - { name: historical, period: [1991, 2020] }
            - { name: ssp245, period: [2041, 2070] }
            - { name: ssp585, period: [2041, 2070] }
        """)
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    with pytest.raises(ValueError, match="timeseries_csv"):
        load_config(cfg_file)


def test_climate_config_models_parse_directly():
    """The Pydantic models themselves accept the full shape — only the
    PipelineConfig-level gate rejects until #138b lands. This keeps the
    schema introspectable for tooling and docs."""
    from terraflow.config import ClimateConfig, Scenario, TemporalAggregation

    cfg = ClimateConfig(
        temporal_aggregations=[
            TemporalAggregation(kind="annual_mean"),
            TemporalAggregation(kind="seasonal_mean", months=[4, 5, 6, 7, 8, 9]),
            TemporalAggregation(kind="growing_degree_days", base_temp_c=10.0),
            TemporalAggregation(kind="frost_days", threshold_c=0.0),
            TemporalAggregation(kind="heat_stress_days", threshold_c=35.0),
            TemporalAggregation(kind="precip_percentile", percentile=95.0),
            TemporalAggregation(kind="spei", timescale_months=3),
        ],
        scenarios=[
            Scenario(name="historical", period=[1991, 2020]),
            Scenario(name="ssp245", period=[2041, 2070]),
            Scenario(name="ssp585", period=[2041, 2070]),
        ],
    )
    assert len(cfg.temporal_aggregations) == 7
    assert len(cfg.scenarios) == 3
    assert cfg.scenarios[0].period == [1991, 2020]
    assert cfg.temporal_aggregations[1].months == [4, 5, 6, 7, 8, 9]
