import pandas as pd

from drought_impact.coverage import build_coverage
from drought_impact.rma import load_col


def test_insured_acre_fraction(bench_cfg):
    col = load_col(bench_cfg)
    nass = pd.read_parquet(bench_cfg.nass_acres_path)
    cov = build_coverage(col, nass)
    # insured 8000 / planted 10000 = 0.8
    assert cov["insured_acre_fraction"].dropna().round(3).eq(0.8).all()


def test_coverage_without_nass_keeps_schema(bench_cfg):
    col = load_col(bench_cfg)
    cov = build_coverage(col, None)
    assert {"insured_acres", "planted_acres", "insured_acre_fraction"}.issubset(cov.columns)
    assert cov["insured_acre_fraction"].isna().all()
