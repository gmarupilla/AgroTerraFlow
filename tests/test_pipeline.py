from pathlib import Path
import textwrap

from terraflow.pipeline import run_pipeline


def test_run_pipeline_with_synthetic_data(
    tmp_path: Path,
    synthetic_raster: Path,
    synthetic_climate_csv: Path,
):
    out_dir = tmp_path / "outputs"

    cfg_content = textwrap.dedent(
        f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{synthetic_climate_csv}"
        output_dir: "{out_dir}"

        roi:
          type: "bbox"
          xmin: -101.0
          ymin: 39.0
          xmax: -99.0
          ymax: 41.0

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

        max_cells: 10
        """
    )

    cfg_file = tmp_path / "cfg.yml"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    df = run_pipeline(cfg_file)

    # Basic structural checks
    assert not df.empty
    assert len(df) <= 10
    assert {"cell_id", "lat", "lon", "v_index", "score", "label"}.issubset(df.columns)

    # Scores must be in [0, 1]
    assert df["score"].between(0.0, 1.0).all()

    # Labels must be from the expected set
    assert set(df["label"].unique()).issubset({"low", "medium", "high"})

    # Results file exists
    results_csv = out_dir / "results.csv"
    assert results_csv.exists()
