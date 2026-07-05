import pandas as pd

from drought_impact.assemble import assemble_benchmark
from drought_impact.predictors import extract_centroids
from drought_impact.splits import build_splits, validate_splits


def _splits(bench_cfg):
    benchmark, _ = assemble_benchmark(bench_cfg, write=False)
    centroids = extract_centroids(pd.read_parquet(bench_cfg.feature_table_path))
    return benchmark, build_splits(benchmark, centroids, bench_cfg)


def test_temporal_split_holds_out_2012(bench_cfg):
    _, splits = _splits(bench_cfg)
    assert splits["temporal"]["test_years"] == [2012]
    assert all(k.endswith(":2012") for k in splits["temporal"]["test"])
    assert not any(k.endswith(":2012") for k in splits["temporal"]["train"])


def test_all_folds_disjoint(bench_cfg):
    _, splits = _splits(bench_cfg)
    validate_splits(splits)  # raises on leakage


def test_spatial_block_has_multiple_folds(bench_cfg):
    _, splits = _splits(bench_cfg)
    assert len(splits["spatial_block"]["folds"]) >= 2


def test_loyo_covers_every_year(bench_cfg):
    benchmark, splits = _splits(bench_cfg)
    fold_years = {f["year"] for f in splits["loyo"]["folds"]}
    assert fold_years == set(benchmark["year"].unique())
