"""Reproducible evaluation splits for the drought-impact benchmark.

Three complementary regimes, all deterministic from the config (no RNG):
- **temporal** — held-out years (incl. the 2012 extreme + recent 2022/2023) test extrapolation to
  unseen seasons.
- **spatial** — leave-one-state-out blocks test spatial transfer (guards against spatially
  autocorrelated leakage; finer lon/lat grids are a follow-up).
- **loyo** — leave-one-year-out folds for a stability estimate across all years.

Split *definitions* (not enumerated rows) are serialized so the artifact is small and the masks
are re-derivable from any benchmark table.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd

from .config import DroughtConfig


def temporal_masks(df: pd.DataFrame, cfg: DroughtConfig) -> tuple[np.ndarray, np.ndarray]:
    """(train_mask, test_mask) for the official temporal split."""
    test = df["year"].isin(cfg.test_years).to_numpy()
    train = (~test) & (df["year"] <= cfg.train_max_year).to_numpy()
    return train, test


def spatial_block_ids(df: pd.DataFrame) -> pd.Series:
    """State-level spatial block id (first two GEOID digits = state FIPS)."""
    return df["GEOID"].str[:2]


def spatial_folds(df: pd.DataFrame) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """Leave-one-state-out folds: (state, train_mask, test_mask)."""
    blocks = spatial_block_ids(df)
    for state in sorted(blocks.unique()):
        test = (blocks == state).to_numpy()
        yield state, ~test, test


def loyo_folds(df: pd.DataFrame) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Leave-one-year-out folds: (year, train_mask, test_mask)."""
    for year in sorted(df["year"].unique()):
        test = (df["year"] == year).to_numpy()
        yield int(year), ~test, test


def describe_splits(cfg: DroughtConfig) -> dict:
    """JSON-serializable split definition (re-derivable, not enumerated)."""
    return {
        "temporal": {
            "test_years": list(cfg.test_years),
            "train_max_year": cfg.train_max_year,
            "rule": "test = year in test_years; train = remaining years <= train_max_year",
        },
        "spatial": {"scheme": "leave-one-state-out", "block_key": "GEOID[:2]"},
        "loyo": {"scheme": "leave-one-year-out", "years": cfg.years},
    }
