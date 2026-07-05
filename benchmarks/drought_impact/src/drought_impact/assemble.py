"""Assemble the benchmark table: labels ⋈ predictors ⋈ coverage → benchmark.parquet.

Also writes ``manifest.json`` carrying a deterministic build fingerprint over the config
(the knobs that shape the output) plus SHA-256s of every input file. Identical inputs →
identical fingerprint → reproducible builds (AgroTerraFlow's provenance DNA, vendored).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import BenchmarkConfig
from .coverage import build_coverage
from .fingerprint import compute_build_fingerprint, fingerprint_file
from .labels import build_labels
from .predictors import aggregate_predictors
from .rma import load_col

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
