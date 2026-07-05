"""Configured severity-index inputs must actually be joined (not silently dropped).

Regression test for the case where `wxcond_path` / `vci_tci_vhi_path` / `usdm_path` are
set: the columns must land in `benchmark.parquet` so the severity-index baselines run.
"""

from __future__ import annotations

import pandas as pd

from drought_impact.assemble import assemble_benchmark
from drought_impact.baselines import run_baselines
from drought_impact.predictors import extract_centroids
from drought_impact.splits import build_splits


def _write_wxcond(path, feature_table_path):
    """A weekly WxCond severity-probability frame aligned to the fixture counties/years."""
    ft = pd.read_parquet(feature_table_path)
    rows = []
    for (geoid, year), grp in ft.groupby(["GEOID", "year"]):
        for date in grp["date"]:
            rows.append({"GEOID": geoid, "date": date, "year": year, "wxcond_prob": 0.9 if year == 2012 else 0.1})
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_configured_wxcond_column_is_joined(bench_cfg, tmp_path):
    wx = tmp_path / "wxcond.parquet"
    _write_wxcond(wx, bench_cfg.feature_table_path)
    cfg = bench_cfg.model_copy(update={"wxcond_path": wx})

    benchmark, _ = assemble_benchmark(cfg, write=False)
    assert "wxcond_prob" in benchmark.columns
    # 2012 (drought year) carries the high severity probability.
    got = benchmark[benchmark["year"] == 2012]["wxcond_prob"].dropna()
    assert (got > 0.5).all()


def test_index_baseline_runs_when_input_configured(bench_cfg, tmp_path):
    wx = tmp_path / "wxcond.parquet"
    _write_wxcond(wx, bench_cfg.feature_table_path)
    cfg = bench_cfg.model_copy(update={"wxcond_path": wx})

    benchmark, _ = assemble_benchmark(cfg, write=False)
    centroids = extract_centroids(pd.read_parquet(cfg.feature_table_path))
    splits = build_splits(benchmark, centroids, cfg)
    leaderboard = run_baselines(benchmark, splits)
    assert "index_wxcond_prob" in set(leaderboard["baseline"])


def test_missing_index_file_warns_not_crashes(bench_cfg, tmp_path, caplog):
    cfg = bench_cfg.model_copy(update={"wxcond_path": tmp_path / "does_not_exist.parquet"})
    with caplog.at_level("WARNING"):
        benchmark, _ = assemble_benchmark(cfg, write=False)
    assert "wxcond_prob" not in benchmark.columns
    assert any("does not exist" in r.message for r in caplog.records)
