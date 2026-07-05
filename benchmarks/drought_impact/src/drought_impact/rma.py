"""USDA RMA Cause-of-Loss (COL, "Summary of Business with Month of Loss") ingest.

The yearly archives are pipe-delimited with **no header row** and a fixed 30-field
record layout (documented by RMA). We parse positionally against :data:`COL_COLUMNS`,
build a 5-digit ``GEOID`` from the FIPS state + county codes, and filter to the
configured states + crop.

Network note: downloads go through whatever egress the environment allows. When the
host is blocked (e.g. this planning container), :func:`download_col_year` raises a clear
error telling the caller to place the archive in ``rma_data_dir`` manually. Parsing does
not need the network.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from .config import BenchmarkConfig

# Fixed 30-field COL record layout (positional; files have no header row).
COL_COLUMNS: list[str] = [
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
    "cause_of_loss_description",
    "month_of_loss",
    "month_of_loss_name",
    "year_of_loss",
    "policies_earning_premium",
    "policies_indemnified",
    "net_planted_quantity",
    "net_endorsed_acres",
    "liability",
    "total_premium",
    "producer_paid_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "net_determined_quantity",
    "indemnity_amount",
    "loss_ratio",
]

# Columns coerced to numeric after parsing.
_NUMERIC_COLUMNS = [
    "commodity_year",
    "month_of_loss",
    "year_of_loss",
    "policies_earning_premium",
    "policies_indemnified",
    "net_planted_quantity",
    "net_endorsed_acres",
    "liability",
    "total_premium",
    "producer_paid_premium",
    "subsidy",
    "state_private_subsidy",
    "additional_subsidy",
    "efa_premium_discount",
    "net_determined_quantity",
    "indemnity_amount",
    "loss_ratio",
]

DROUGHT_DESCRIPTION = "Drought"


def download_col_year(year: int, cfg: BenchmarkConfig, *, overwrite: bool = False) -> Path:
    """Download one COL yearly archive into ``cfg.rma_data_dir`` and return its path.

    Raises a clear, actionable error on any network failure — the caller can then place
    the file manually and re-run (parsing is offline).
    """
    import requests  # local import: keeps the module importable without network deps at import time

    dest_dir = Path(cfg.rma_data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = cfg.rma_source.url_for(year)
    dest = dest_dir / cfg.rma_source.filename_template.format(year=year)

    if dest.exists() and not overwrite:
        return dest

    try:
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - re-raised with guidance
        raise RuntimeError(
            f"Failed to download RMA COL for {year} from {url}: {exc}. "
            f"If network egress is blocked, download the archive manually and place it at "
            f"{dest}, then re-run without the fetch step."
        ) from exc

    with dest.open("wb") as handle:
        for chunk in resp.iter_content(chunk_size=1_048_576):
            if chunk:
                handle.write(chunk)
    return dest


def _read_pipe_delimited(handle) -> pd.DataFrame:
    df = pd.read_csv(
        handle,
        sep="|",
        header=None,
        names=COL_COLUMNS,
        dtype=str,
        engine="python",
        skipinitialspace=True,
    )
    # Strip surrounding whitespace on all string cells.
    for col in df.columns:
        df[col] = df[col].str.strip()
    for col in _NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Build 5-digit GEOID from zero-padded FIPS state (2) + county (3).
    df["GEOID"] = df["state_code"].str.zfill(2) + df["county_code"].str.zfill(3)
    return df


def parse_col_file(path: str | Path) -> pd.DataFrame:
    """Parse one COL file (``.txt``/``.csv`` pipe-delimited, or a ``.zip`` of one) → tidy frame.

    Returns a DataFrame with :data:`COL_COLUMNS` plus a derived ``GEOID`` column.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"COL file not found: {path}")

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if not n.endswith("/")]
            if not members:
                raise ValueError(f"COL archive {path} is empty")
            with zf.open(members[0]) as raw:
                return _read_pipe_delimited(io.TextIOWrapper(raw, encoding="latin-1"))

    with path.open("r", encoding="latin-1") as handle:
        return _read_pipe_delimited(handle)


def load_col(cfg: BenchmarkConfig, years: list[int] | None = None) -> pd.DataFrame:
    """Load + concatenate COL files for the configured years, filtered to states + crop.

    Reads whatever archives are present in ``cfg.rma_data_dir`` (does not download).
    Missing years are skipped with no error so a partial local cache still works.
    """
    years = years or cfg.years()
    state_set = set(cfg.states)
    crop = cfg.crop.upper()
    data_dir = Path(cfg.rma_data_dir)

    frames: list[pd.DataFrame] = []
    for year in years:
        fname = cfg.rma_source.filename_template.format(year=year)
        candidate = data_dir / fname
        # Accept the archive or an already-unzipped sibling (.txt/.csv).
        alt = [candidate, candidate.with_suffix(".txt"), candidate.with_suffix(".csv")]
        found = next((p for p in alt if p.exists()), None)
        if found is None:
            continue
        df = parse_col_file(found)
        df = df[df["state_code"].str.zfill(2).isin(state_set) & (df["commodity_name"].str.upper() == crop)]
        frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"No COL archives found for years {years} in {data_dir}. "
            f"Download them (see download_col_year) or place them manually."
        )
    return pd.concat(frames, ignore_index=True)
