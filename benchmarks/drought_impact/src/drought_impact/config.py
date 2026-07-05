"""Benchmark configuration (Pydantic v2).

Mirrors the ``terraflow/config.py`` style: ``BaseModel`` + ``ConfigDict(extra="forbid")``,
``field_validator`` for per-field checks, and a ``validate_all()`` method run after
construction. Every external location (flashdry inputs, RMA source, output dir) is a
config value — nothing is hardcoded, so the same code runs here on fixtures and locally
on the real flashdry/RMA data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

# Corn Belt 6-state scope (FIPS-2 state codes). Kept as a constant so tests and the
# config validator share one source of truth.
CORN_BELT_STATE_FIPS: dict[str, str] = {
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "27": "MN",
    "29": "MO",
    "31": "NE",
}


class RmaSource(BaseModel):
    """Where RMA Cause-of-Loss yearly archives come from.

    ``filename_template`` must contain a ``{year}`` placeholder. The full URL for a year
    is ``base_url.rstrip('/') + '/' + filename_template.format(year=year)``.
    """

    base_url: str = "https://www.rma.usda.gov/-/media/RMA/Cause-Of-Loss/Summary-of-Business-with-Month-of-Loss"
    filename_template: str = "colsom_{year}.zip"

    model_config = ConfigDict(extra="forbid")

    @field_validator("filename_template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if "{year}" not in v:
            raise ValueError("rma_source.filename_template must contain a '{year}' placeholder")
        return v

    def url_for(self, year: int) -> str:
        return f"{self.base_url.rstrip('/')}/{self.filename_template.format(year=year)}"


class BenchmarkConfig(BaseModel):
    """Top-level v0 benchmark configuration.

    Attributes
    ----------
    states:
        FIPS-2 state codes to include (default: the 6-state Corn Belt).
    year_min, year_max:
        Inclusive crop-year range.
    crop:
        RMA ``Commodity Name`` to filter on (e.g. ``"CORN"``).
    season_start_doy, cutoff_doy:
        Growing-season window (day-of-year) over which ``_anom`` predictors are
        aggregated. ``cutoff_doy`` drives the early-warning framing.
    binary_threshold:
        Loss-cost value above which the binary significant-loss flag is 1 (when
        ``binary_threshold_mode == "fixed"``).
    binary_threshold_mode:
        ``"fixed"`` uses ``binary_threshold`` directly; ``"county_baseline"`` flags a
        county-year whose loss-cost exceeds its own historical mean by
        ``binary_threshold``.
    spatial_blocks_side:
        Grid resolution per side for the spatial-block split (total blocks = side²).
    temporal_test_years:
        Years held out for the official temporal test split.
    Input paths:
        ``feature_table_path`` (flashdry predictors), ``nass_acres_path``,
        ``wxcond_path``, ``vci_tci_vhi_path``, ``usdm_path`` — all optional; missing
        ones simply skip their derived columns / baselines. ``rma_data_dir`` holds
        downloaded/placed COL archives. ``output_dir`` receives artifacts.
    """

    states: list[str] = list(CORN_BELT_STATE_FIPS.keys())
    year_min: int = 2000
    year_max: int = 2023
    crop: str = "CORN"

    season_start_doy: int = 60
    cutoff_doy: int = 212  # ~Jul 31

    binary_threshold: float = 0.10
    binary_threshold_mode: Literal["fixed", "county_baseline"] = "fixed"

    spatial_blocks_side: int = 4
    temporal_test_years: list[int] = [2012, 2022, 2023]

    # External inputs — all config-driven, may be absent (skipped) except RMA + features.
    feature_table_path: Optional[Path] = None
    nass_acres_path: Optional[Path] = None
    wxcond_path: Optional[Path] = None
    vci_tci_vhi_path: Optional[Path] = None
    usdm_path: Optional[Path] = None

    rma_data_dir: Path = Path("data/raw")
    output_dir: Path = Path("data/processed")
    rma_source: RmaSource = RmaSource()

    model_config = ConfigDict(extra="forbid")

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("states must be a non-empty list of FIPS-2 codes")
        for code in v:
            if not (isinstance(code, str) and len(code) == 2 and code.isdigit()):
                raise ValueError(f"state codes must be 2-digit FIPS strings, got {code!r}")
        return v

    @field_validator("season_start_doy", "cutoff_doy")
    @classmethod
    def validate_doy(cls, v: int) -> int:
        if not 1 <= v <= 366:
            raise ValueError(f"day-of-year must be in 1-366, got {v}")
        return v

    @field_validator("spatial_blocks_side")
    @classmethod
    def validate_blocks_side(cls, v: int) -> int:
        if v < 2:
            raise ValueError(f"spatial_blocks_side must be >= 2, got {v}")
        return v

    def validate_all(self) -> None:
        """Validate cross-field constraints. Call after construction."""
        if self.year_min > self.year_max:
            raise ValueError(f"year_min ({self.year_min}) must be <= year_max ({self.year_max})")
        if self.season_start_doy >= self.cutoff_doy:
            raise ValueError(f"season_start_doy ({self.season_start_doy}) must be < cutoff_doy ({self.cutoff_doy})")
        for yr in self.temporal_test_years:
            if not self.year_min <= yr <= self.year_max:
                raise ValueError(
                    f"temporal_test_years entry {yr} outside [year_min, year_max] "
                    f"[{self.year_min}, {self.year_max}]"
                )

    def years(self) -> list[int]:
        return list(range(self.year_min, self.year_max + 1))

    def as_fingerprint_dict(self) -> dict:
        """Config subset that determines the build output (for the build fingerprint).

        Excludes on-disk *locations* (paths differ across machines) but keeps every
        knob that changes the assembled dataset.
        """
        return {
            "states": sorted(self.states),
            "year_min": self.year_min,
            "year_max": self.year_max,
            "crop": self.crop,
            "season_start_doy": self.season_start_doy,
            "cutoff_doy": self.cutoff_doy,
            "binary_threshold": self.binary_threshold,
            "binary_threshold_mode": self.binary_threshold_mode,
            "spatial_blocks_side": self.spatial_blocks_side,
            "temporal_test_years": sorted(self.temporal_test_years),
        }


def load_config_dict(path: str | Path) -> dict:
    """Load a YAML config file into a raw dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML config: {e}") from e
    if data is None:
        raise ValueError("Configuration file is empty")
    return data


def build_config(data: dict) -> BenchmarkConfig:
    """Validate a raw dict into a BenchmarkConfig."""
    try:
        cfg = BenchmarkConfig.model_validate(data)
        cfg.validate_all()
        return cfg
    except ValueError as e:
        raise ValueError(f"Configuration validation failed: {e}") from e


def load_config(path: str | Path) -> BenchmarkConfig:
    """Load and validate a YAML config file into a BenchmarkConfig."""
    return build_config(load_config_dict(path))
