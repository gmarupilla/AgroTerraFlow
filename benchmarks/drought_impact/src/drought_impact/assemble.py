"""Assemble the benchmark table: labels ⋈ predictors ⋈ coverage → benchmark.parquet.

Also writes ``manifest.json`` carrying a deterministic build fingerprint over the config
(the knobs that shape the output) plus SHA-256s of every input file. Identical inputs →
identical fingerprint → reproducible builds (AgroTerraFlow's provenance DNA, vendored).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .baselines import INDEX_COLUMN_CANDIDATES
from .config import BenchmarkConfig
from .coverage import build_coverage
from .fingerprint import compute_build_fingerprint, fingerprint_file
from .labels import build_labels
from .predictors import aggregate_predictors
from .rma import load_col

logger = logging.getLogger(__name__)

# Non-predictor columns, in fixed leading order.
_LEADING_COLUMNS = [
    "GEOID",
    "year",
    "drought_loss_cost",
    "significant_loss",
    "drought_indemnity",
    "county_liability",
    "total_premium_sum",
    "total_indemnity",
    "insured_acres",
    "planted_acres",
    "insured_acre_fraction",
]

# Config path attributes that carry external severity-index inputs, and the column
# names (a subset of INDEX_COLUMN_CANDIDATES) each is expected to provide.
_INDEX_PATH_ATTRS = ["wxcond_path", "vci_tci_vhi_path", "usdm_path"]


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic column order: leading label/coverage, then indices, then predictors."""
    leading = [c for c in _LEADING_COLUMNS if c in df.columns]
    index_cols = [c for c in INDEX_COLUMN_CANDIDATES if c in df.columns]
    rest = sorted(c for c in df.columns if c not in leading and c not in index_cols)
    return df[leading + index_cols + rest]


def _aggregate_index_frame(frame: pd.DataFrame, cfg: BenchmarkConfig, value_cols: list[str]) -> pd.DataFrame:
    """Reduce a (possibly weekly) index frame to one row per ``GEOID`` × year.

    Weekly frames (those with a ``date`` column) are averaged over the same growing-season
    window ``[season_start_doy, cutoff_doy]`` used for the predictors, preserving the
    early-warning framing. Already-annual frames are grouped directly.
    """
    frame = frame.copy()
    frame["GEOID"] = frame["GEOID"].astype(str).str.zfill(5)
    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"])
        frame["year"] = frame["year"] if "year" in frame.columns else dates.dt.year
        doy = dates.dt.dayofyear
        frame = frame[(doy >= cfg.season_start_doy) & (doy <= cfg.cutoff_doy)]
    frame["year"] = frame["year"].astype("Int64")
    return frame.groupby(["GEOID", "year"], dropna=True)[value_cols].mean().reset_index()


def attach_index_columns(benchmark: pd.DataFrame, cfg: BenchmarkConfig) -> pd.DataFrame:
    """Join configured severity-index inputs (WxCond / VCI-TCI-VHI / USDM) onto the benchmark.

    Each configured path is read, its recognized index columns
    (:data:`drought_impact.baselines.INDEX_COLUMN_CANDIDATES`) are aggregated to
    ``GEOID`` × year, and left-joined. When a path is set but missing or carries no
    recognized columns, a warning is logged instead of silently dropping the input — so
    the severity-index baselines are never quietly skipped.
    """
    out = benchmark
    for attr in _INDEX_PATH_ATTRS:
        path = getattr(cfg, attr)
        if path is None:
            continue
        if not Path(path).exists():
            logger.warning("%s=%s does not exist; index columns not joined", attr, path)
            continue
        frame = pd.read_parquet(path)
        if "GEOID" not in frame.columns:
            logger.warning("%s=%s has no GEOID column; index columns not joined", attr, path)
            continue
        value_cols = [c for c in INDEX_COLUMN_CANDIDATES if c in frame.columns]
        if not value_cols:
            logger.warning(
                "%s=%s has no recognized index columns %s; nothing joined",
                attr,
                path,
                INDEX_COLUMN_CANDIDATES,
            )
            continue
        agg = _aggregate_index_frame(frame, cfg, value_cols)
        out = out.merge(agg, on=["GEOID", "year"], how="left")
    return out


def join_benchmark(
    labels: pd.DataFrame,
    predictors: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:
    """Pure join of the three tables on (``GEOID``, ``year``) → the benchmark frame.

    Left-joined on labels (the universe of observed county-years). Column order is
    deterministic: leading label/coverage columns, then predictor columns sorted by name.
    """
    df = labels.merge(coverage, on=["GEOID", "year"], how="left")
    df = df.merge(predictors, on=["GEOID", "year"], how="left")

    leading = [c for c in _LEADING_COLUMNS if c in df.columns]
    predictor_cols = sorted(c for c in df.columns if c not in leading)
    df = df[leading + predictor_cols]
    return df.sort_values(["GEOID", "year"]).reset_index(drop=True)


def _input_fingerprints(cfg: BenchmarkConfig) -> list[dict]:
    """Fingerprint every input file that actually exists on disk (deterministic order)."""
    fps: list[dict] = []
    paths: list[Path] = []
    for attr in ("feature_table_path", "nass_acres_path", "wxcond_path", "vci_tci_vhi_path", "usdm_path"):
        p = getattr(cfg, attr)
        if p is not None and Path(p).exists():
            paths.append(Path(p))
    # COL archives present in rma_data_dir for the configured years.
    for year in cfg.years():
        cand = Path(cfg.rma_data_dir) / cfg.rma_source.filename_template.format(year=year)
        for p in (cand, cand.with_suffix(".txt"), cand.with_suffix(".csv")):
            if p.exists():
                paths.append(p)
                break
    for p in sorted(set(paths)):
        fps.append(fingerprint_file(p))
    return fps


def assemble_benchmark(cfg: BenchmarkConfig, *, write: bool = True) -> tuple[pd.DataFrame, dict]:
    """Run the full assembly from disk and (optionally) write artifacts.

    Returns ``(benchmark_df, manifest_dict)``. Writes ``benchmark.parquet`` and
    ``manifest.json`` under ``cfg.output_dir`` when ``write`` is True.
    """
    col = load_col(cfg)
    labels = build_labels(col, cfg)

    if cfg.feature_table_path is None:
        raise ValueError("cfg.feature_table_path is required to assemble predictors")
    feature_table = pd.read_parquet(cfg.feature_table_path)
    predictors = aggregate_predictors(feature_table, cfg)

    nass = pd.read_parquet(cfg.nass_acres_path) if cfg.nass_acres_path is not None else None
    coverage = build_coverage(col, nass)

    benchmark = join_benchmark(labels, predictors, coverage)
    benchmark = _order_columns(attach_index_columns(benchmark, cfg))

    fingerprint = compute_build_fingerprint(cfg.as_fingerprint_dict(), _input_fingerprints(cfg))
    manifest = {
        "build_fingerprint": fingerprint,
        "config": cfg.as_fingerprint_dict(),
        "n_rows": int(len(benchmark)),
        "n_counties": int(benchmark["GEOID"].nunique()),
        "year_range": [int(cfg.year_min), int(cfg.year_max)],
        "n_positive": int(benchmark["significant_loss"].sum()),
    }

    if write:
        out_dir = Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        benchmark.to_parquet(out_dir / "benchmark.parquet", index=False)
        with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

    return benchmark, manifest
