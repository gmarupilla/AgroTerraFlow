"""Predictor aggregation from the flashdry feature table.

The flashdry ``feature_table.parquet`` is weekly, keyed on ``GEOID``/``date``/``year``,
carrying ~60 deseasonalized ``_anom`` features (+ NDVI). For each ``GEOID`` × crop-year
we aggregate every ``_anom`` feature over a growing-season window into a fixed vector of
summary statistics — one row per county-year, ready to join with the labels.

The window ``[season_start_doy, cutoff_doy]`` drives the **early-warning framing**: with
``cutoff_doy`` ~= Jul 31 the predictors use only signal available before the loss is
realized. Pass ``end_of_season=True`` for the full-season comparison variant.
"""

from __future__ import annotations

import pandas as pd

from .config import BenchmarkConfig

FEATURE_SUFFIX = "_anom"
# A week counts as "stress" when its deseasonalized anomaly is more than STRESS_Z
# standard deviations below normal. Documented, configurable via this module constant.
STRESS_Z = -1.0
_STATS = ["mean", "min", "max", "last", "nstress"]


def anom_columns(feature_table: pd.DataFrame) -> list[str]:
    """Return the deseasonalized ``*_anom`` feature column names, sorted for determinism."""
    return sorted(c for c in feature_table.columns if c.endswith(FEATURE_SUFFIX))


def _day_of_year(dates: pd.Series) -> pd.Series:
    return pd.to_datetime(dates).dt.dayofyear


def aggregate_predictors(
    feature_table: pd.DataFrame,
    cfg: BenchmarkConfig,
    *,
    end_of_season: bool = False,
) -> pd.DataFrame:
    """Aggregate ``_anom`` features to one vector per ``GEOID`` × year.

    Output columns: ``GEOID``, ``year``, ``n_obs``, and for each feature ``f`` the set
    ``{f_mean, f_min, f_max, f_last, f_nstress}``.
    """
    df = feature_table.copy()
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["date"]).dt.year
    df["doy"] = _day_of_year(df["date"])

    lo = cfg.season_start_doy
    hi = 366 if end_of_season else cfg.cutoff_doy
    df = df[(df["doy"] >= lo) & (df["doy"] <= hi)].copy()

    features = anom_columns(df)
    if not features:
        raise ValueError("feature_table has no '*_anom' columns to aggregate")

    df = df.sort_values(["GEOID", "year", "date"])
    grouped = df.groupby(["GEOID", "year"], dropna=True)

    parts: list[pd.DataFrame] = []
    n_obs = grouped.size().rename("n_obs")
    parts.append(n_obs)

    for feat in features:
        agg = grouped[feat].agg(["mean", "min", "max", "last"])
        agg.columns = [f"{feat}_{stat}" for stat in ["mean", "min", "max", "last"]]
        nstress = grouped[feat].apply(lambda s: int((s < STRESS_Z).sum())).rename(f"{feat}_nstress")
        parts.append(agg)
        parts.append(nstress)

    out = pd.concat(parts, axis=1).reset_index()
    return out


def extract_centroids(feature_table: pd.DataFrame) -> pd.DataFrame:
    """Return a per-``GEOID`` centroid (``lat``, ``lon``) frame if those columns exist.

    Used by the spatial-block split. Returns an empty frame (GEOID column only) when the
    feature table carries no coordinate columns.
    """
    lat_col = next((c for c in ("lat", "latitude", "centroid_lat") if c in feature_table.columns), None)
    lon_col = next((c for c in ("lon", "longitude", "centroid_lon") if c in feature_table.columns), None)
    if lat_col is None or lon_col is None:
        return pd.DataFrame({"GEOID": sorted(feature_table["GEOID"].unique())})
    cent = feature_table.groupby("GEOID")[[lat_col, lon_col]].mean().reset_index()
    return cent.rename(columns={lat_col: "lat", lon_col: "lon"})
