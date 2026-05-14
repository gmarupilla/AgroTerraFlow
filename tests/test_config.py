import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from terraflow.config import GeoAIConfig, load_config


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
# GeoAIConfig (issue #91 — foundation for `terraflow geoai` subcommand)
# ---------------------------------------------------------------------------


def test_geoai_config_defaults_valid():
    cfg = GeoAIConfig(engine="landcover")
    assert cfg.engine == "landcover"
    assert cfg.chip_size == 512
    assert cfg.confidence_threshold == 0.5
    assert cfg.batch_size == 4


def test_geoai_config_rejects_bad_engine():
    with pytest.raises(ValidationError):
        GeoAIConfig(engine="bogus")


@pytest.mark.parametrize("size", [64, 128, 256, 512, 1024, 2048])
def test_geoai_config_accepts_pow2_chip_sizes(size: int):
    cfg = GeoAIConfig(engine="fields", chip_size=size)
    assert cfg.chip_size == size


@pytest.mark.parametrize("size", [0, -1, 3, 500, 513])
def test_geoai_config_rejects_non_pow2_chip_size(size: int):
    with pytest.raises(ValidationError, match="chip_size"):
        GeoAIConfig(engine="fields", chip_size=size)


@pytest.mark.parametrize("threshold", [-0.1, 1.1, 2.0])
def test_geoai_config_rejects_out_of_range_threshold(threshold: float):
    with pytest.raises(ValidationError, match="confidence_threshold"):
        GeoAIConfig(engine="canopy", confidence_threshold=threshold)


@pytest.mark.parametrize("batch", [0, -1, -100])
def test_geoai_config_rejects_non_positive_batch_size(batch: int):
    with pytest.raises(ValidationError, match="batch_size"):
        GeoAIConfig(engine="fields", batch_size=batch)


def test_geoai_config_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        GeoAIConfig(engine="fields", bogus_key=1)


def test_pipeline_config_accepts_optional_geoai_block(tmp_path: Path):
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
        geoai:
          engine: "landcover"
          chip_size: 256
          confidence_threshold: 0.75
          batch_size: 8
        """)

    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.geoai is not None
    assert cfg.geoai.engine == "landcover"
    assert cfg.geoai.chip_size == 256
    assert cfg.geoai.confidence_threshold == 0.75
    assert cfg.geoai.batch_size == 8


def test_pipeline_config_geoai_defaults_to_none(tmp_path: Path):
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
    assert cfg.geoai is None
