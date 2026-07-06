"""Ingest USDA RMA *Summary of Business — State/County/Crop* (coverage) files.

These public ``sobcov_YYYY`` files hold the **full insured pool** per county-crop-year (all policies,
not just those with losses), so they provide the *true* total liability and insured acreage — unlike
the Cause of Loss file, whose liability reflects only loss-experiencing policies. Using the SOB total
liability as the drought-loss-ratio denominator removes the >1 artifact of the loss-experience ratio.

Verified 28-field, pipe-delimited layout (2000 & 2012). Key fields for the benchmark:
``net_reported_quantity`` (insured acres, field 19), ``liability`` (field 21), ``total_premium`` (22).
"""

from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BASE_URL = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop"

SOB_COLUMNS: tuple[str, ...] = (
    "commodity_year",
    "state_code",
    "state_abbrev",
    "county_code",
    "county_name",
    "commodity_code",
    "commodity_name",
    "insurance_plan_code",
    "insurance_plan_abbrev",
    "coverage_category",
    "delivery_type",
    "coverage_level",
    "policies_sold",
    "policies_earning_premium",
    "policies_indemnified",
    "units_earning_premium",
    "units_indemnified",
    "quantity_type",
    "net_reported_quantity",
    "endorsed_acres",
    "liability",
    "total_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "indemnity_amount",
    "loss_ratio",
)

_NUMERIC_COLUMNS: tuple[str, ...] = (
    "commodity_year",
    "coverage_level",
    "net_reported_quantity",
    "endorsed_acres",
    "liability",
    "total_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "indemnity_amount",
    "loss_ratio",
)


def sob_url(year: int) -> str:
    return f"{BASE_URL}/sobcov_{year}.zip"


def download_sob_years(years: list[int], dest_dir: Path, *, overwrite: bool = False) -> list[Path]:
    """Download (and cache) the SOB coverage ZIP for each year into *dest_dir*."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for year in years:
        target = dest_dir / f"sobcov_{year}.zip"
        if overwrite or not target.exists():
            urllib.request.urlretrieve(sob_url(year), target)  # noqa: S310 (trusted USDA host)
        paths.append(target)
    return paths


def _open_sob_text(path: Path):
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
            return zf.open(name)
    return path.open("rb")


def parse_sob_file(
    path: Path,
    *,
    states: list[str] | None = None,
    commodity: str | None = None,
) -> pd.DataFrame:
    """Parse one SOB coverage file into a tidy DataFrame with a 5-digit ``GEOID``.

    Optional ``states`` / ``commodity`` filters are applied before the full strip/convert for speed.
    """
    handle = _open_sob_text(path)
    try:
        df = pd.read_csv(
            handle,
            sep="|",
            header=None,
            names=list(SOB_COLUMNS),
            dtype=str,
            encoding="latin-1",
            na_filter=False,
        )
    finally:
        handle.close()

    if states is not None:
        df = df[df["state_code"].str.strip().str.zfill(2).isin(states)]
    if commodity is not None:
        df = df[df["commodity_name"].str.strip() == commodity]
    df = df.copy()

    for col in SOB_COLUMNS:
        df[col] = df[col].str.strip()
    for col in _NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["state_code"] = df["state_code"].str.zfill(2)
    df["county_code"] = df["county_code"].str.zfill(3)
    df["GEOID"] = df["state_code"] + df["county_code"]
    return df


def load_sob(
    sob_dir: Path,
    years: list[int],
    *,
    states: list[str] | None = None,
    commodity: str | None = None,
) -> pd.DataFrame:
    """Load and concatenate SOB coverage records for *years* from *sob_dir*."""
    sob_dir = Path(sob_dir)
    frames: list[pd.DataFrame] = []
    for year in years:
        candidates = [
            sob_dir / f"sobcov_{year}.zip",
            sob_dir / f"sobcov{year % 100:02d}.txt",
            sob_dir / f"sobcov_{year}.txt",
        ]
        path = next((c for c in candidates if c.exists()), None)
        if path is None:
            raise FileNotFoundError(
                f"No SOB coverage file for {year} in {sob_dir} "
                f"(expected one of: {', '.join(c.name for c in candidates)})"
            )
        frames.append(parse_sob_file(path, states=states, commodity=commodity))
    return pd.concat(frames, ignore_index=True)


def aggregate_sob(sob: pd.DataFrame) -> pd.DataFrame:
    """Aggregate SOB rows to per-(GEOID, year) totals: liability, premium, insured acres."""
    grouped = sob.groupby(["GEOID", "commodity_year"], as_index=False).agg(
        total_liability=("liability", "sum"),
        total_premium=("total_premium", "sum"),
        insured_acres=("net_reported_quantity", "sum"),
    )
    grouped = grouped.rename(columns={"commodity_year": "year"})
    grouped["year"] = grouped["year"].astype(int)
    return grouped
