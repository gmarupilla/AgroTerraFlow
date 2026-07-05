"""Tests for RMA Cause of Loss ingest + label construction (terraflow.drought.rma/labels)."""

from __future__ import annotations

from pathlib import Path

import pytest

from terraflow.drought.config import DroughtConfig
from terraflow.drought.labels import LABEL_COLUMNS, build_labels
from terraflow.drought.rma import COL_COLUMNS, col_url, load_col, parse_col_file

from .drought_synthetic import write_synthetic_col


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
    assert r["liability"] == pytest.approx(3000.0)
    assert r["drought_share"] == pytest.approx(0.75)
    assert r["drought_loss_ratio"] == pytest.approx(0.1)  # 300/3000
    assert bool(r["significant_drought_loss"]) is True  # >= 0.10 threshold


def test_build_labels_filters_scope(tmp_path: Path):
    rows = [
        {"year": 2000, "state": 17, "county": 1, "commodity": "CORN", "cause": "Drought", "indemnity": 500},
        {"year": 2000, "state": 17, "county": 2, "commodity": "SOYBEANS", "cause": "Drought", "indemnity": 500},
    ]
    write_synthetic_col(tmp_path / "colsom00.txt", rows)
    col = load_col(tmp_path, [2000])
    labels = build_labels(col, _cfg(tmp_path))  # crop defaults to CORN
    assert set(labels["GEOID"]) == {"17001"}
