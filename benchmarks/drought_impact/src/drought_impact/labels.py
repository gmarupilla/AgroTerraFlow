"""Label construction: drought loss-cost ratio + binary significant-loss flag.

Target definition (per ``GEOID`` × crop-year):

- ``county_liability`` = Σ ``liability`` over **all** cause rows for that county-year.
  This defines the universe of *observed* county-years — any county-year with liability
  but no drought cause row is a genuine **true negative** (``drought_loss_cost == 0``),
  not a missing value.
- ``drought_indemnity`` = Σ ``indemnity_amount`` where
  ``cause_of_loss_description == "Drought"``.
- primary target ``drought_loss_cost`` = ``drought_indemnity / county_liability``.

Denominator honesty (documented in the datasheet): we use indemnity/**liability**, not
RMA's field-30 loss ratio (indemnity/**premium**). ``county_liability`` sums liability
across cause rows, which can over-count when a policy incurs losses from multiple causes;
``total_premium_sum`` is emitted alongside as a cross-check column.
"""

from __future__ import annotations

import pandas as pd

from .config import BenchmarkConfig
from .rma import DROUGHT_DESCRIPTION

LABEL_COLUMNS = [
    "GEOID",
    "year",
    "county_liability",
    "total_premium_sum",
    "drought_indemnity",
    "total_indemnity",
    "drought_loss_cost",
    "significant_loss",
]


def build_labels(col: pd.DataFrame, cfg: BenchmarkConfig) -> pd.DataFrame:
    """Build the GEOID×year label table from a parsed COL frame.

    Parameters
    ----------
    col:
        Tidy COL frame from :func:`drought_impact.rma.load_col` (has ``GEOID``,
        ``commodity_year``, ``cause_of_loss_description``, ``liability``,
        ``indemnity_amount``, ``total_premium``).
    cfg:
        Benchmark config (drives the binary threshold + mode).
    """
    df = col.copy()
    df["year"] = df["commodity_year"].astype("Int64")

    grouped = df.groupby(["GEOID", "year"], dropna=True)
    liability = grouped["liability"].sum(min_count=1).rename("county_liability")
    premium = grouped["total_premium"].sum(min_count=1).rename("total_premium_sum")
    total_indemnity = grouped["indemnity_amount"].sum(min_count=1).rename("total_indemnity")

    is_drought = df["cause_of_loss_description"].str.strip().str.casefold() == DROUGHT_DESCRIPTION.casefold()
    drought_indemnity = (
        df[is_drought].groupby(["GEOID", "year"])["indemnity_amount"].sum(min_count=1).rename("drought_indemnity")
    )

    labels = pd.concat([liability, premium, total_indemnity], axis=1).reset_index()
    labels = labels.merge(drought_indemnity.reset_index(), on=["GEOID", "year"], how="left")
    # County-years with no drought cause row are true negatives → 0 indemnity.
    labels["drought_indemnity"] = labels["drought_indemnity"].fillna(0.0)

    # Guard against zero / missing liability (cannot form a ratio).
    labels = labels[labels["county_liability"] > 0].copy()
    labels["drought_loss_cost"] = labels["drought_indemnity"] / labels["county_liability"]

    labels["significant_loss"] = _binary_flag(labels, cfg).astype(int)
    return labels[LABEL_COLUMNS].sort_values(["GEOID", "year"]).reset_index(drop=True)


def _binary_flag(labels: pd.DataFrame, cfg: BenchmarkConfig) -> pd.Series:
    """Return the boolean significant-loss flag per the configured mode."""
    loss = labels["drought_loss_cost"]
    if cfg.binary_threshold_mode == "fixed":
        return loss > cfg.binary_threshold
    # county_baseline: flag when a county-year exceeds its own historical mean by threshold.
    county_mean = labels.groupby("GEOID")["drought_loss_cost"].transform("mean")
    return loss > (county_mean + cfg.binary_threshold)
