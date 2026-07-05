"""Tests for benchmark assembly, determinism, and the leaderboard (dataset/evaluate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from terraflow.drought.config import DroughtConfig
from terraflow.drought.dataset import assemble_benchmark, load_benchmark
from terraflow.drought.evaluate import run_leaderboard

from .drought_synthetic import make_benchmark, make_feature_table, write_synthetic_col

_STATES = ["17", "19"]
_GEOIDS = ["17001", "19005"]


def _setup_inputs(tmp_path: Path, years: list[int]) -> DroughtConfig:
    ft = make_feature_table(_GEOIDS, years)
    ft_path = tmp_path / "feature_table.parquet"
    ft.to_parquet(ft_path, index=False)
    for y in years:
        rows = [
            {
                "year": y,
                "state": g[:2],
                "county": g[2:],
                "commodity": "CORN",
                "cause": "Drought",
                "liability": 1000,
                "indemnity": 300 if g == "17001" else 50,
            }
            for g in _GEOIDS
        ]
        write_synthetic_col(tmp_path / f"colsom_{y}.zip", rows)
    return DroughtConfig(
        states=_STATES,
        year_min=min(years),
        year_max=max(years),
        rma_dir=tmp_path,
        feature_table=ft_path,
        output_dir=tmp_path / "out",
    )


def test_assemble_writes_artifacts(tmp_path: Path):
    cfg = _setup_inputs(tmp_path, [2000, 2001])
    bench = assemble_benchmark(cfg, write=True)

    assert len(bench) == 4  # 2 counties × 2 years
    assert (cfg.output_dir / "benchmark.parquet").exists()
    manifest = json.loads((cfg.output_dir / "manifest.json").read_text())
    assert manifest["schema_version"] == "1"
    assert len(manifest["build_fingerprint"]) == 64
    assert manifest["n_counties"] == 2
    assert (cfg.output_dir / "splits.json").exists()
    # 17001 has ratio 0.3 (positive), 19005 has 0.05 (negative).
    pos = bench.set_index("GEOID")["significant_drought_loss"]
    assert bool(pos.loc["17001"].all()) is True
    assert bool(pos.loc["19005"].any()) is False


def test_assemble_is_deterministic(tmp_path: Path):
    cfg = _setup_inputs(tmp_path, [2000, 2001])
    assemble_benchmark(cfg, write=True)
    fp1 = json.loads((cfg.output_dir / "manifest.json").read_text())["build_fingerprint"]
    assemble_benchmark(cfg, write=True)
    fp2 = json.loads((cfg.output_dir / "manifest.json").read_text())["build_fingerprint"]
    assert fp1 == fp2


def test_load_benchmark_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="No benchmark"):
        load_benchmark(tmp_path)


def test_run_leaderboard_structure_and_files(tmp_path: Path):
    geoids = [f"{s}{c:03d}" for s in ("17", "18", "19") for c in range(1, 6)]
    bench = make_benchmark(geoids, [2000, 2001, 2002, 2003])
    cfg = DroughtConfig(
        states=["17", "18", "19"],
        year_min=2000,
        year_max=2003,
        test_years=[2003],
        train_max_year=2002,
        rma_dir=tmp_path,
        feature_table=tmp_path / "x",
        output_dir=tmp_path / "out",
    )
    report = run_leaderboard(bench, cfg, write_dir=cfg.output_dir)

    assert "regression" in report["temporal"] and "classification" in report["temporal"]
    assert "Ridge[climate]" in report["temporal"]["regression"]
    assert "LogReg[severity]" in report["temporal"]["classification"]
    assert "spatial_loso" in report
    assert (cfg.output_dir / "evaluate_report.json").exists()
    assert (cfg.output_dir / "leaderboard.csv").exists()


def test_run_leaderboard_empty_split_raises(tmp_path: Path):
    bench = make_benchmark(["17001", "17003"], [2000, 2001])
    cfg = DroughtConfig(
        states=["17"],
        year_min=2000,
        year_max=2001,
        test_years=[2099],
        train_max_year=2001,
        rma_dir=tmp_path,
        feature_table=tmp_path / "x",
        output_dir=tmp_path / "out",
    )
    with pytest.raises(ValueError, match="empty train or test"):
        run_leaderboard(bench, cfg)
