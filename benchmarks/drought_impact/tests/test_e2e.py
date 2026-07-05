"""End-to-end fixture run: assemble → splits → baselines, plus the argparse CLI.

Proves the whole wiring works on synthetic data with no flashdry/RMA/network access.
"""

from __future__ import annotations

import json

import pandas as pd
import yaml

from drought_impact.assemble import assemble_benchmark
from drought_impact.baselines import run_baselines
from drought_impact.cli import main
from drought_impact.predictors import extract_centroids
from drought_impact.splits import build_splits, validate_splits


def test_full_pipeline_functions(bench_cfg):
    benchmark, manifest = assemble_benchmark(bench_cfg, write=False)
    centroids = extract_centroids(pd.read_parquet(bench_cfg.feature_table_path))
    splits = build_splits(benchmark, centroids, bench_cfg)
    validate_splits(splits)

    leaderboard = run_baselines(benchmark, splits)
    names = set(leaderboard["baseline"])
    assert {"naive_climatology", "naive_county"}.issubset(names)
    assert "ridge" in names  # an ML regression baseline ran
    # every regression row has a finite RMSE
    reg = leaderboard[leaderboard["task"] == "regression"]
    assert reg["rmse"].notna().all()


def _write_yaml_config(bench_cfg, path):
    data = {
        "states": bench_cfg.states,
        "year_min": bench_cfg.year_min,
        "year_max": bench_cfg.year_max,
        "crop": bench_cfg.crop,
        "season_start_doy": bench_cfg.season_start_doy,
        "cutoff_doy": bench_cfg.cutoff_doy,
        "binary_threshold": bench_cfg.binary_threshold,
        "spatial_blocks_side": bench_cfg.spatial_blocks_side,
        "temporal_test_years": bench_cfg.temporal_test_years,
        "feature_table_path": str(bench_cfg.feature_table_path),
        "nass_acres_path": str(bench_cfg.nass_acres_path),
        "rma_data_dir": str(bench_cfg.rma_data_dir),
        "output_dir": str(bench_cfg.output_dir),
    }
    path.write_text(yaml.safe_dump(data))


def test_cli_build_splits_baselines(bench_cfg, tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    _write_yaml_config(bench_cfg, cfg_path)

    assert main(["build", "--config", str(cfg_path)]) == 0
    assert main(["splits", "--config", str(cfg_path)]) == 0
    assert main(["baselines", "--config", str(cfg_path)]) == 0

    out = bench_cfg.output_dir
    assert (out / "benchmark.parquet").exists()
    assert (out / "leaderboard.csv").exists()
    splits = json.loads((out / "splits.json").read_text())
    assert "temporal" in splits and "spatial_block" in splits and "loyo" in splits
