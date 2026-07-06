"""Build county-crop-year drought-loss labels from parsed RMA Cause of Loss records.

The impact label is what makes this benchmark distinct from severity (USDM D2+) and yield
(CY-Bench/SustainBench) benchmarks: it is the *insured drought loss* actually paid out.

:func:`build_labels` aggregates Cause of Loss into per-(GEOID, year) numerators (drought/total
indemnity) plus a fallback loss-experience liability. :func:`finalize_targets` then computes the
primary targets once the *true* total insured liability (from the Summary-of-Business coverage file)
and planted acres are joined:

- ``drought_indemnity``  = Σ indemnity where cause_of_loss_desc ∈ drought_causes
- ``total_indemnity``    = Σ indemnity over all causes
- ``drought_share``      = drought_indemnity / total_indemnity            (clean, in [0, 1])
- ``drought_loss_ratio`` = drought_indemnity / total insured liability    (primary regression target)
- ``significant_drought_loss`` = drought_loss_ratio ≥ threshold           (binary target)
- ``insured_acre_fraction`` = insured acres / NASS planted acres          (coverage-bias column)

Using the Summary-of-Business total liability (all policies) as the denominator removes the >1
artifact of the Cause-of-Loss loss-experience liability (only loss-experiencing policies).
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
    "col_liability",
    "drought_share",
)


def build_labels(col: pd.DataFrame, cfg: DroughtConfig) -> pd.DataFrame:
    """Aggregate parsed Cause of Loss records into per-(GEOID, year) numerators.

    Produces drought/total indemnity, the loss-experience (Cause-of-Loss) liability as a fallback
    denominator ``col_liability``, and the bounded ``drought_share``. The primary
    ``drought_loss_ratio`` / ``significant_drought_loss`` targets are computed by
    :func:`finalize_targets` once the true Summary-of-Business total liability is joined.
    """
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
        col_liability=("liability", "sum"),
    )
    grouped = grouped.rename(columns={"commodity_year": "year"})
    grouped["drought_share"] = _safe_ratio(grouped["drought_indemnity"], grouped["total_indemnity"])
    grouped["year"] = grouped["year"].astype(int)
    return grouped[list(LABEL_COLUMNS)].sort_values(["GEOID", "year"]).reset_index(drop=True)


def finalize_targets(df: pd.DataFrame, cfg: DroughtConfig) -> pd.DataFrame:
    """Compute the final targets on the fully-joined benchmark frame.

    Uses the true Summary-of-Business ``total_liability`` as the drought-loss-ratio denominator when
    present (removing the loss-experience >1 artifact), else falls back to ``col_liability``. Adds the
    ``insured_acre_fraction`` coverage-bias column when both insured and planted acres are available.
    """
    out = df.copy()
    liability = out["total_liability"] if "total_liability" in out.columns else out["col_liability"]
    out["drought_loss_ratio"] = _safe_ratio(out["drought_indemnity"], liability)
    out["significant_drought_loss"] = out["drought_loss_ratio"] >= cfg.loss_ratio_threshold
    if "insured_acres" in out.columns and "planted_acres" in out.columns:
        planted = out["planted_acres"].to_numpy(dtype=float)
        insured = out["insured_acres"].to_numpy(dtype=float)
        # Missing/withheld planted acres -> unknown coverage (NaN), not a spurious 0.0.
        out["insured_acre_fraction"] = np.divide(insured, planted, out=np.full(len(out), np.nan), where=planted > 0)
    return out


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """numerator / denominator with 0 where the denominator is 0 (no exposure)."""
    num = numerator.to_numpy(dtype=float)
    den = denominator.to_numpy(dtype=float)
    out = np.divide(num, den, out=np.zeros(len(num), dtype=float), where=den > 0)
    return pd.Series(out, index=numerator.index)
