"""Configuration model for the drought-impact benchmark.

The benchmark predicts *insured drought loss* (USDA RMA Cause of Loss) from within-season
climate/vegetation predictors. This module defines the single Pydantic config that drives the
whole build so runs are reproducible and fingerprintable.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

# The 6-state Corn Belt used by the flashdry predictor corpus (FIPS state codes).
CORN_BELT_STATES: tuple[str, ...] = ("17", "18", "19", "27", "29", "31")  # IL IN IA MN MO NE

# FIPS state code → USPS postal code (for the NASS QuickStats query).
STATE_FIPS_TO_ALPHA: dict[str, str] = {
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "27": "MN",
    "29": "MO",
    "31": "NE",
    "01": "AL",
    "05": "AR",
    "08": "CO",
    "20": "KS",
    "21": "KY",
    "26": "MI",
    "38": "ND",
    "39": "OH",
    "46": "SD",
    "47": "TN",
    "55": "WI",
}


class DroughtConfig(BaseModel):
    """End-to-end configuration for building and evaluating the drought-impact benchmark."""

    # --- Spatial / temporal scope -------------------------------------------------------
    states: list[str] = Field(default_factory=lambda: list(CORN_BELT_STATES))
    crop: str = "CORN"
    year_min: int = 2000
    year_max: int = 2023

    # --- Label definition (RMA Cause of Loss) -------------------------------------------
    # Cause-of-loss *descriptions* (field 13) counted as drought-attributed. "Drought" is the
    # clean, defensible default; ``["Drought", "Heat", "Hot Wind"]`` gives a heat-inclusive variant.
    drought_causes: list[str] = Field(default_factory=lambda: ["Drought"])
    # Binary "significant drought loss" threshold on the primary regression target
    # (drought_loss_ratio = drought_indemnity / liability).
    loss_ratio_threshold: float = 0.10

    # --- Predictor aggregation ----------------------------------------------------------
    # Aggregate within-season predictors only up to this day-of-year (early-warning framing).
    # 212 ≈ Jul 31. Set to 273 (Sep 30) for the end-of-season variant.
    cutoff_doy: int = 212

    # --- Splits -------------------------------------------------------------------------
    test_years: list[int] = Field(default_factory=lambda: [2012, 2017, 2022, 2023])
    train_max_year: int = 2015
    n_blocks_side: int = 4  # spatial-block grid is n×n

    # --- Coverage / denominator hardening ----------------------------------------------
    # SOB coverage files give the TRUE total insured liability (denominator) + insured acres.
    # If unset, the drought-loss ratio falls back to the Cause-of-Loss loss-experience liability.
    sob_dir: Path | None = None  # directory holding sobcov_YYYY.zip files
    # Pull NASS planted acres to add an insured-acre-fraction coverage-bias column (needs an API key).
    add_coverage: bool = True

    # --- Paths --------------------------------------------------------------------------
    rma_dir: Path  # directory holding colsom_YYYY.txt (or .zip) files
    feature_table: Path  # flashdry data/processed/feature_table.parquet
    output_dir: Path

    @field_validator("states", mode="before")
    @classmethod
    def _pad_states(cls, v: list[str]) -> list[str]:
        return [str(s).zfill(2) for s in v]

    @field_validator("year_max")
    @classmethod
    def _years_ordered(cls, v: int, info) -> int:
        ymin = info.data.get("year_min")
        if ymin is not None and v < ymin:
            raise ValueError(f"year_max ({v}) must be >= year_min ({ymin})")
        return v

    @property
    def years(self) -> list[int]:
        return list(range(self.year_min, self.year_max + 1))

    @property
    def state_alphas(self) -> list[str]:
        """USPS postal codes for the configured FIPS states (for the NASS query)."""
        return [STATE_FIPS_TO_ALPHA[s] for s in self.states if s in STATE_FIPS_TO_ALPHA]

    @classmethod
    def from_yaml(cls, path: Path) -> "DroughtConfig":
        """Load a :class:`DroughtConfig` from a YAML file."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(**data)
