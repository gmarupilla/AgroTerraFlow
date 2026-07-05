"""Aggregate flashdry within-season predictors to one vector per (GEOID, crop-year).

The flashdry ``feature_table.parquet`` is sub-annual (growing-season, ~biweekly). For an
early-warning task we aggregate each base feature over the season *up to* ``cutoff_doy`` — so a
model only sees signal available by, e.g., end of July — into {mean, min, max, last} summaries.

Two feature families are tagged so baselines can select them:
- **climate/vegetation** — the 30 deseasonalized ``*_anom`` features + ``NDVI_anom_z``
- **severity** — ``dm_gte_d2`` / ``dm_class`` (USDM drought severity). Aggregating these lets us
  build a *severity-only* baseline and quantify how much within-season climate signal adds on top
  of the (strong) USDM severity indicator for predicting realized drought *loss*.
"""

from __future__ import annotations

import pandas as pd

from .config import DroughtConfig

# 30 deseasonalized anomaly features (primary climate inputs).
_VARS = ("precip_m", "VPD_kPa", "swvl1", "Tmax_K", "Tmean_C", "dm_prcp")
_WINDOWS = (7, 14, 30, 60, 90)
ANOM_FEATURES: tuple[str, ...] = tuple(f"{v}_{w}d_anom" for v in _VARS for w in _WINDOWS)
CLIMATE_FEATURES: tuple[str, ...] = ANOM_FEATURES + ("NDVI_anom_z",)
SEVERITY_FEATURES: tuple[str, ...] = ("dm_gte_d2", "dm_class")

_STATS = ("mean", "min", "max", "last")


def _feature_columns(bases: tuple[str, ...]) -> list[str]:
    """Output column names produced for a set of base features."""
    return [f"{b}_{s}" for b in bases for s in _STATS]


def climate_predictor_columns() -> list[str]:
    return _feature_columns(CLIMATE_FEATURES)


def severity_predictor_columns() -> list[str]:
    return _feature_columns(SEVERITY_FEATURES)


def aggregate_predictors(feature_table: pd.DataFrame, cfg: DroughtConfig) -> pd.DataFrame:
    """Aggregate within-season predictors up to ``cfg.cutoff_doy`` per (GEOID, year).

    Returns one row per (GEOID, year) with {mean, min, max, last} of every climate and severity
    feature, plus ``n_obs`` (observations before the cutoff) and ``n_stress_weeks`` (vegetation
    ≤ −1 SD). ``last`` is the value at the largest DOY at or before the cutoff.
    """
    df = feature_table[
        (feature_table["doy"] <= cfg.cutoff_doy)
        & feature_table["year"].between(cfg.year_min, cfg.year_max)
        & feature_table["STATEFP"].isin(cfg.states)
    ].copy()
    df = df.sort_values(["GEOID", "year", "doy"])

    bases = list(CLIMATE_FEATURES + SEVERITY_FEATURES)
    agg_spec = {b: list(_STATS) for b in bases}
    grouped = df.groupby(["GEOID", "year"]).agg(agg_spec)
    grouped.columns = [f"{base}_{stat}" for base, stat in grouped.columns]

    extras = df.groupby(["GEOID", "year"]).agg(
        n_obs=("doy", "size"),
        n_stress_weeks=("NDVI_anom_z", lambda s: int((s <= -1.0).sum())),
    )
    out = grouped.join(extras).reset_index()
    out["year"] = out["year"].astype(int)
    return out
