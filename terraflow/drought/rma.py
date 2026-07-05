"""Ingest USDA RMA *Cause of Loss* Summary-of-Business files.

The Cause of Loss Historical Data Files are public, pipe-delimited flat files (one ZIP per year,
1989–present) published at
https://www.rma.usda.gov/tools-reports/summary-of-business/cause-loss

Each record is broken down by year × state × county × commodity × insurance-plan × coverage ×
stage × cause-of-loss × month-of-loss. The 30-field record layout is stable across the benchmark's
year range (verified 2000 & 2012 → exactly 30 fields). Fields are space-padded within the pipe
delimiters and numerics are zero-/dot-padded (e.g. ``00.0000000000``), so string fields are
stripped and numeric fields coerced.
"""

from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BASE_URL = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/cause_of_loss"

# The 30 fields in record-layout order (COL_Summary_of_Business_with_Month_All_Years).
COL_COLUMNS: tuple[str, ...] = (
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
    "stage_code",
    "cause_of_loss_code",
    "cause_of_loss_desc",
    "month_of_loss",
    "month_of_loss_name",
    "year_of_loss",
    "policies_earning_premium",
    "policies_indemnified",
    "net_planted_qty",
    "net_endorsed_acres",
    "liability",
    "total_premium",
    "producer_paid_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "net_determined_qty",
    "indemnity_amount",
    "loss_ratio",
)

# Columns coerced to numeric; everything else is a stripped string.
_NUMERIC_COLUMNS: tuple[str, ...] = (
    "commodity_year",
    "net_planted_qty",
    "net_endorsed_acres",
    "liability",
    "total_premium",
    "producer_paid_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "net_determined_qty",
    "indemnity_amount",
    "loss_ratio",
)


def col_url(year: int) -> str:
    """Public download URL for a given commodity year's Cause of Loss ZIP."""
    return f"{BASE_URL}/colsom_{year}.zip"


def download_col_years(years: list[int], dest_dir: Path, *, overwrite: bool = False) -> list[Path]:
    """Download (and cache) the Cause of Loss ZIP for each year into *dest_dir*.

    Returns the list of local ZIP paths. Existing files are reused unless ``overwrite=True``.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for year in years:
        target = dest_dir / f"colsom_{year}.zip"
        if overwrite or not target.exists():
            urllib.request.urlretrieve(col_url(year), target)  # noqa: S310 (trusted USDA host)
        paths.append(target)
    return paths


def _open_col_text(path: Path):
    """Yield a readable text handle for a colsom file, transparently unzipping ``.zip``."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
            return zf.open(name)
    return path.open("rb")


def parse_col_file(
    path: Path,
    *,
    states: list[str] | None = None,
    commodity: str | None = None,
) -> pd.DataFrame:
    """Parse a single Cause of Loss file (``.txt`` or ``.zip``) into a tidy DataFrame.

    String fields are stripped; numeric fields are coerced. Adds a 5-digit ``GEOID`` (state FIPS +
    county FIPS) matching the flashdry predictor tables. Optional ``states`` / ``commodity`` filters
    are applied *before* the (costly) strip/convert of every column, which keeps whole-corpus loads
    fast when only one crop/region is needed.
    """
    handle = _open_col_text(path)
    try:
        df = pd.read_csv(
            handle,
            sep="|",
            header=None,
            names=list(COL_COLUMNS),
            dtype=str,
            encoding="latin-1",
            na_filter=False,
        )
    finally:
        handle.close()

    # Cheap early filter on just the two key columns to shrink the frame before full processing.
    if states is not None:
        df = df[df["state_code"].str.strip().str.zfill(2).isin(states)]
    if commodity is not None:
        df = df[df["commodity_name"].str.strip() == commodity]
    df = df.copy()

    for col in COL_COLUMNS:
        df[col] = df[col].str.strip()
    for col in _NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["state_code"] = df["state_code"].str.zfill(2)
    df["county_code"] = df["county_code"].str.zfill(3)
    df["GEOID"] = df["state_code"] + df["county_code"]
    return df


def load_col(
    rma_dir: Path,
    years: list[int],
    *,
    states: list[str] | None = None,
    commodity: str | None = None,
) -> pd.DataFrame:
    """Load and concatenate Cause of Loss records for *years* from *rma_dir*.

    Accepts either ``colsom_YYYY.zip`` or the extracted ``colsomYY.txt`` in *rma_dir*. ``states`` /
    ``commodity`` filters are pushed down into each file for speed.
    """
    rma_dir = Path(rma_dir)
    frames: list[pd.DataFrame] = []
    for year in years:
        candidates = [
            rma_dir / f"colsom_{year}.zip",
            rma_dir / f"colsom{year % 100:02d}.txt",
            rma_dir / f"colsom_{year}.txt",
        ]
        path = next((c for c in candidates if c.exists()), None)
        if path is None:
            raise FileNotFoundError(
                f"No Cause of Loss file for {year} in {rma_dir} "
                f"(expected one of: {', '.join(c.name for c in candidates)})"
            )
        frames.append(parse_col_file(path, states=states, commodity=commodity))
    return pd.concat(frames, ignore_index=True)
