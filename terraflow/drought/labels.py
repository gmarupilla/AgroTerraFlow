"""Build county-crop-year drought-loss labels from parsed RMA Cause of Loss records.

The impact label is what makes this benchmark distinct from severity (USDM D2+) and yield
(CY-Bench/SustainBench) benchmarks: it is the *insured drought loss* actually paid out.

For each (GEOID, commodity_year) with commodity == ``crop`` and state in scope:
- ``drought_indemnity``  = Σ indemnity where cause_of_loss_desc ∈ drought_causes
- ``total_indemnity``    = Σ indemnity over all causes
- ``liability``          = Σ liability over the county-crop-year's loss records
- ``drought_share``      = drought_indemnity / total_indemnity            (clean, in [0, 1])
- ``drought_loss_ratio`` = drought_indemnity / liability                  (primary regression target)
- ``significant_drought_loss`` = drought_loss_ratio ≥ threshold           (binary target)

Note on the denominator: ``liability`` is summed over the county-crop-year's Cause of Loss rows,
which represent loss-experiencing policies (COL only contains indemnified experience). It is a
well-defined loss-experience ratio, not the full insured liability — and can exceed 1.0 in
catastrophic county-years (verified: up to ~1.11 in the 2012 Corn Belt). Rank-based metrics
(Spearman) and the binary target are therefore the robust headlines; ``drought_share`` is provided
as a fully double-count-free, bounded [0, 1] auxiliary target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DroughtConfig

LABEL_COLUMNS: tuple[str, ...] = (
    "GEOID",
    "year",
    "drought_indemnity",
    "total_indemnity",
    "liability",
    "drought_share",
    "drought_loss_ratio",
    "significant_drought_loss",
)


def build_labels(col: pd.DataFrame, cfg: DroughtConfig) -> pd.DataFrame:
    """Aggregate parsed Cause of Loss records into per-(GEOID, year) drought-loss labels."""
    scoped = col[
        col["state_code"].isin(cfg.states)
        & (col["commodity_name"] == cfg.crop)
        & col["commodity_year"].between(cfg.year_min, cfg.year_max)
    ].copy()

    scoped["_is_drought"] = scoped["cause_of_loss_desc"].isin(cfg.drought_causes)
    scoped["_drought_indemnity"] = np.where(scoped["_is_drought"], scoped["indemnity_amount"], 0.0)

    grouped = scoped.groupby(["GEOID", "commodity_year"], as_index=False).agg(
        drought_indemnity=("_drought_indemnity", "sum"),
        total_indemnity=("indemnity_amount", "sum"),
        liability=("liability", "sum"),
    )
    grouped = grouped.rename(columns={"commodity_year": "year"})

    grouped["drought_share"] = _safe_ratio(grouped["drought_indemnity"], grouped["total_indemnity"])
    grouped["drought_loss_ratio"] = _safe_ratio(grouped["drought_indemnity"], grouped["liability"])
    grouped["significant_drought_loss"] = grouped["drought_loss_ratio"] >= cfg.loss_ratio_threshold

    grouped["year"] = grouped["year"].astype(int)
    return grouped[list(LABEL_COLUMNS)].sort_values(["GEOID", "year"]).reset_index(drop=True)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """numerator / denominator with 0 where the denominator is 0 (no loss experience)."""
    out = np.divide(
        numerator.to_numpy(dtype=float),
        denominator.to_numpy(dtype=float),
        out=np.zeros(len(numerator), dtype=float),
        where=denominator.to_numpy(dtype=float) > 0,
    )
    return pd.Series(out, index=numerator.index)
