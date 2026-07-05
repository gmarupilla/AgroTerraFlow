"""Tests for RMA Cause of Loss ingest + label construction (terraflow.drought.rma/labels)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from terraflow.drought.config import DroughtConfig
from terraflow.drought.labels import LABEL_COLUMNS, build_labels, finalize_targets
from terraflow.drought.nass import parse_nass_records
from terraflow.drought.rma import COL_COLUMNS, col_url, load_col, parse_col_file
from terraflow.drought.sob import aggregate_sob, load_sob

from .drought_synthetic import write_synthetic_col, write_synthetic_sob


def _cfg(tmp_path: Path, **kw) -> DroughtConfig:
    defaults: dict = dict(
        states=["17", "19"],
        year_min=2000,
        year_max=2001,
        rma_dir=tmp_path,
        feature_table=tmp_path / "ft.parquet",
        output_dir=tmp_path / "out",
    )
    defaults.update(kw)
    return DroughtConfig(**defaults)


def test_col_url_pattern():
    assert col_url(2012).endswith("/colsom_2012.zip")


def test_parse_txt_and_zip_agree(tmp_path: Path):
    rows = [
        {
            "year": 2000,
            "state": 17,
            "county": 1,
            "commodity": "CORN",
            "cause": "Drought",
            "liability": 1000,
            "indemnity": 300,
        }
    ]
    txt = write_synthetic_col(tmp_path / "colsom00.txt", rows)
    zip_ = write_synthetic_col(tmp_path / "colsom_2000.zip", rows)

    df_txt = parse_col_file(txt)
    df_zip = parse_col_file(zip_)

    assert list(df_txt.columns)[: len(COL_COLUMNS)] == list(COL_COLUMNS)
    assert df_txt.loc[0, "GEOID"] == "17001"
    assert df_txt.loc[0, "commodity_name"] == "CORN"  # stripped
    assert df_txt.loc[0, "indemnity_amount"] == pytest.approx(300.0)  # numeric-coerced
    assert df_zip.loc[0, "GEOID"] == "17001"


def test_parse_pushdown_filters(tmp_path: Path):
    rows = [
        {"year": 2000, "state": 17, "county": 1, "commodity": "CORN", "cause": "Drought"},
        {"year": 2000, "state": 55, "county": 1, "commodity": "CORN", "cause": "Drought"},
        {"year": 2000, "state": 17, "county": 2, "commodity": "WHEAT", "cause": "Drought"},
    ]
    path = write_synthetic_col(tmp_path / "colsom00.txt", rows)
    df = parse_col_file(path, states=["17"], commodity="CORN")
    assert len(df) == 1
    assert df.loc[0, "GEOID"] == "17001"


def test_load_col_missing_year_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="No Cause of Loss file for 2000"):
        load_col(tmp_path, [2000])


def test_build_labels_math(tmp_path: Path):
    # One county-year: two drought rows (indemnity 200+100) + one hail row (indemnity 100).
    rows = [
        {
            "year": 2000,
            "state": 17,
            "county": 1,
            "commodity": "CORN",
            "cause": "Drought",
            "liability": 1000,
            "indemnity": 200,
        },
        {
            "year": 2000,
            "state": 17,
            "county": 1,
            "commodity": "CORN",
            "cause": "Drought",
            "liability": 1000,
            "indemnity": 100,
        },
        {
            "year": 2000,
            "state": 17,
            "county": 1,
            "commodity": "CORN",
            "cause": "Hail",
            "liability": 1000,
            "indemnity": 100,
        },
    ]
    write_synthetic_col(tmp_path / "colsom00.txt", rows)
    col = load_col(tmp_path, [2000], states=["17"], commodity="CORN")
    labels = build_labels(col, _cfg(tmp_path))

    assert list(labels.columns) == list(LABEL_COLUMNS)
    r = labels.iloc[0]
    assert r["drought_indemnity"] == pytest.approx(300.0)
    assert r["total_indemnity"] == pytest.approx(400.0)
    assert r["col_liability"] == pytest.approx(3000.0)
    assert r["drought_share"] == pytest.approx(0.75)
    # No SOB joined -> finalize falls back to col_liability: ratio = 300/3000 = 0.10 -> significant.
    final = finalize_targets(labels, _cfg(tmp_path))
    fr = final.iloc[0]
    assert fr["drought_loss_ratio"] == pytest.approx(0.1)
    assert bool(fr["significant_drought_loss"]) is True


def test_build_labels_filters_scope(tmp_path: Path):
    rows = [
        {"year": 2000, "state": 17, "county": 1, "commodity": "CORN", "cause": "Drought", "indemnity": 500},
        {"year": 2000, "state": 17, "county": 2, "commodity": "SOYBEANS", "cause": "Drought", "indemnity": 500},
    ]
    write_synthetic_col(tmp_path / "colsom00.txt", rows)
    col = load_col(tmp_path, [2000])
    labels = build_labels(col, _cfg(tmp_path))  # crop defaults to CORN
    assert set(labels["GEOID"]) == {"17001"}


def test_sob_parse_and_aggregate(tmp_path: Path):
    rows = [
        {"year": 2012, "state": 19, "county": 1, "commodity": "CORN", "liability": 6_000_000, "acres": 3000},
        {"year": 2012, "state": 19, "county": 1, "commodity": "CORN", "liability": 4_000_000, "acres": 2000},
    ]
    write_synthetic_sob(tmp_path / "sobcov_2012.zip", rows)
    sob = load_sob(tmp_path, [2012], states=["19"], commodity="CORN")
    agg = aggregate_sob(sob)
    a = agg.iloc[0]
    assert a["GEOID"] == "19001"
    assert a["total_liability"] == pytest.approx(10_000_000)
    assert a["insured_acres"] == pytest.approx(5000)


def test_finalize_uses_true_sob_liability(tmp_path: Path):
    # With SOB total_liability (10000) the ratio is 0.03 (< threshold), not the col_liability
    # fallback (1000 -> 0.30). Coverage fraction = insured / planted.
    df = pd.DataFrame(
        {
            "GEOID": ["19001"],
            "year": [2012],
            "drought_indemnity": [300.0],
            "total_indemnity": [300.0],
            "col_liability": [1000.0],
            "total_liability": [10_000.0],
            "insured_acres": [5000.0],
            "planted_acres": [6000.0],
        }
    )
    final = finalize_targets(df, _cfg(tmp_path)).iloc[0]
    assert final["drought_loss_ratio"] == pytest.approx(0.03)
    assert bool(final["significant_drought_loss"]) is False
    assert final["insured_acre_fraction"] == pytest.approx(5000 / 6000)


def test_nass_parse_records():
    recs = [
        {"agg_level_desc": "COUNTY", "state_fips_code": "19", "county_ansi": "001", "year": "2012", "Value": "176,000"},
        {"agg_level_desc": "COUNTY", "state_fips_code": "19", "county_ansi": "001", "year": "2012", "Value": "24,000"},
        {"agg_level_desc": "COUNTY", "state_fips_code": "19", "county_ansi": "", "year": "2012", "Value": "999"},
        {"agg_level_desc": "STATE", "state_fips_code": "19", "county_ansi": "003", "year": "2012", "Value": "5"},
        {"agg_level_desc": "COUNTY", "state_fips_code": "19", "county_ansi": "005", "year": "2012", "Value": "(D)"},
    ]
    df = parse_nass_records(recs)
    assert set(df["GEOID"]) == {"19001"}
    assert df.iloc[0]["planted_acres"] == pytest.approx(200000)  # 176000 + 24000 summed
