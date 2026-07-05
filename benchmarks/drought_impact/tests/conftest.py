"""Synthetic fixtures for the drought-impact benchmark tests.

Everything is generated under ``tmp_path`` (mirrors the TerraFlow test style) so no binary
artifacts are committed. The synthetic data deliberately encodes the invariants the real
dataset must satisfy:

- 4 counties (17001, 17003, 19001, 19003) × 3 years (2010, 2011, 2012).
- 2012 is the extreme drought year → largest drought loss-cost everywhere.
- county 17003 in 2010 has liability but **no** drought row → a true-negative zero-loss
  county-year (not missing).
- ``binary_threshold = 0.10`` → only 2012 county-years are positive (minority class).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from drought_impact.config import BenchmarkConfig
from drought_impact.rma import COL_COLUMNS

# GEOID → (state_code, county_code, state_abbrev, centroid lat, lon)
_COUNTIES = {
    "17001": ("17", "001", "IL", 39.9, -90.6),
    "17003": ("17", "003", "IL", 37.2, -89.4),
    "19001": ("19", "001", "IA", 41.0, -94.4),
    "19003": ("19", "003", "IA", 40.7, -95.0),
}
_YEARS = [2010, 2011, 2012]

# Per-year drought indemnity (liability is a constant 1,000,000 → loss_cost = D / 1e6).
_DROUGHT_INDEMNITY = {2010: 10_000.0, 2011: 50_000.0, 2012: 300_000.0}
_LIABILITY = 1_000_000.0
_INSURED_ACRES = 8_000.0


def _col_row(year: int, geoid: str, cause: str, liability: float, indemnity: float, acres: float) -> list[str]:
    state_code, county_code, state_abbrev, _, _ = _COUNTIES[geoid]
    values = {
        "commodity_year": str(year),
        "state_code": state_code,
        "state_abbrev": state_abbrev,
        "county_code": county_code,
        "county_name": f"COUNTY_{county_code}",
        "commodity_code": "0041",
        "commodity_name": "CORN",
        "insurance_plan_code": "01",
        "insurance_plan_abbrev": "APH",
        "coverage_category": "A",
        "stage_code": "H",
        "cause_of_loss_code": "10" if cause == "Drought" else "11",
        "cause_of_loss_description": cause,
        "month_of_loss": "7",
        "month_of_loss_name": "JUL",
        "year_of_loss": str(year),
        "policies_earning_premium": "50",
        "policies_indemnified": "10",
        "net_planted_quantity": f"{acres:.1f}",
        "net_endorsed_acres": "0.0",
        "liability": f"{liability:.1f}",
        "total_premium": f"{liability * 0.08:.1f}",
        "producer_paid_premium": "0.0",
        "subsidy": "0.0",
        "state_private_subsidy": "0.0",
        "additional_subsidy": "0.0",
        "efa_premium_discount": "0.0",
        "net_determined_quantity": "0.0",
        "indemnity_amount": f"{indemnity:.1f}",
        "loss_ratio": f"{indemnity / (liability * 0.08):.3f}" if liability else "0.0",
    }
    return [values[col] for col in COL_COLUMNS]


def _write_col_files(rma_dir: Path) -> None:
    rma_dir.mkdir(parents=True, exist_ok=True)
    for year in _YEARS:
        rows: list[list[str]] = []
        for geoid in _COUNTIES:
            # Base (non-drought) row carries the liability + insured acres.
            rows.append(_col_row(year, geoid, "Hail", _LIABILITY, 5_000.0, _INSURED_ACRES))
            # Drought row — skipped for 17003 in 2010 (true-negative zero-loss county-year).
            if not (geoid == "17003" and year == 2010):
                rows.append(_col_row(year, geoid, "Drought", 0.0, _DROUGHT_INDEMNITY[year], 0.0))
        lines = ["|".join(r) for r in rows]
        (rma_dir / f"colsom_{year}.txt").write_text("\n".join(lines) + "\n", encoding="latin-1")


def _write_feature_table(path: Path) -> None:
    records = []
    for geoid, (_, _, _, lat, lon) in _COUNTIES.items():
        for year in _YEARS:
            # 8 weekly obs inside the season window (doy 60..212).
            for week, doy in enumerate(range(70, 210, 18)):
                date = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=doy - 1)
                # spei_anom strongly negative in the 2012 drought; mild otherwise.
                spei = -2.5 if year == 2012 else (-0.3 if year == 2011 else 0.1)
                records.append(
                    {
                        "GEOID": geoid,
                        "date": date,
                        "year": year,
                        "lat": lat,
                        "lon": lon,
                        "spei_anom": spei + 0.05 * week,
                        "ndvi_anom": (-1.8 if year == 2012 else 0.2) - 0.02 * week,
                        "tmax_anom": (2.0 if year == 2012 else 0.0) + 0.01 * week,
                    }
                )
    pd.DataFrame(records).to_parquet(path, index=False)


def _write_nass_acres(path: Path) -> None:
    rows = []
    for geoid in _COUNTIES:
        for year in _YEARS:
            rows.append({"GEOID": geoid, "year": year, "planted_acres": _INSURED_ACRES / 0.8})
    pd.DataFrame(rows).to_parquet(path, index=False)


@pytest.fixture
def bench_cfg(tmp_path: Path) -> BenchmarkConfig:
    """A fully-wired BenchmarkConfig pointing at freshly generated synthetic inputs."""
    rma_dir = tmp_path / "raw"
    feature_path = tmp_path / "feature_table.parquet"
    nass_path = tmp_path / "nass_acres.parquet"
    out_dir = tmp_path / "processed"

    _write_col_files(rma_dir)
    _write_feature_table(feature_path)
    _write_nass_acres(nass_path)

    cfg = BenchmarkConfig(
        states=["17", "19"],
        year_min=2010,
        year_max=2012,
        crop="CORN",
        season_start_doy=60,
        cutoff_doy=212,
        binary_threshold=0.10,
        spatial_blocks_side=2,
        temporal_test_years=[2012],
        feature_table_path=feature_path,
        nass_acres_path=nass_path,
        rma_data_dir=rma_dir,
        output_dir=out_dir,
    )
    cfg.validate_all()
    return cfg
