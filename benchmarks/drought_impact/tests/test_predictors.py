import pandas as pd

from drought_impact.predictors import aggregate_predictors, anom_columns, extract_centroids


def _feature_table(bench_cfg):
    return pd.read_parquet(bench_cfg.feature_table_path)


def test_anom_columns_detected(bench_cfg):
    ft = _feature_table(bench_cfg)
    assert anom_columns(ft) == ["ndvi_anom", "spei_anom", "tmax_anom"]


def test_one_row_per_geoid_year_with_expected_stats(bench_cfg):
    ft = _feature_table(bench_cfg)
    agg = aggregate_predictors(ft, bench_cfg)
    assert len(agg) == 4 * 3  # 4 counties × 3 years
    for stat in ("mean", "min", "max", "last", "nstress"):
        assert f"spei_anom_{stat}" in agg.columns


def test_drought_year_has_more_stress_weeks(bench_cfg):
    ft = _feature_table(bench_cfg)
    agg = aggregate_predictors(ft, bench_cfg)
    year_2012 = agg[agg["year"] == 2012]["spei_anom_nstress"]
    year_2010 = agg[agg["year"] == 2010]["spei_anom_nstress"]
    assert year_2012.min() > year_2010.max()


def test_cutoff_window_limits_observations(bench_cfg):
    ft = _feature_table(bench_cfg)
    early = aggregate_predictors(ft, bench_cfg)  # cutoff 212
    full = aggregate_predictors(ft, bench_cfg, end_of_season=True)
    assert early["n_obs"].sum() <= full["n_obs"].sum()


def test_extract_centroids_returns_coords(bench_cfg):
    ft = _feature_table(bench_cfg)
    cent = extract_centroids(ft)
    assert {"GEOID", "lat", "lon"}.issubset(cent.columns)
    assert len(cent) == 4
