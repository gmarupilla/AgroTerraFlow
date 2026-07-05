"""Coverage-bias column: RMA insured acres / NASS planted acres.

RMA Cause-of-Loss data covers *insured* acres only. To let downstream users filter or
weight county-years by how representative they are, we ship an ``insured_acre_fraction``
column = RMA net planted (insured) acres / NASS planted acres. This is the benchmark's
first-class documented limitation (see the datasheet).
"""

from __future__ import annotations

import pandas as pd

# Column names we accept for the NASS planted-acres value (first match wins).
_NASS_ACRE_CANDIDATES = ["planted_acres", "acres_planted", "value", "planted"]


def rma_insured_acres(col: pd.DataFrame) -> pd.DataFrame:
    """Sum RMA net planted (insured) acres per ``GEOID`` × year from a parsed COL frame.

    Note: COL ``net_planted_quantity`` is reported per cause row, so the sum can
    over-count when a county-year has losses from multiple causes. Documented as an
    approximation; the coverage fraction is advisory, not a precise ratio.
    """
    df = col.copy()
    df["year"] = df["commodity_year"].astype("Int64")
    acres = df.groupby(["GEOID", "year"])["net_planted_quantity"].sum(min_count=1).rename("insured_acres").reset_index()
    return acres


def _nass_acre_column(nass: pd.DataFrame) -> str:
    for cand in _NASS_ACRE_CANDIDATES:
        if cand in nass.columns:
            return cand
    raise ValueError(
        f"NASS acres frame has no recognized planted-acres column "
        f"(looked for {_NASS_ACRE_CANDIDATES}); columns present: {list(nass.columns)}"
    )


def build_coverage(col: pd.DataFrame, nass: pd.DataFrame | None) -> pd.DataFrame:
    """Return a ``GEOID``×year coverage frame with ``insured_acres``, ``planted_acres``,
    and ``insured_acre_fraction``.

    When ``nass`` is None, ``planted_acres``/``insured_acre_fraction`` are NaN (the column
    still ships so the schema is stable).
    """
    acres = rma_insured_acres(col)
    if nass is None:
        acres["planted_acres"] = pd.NA
        acres["insured_acre_fraction"] = pd.NA
        return acres

    nass = nass.copy()
    nass["GEOID"] = nass["GEOID"].astype(str).str.zfill(5)
    nass["year"] = nass["year"].astype("Int64")
    acre_col = _nass_acre_column(nass)
    nass = nass[["GEOID", "year", acre_col]].rename(columns={acre_col: "planted_acres"})

    merged = acres.merge(nass, on=["GEOID", "year"], how="left")
    frac = merged["insured_acres"] / merged["planted_acres"]
    merged["insured_acre_fraction"] = frac.where(merged["planted_acres"] > 0)
    return merged
