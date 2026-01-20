from pathlib import Path
import textwrap

from terraflow.config import load_config


def test_load_config_tmp(tmp_path: Path):
    cfg_content = textwrap.dedent(
        """
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
        """
    )
    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.raster_path.name == "usda_cdl.tif"
    assert cfg.model_params.w_v == 0.4
    assert cfg.roi.type == "bbox"
