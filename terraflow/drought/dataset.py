"""Assemble the drought-impact benchmark table and load it back.

Pipeline: parse RMA Cause of Loss → numerator labels → join the true total insured liability
(Summary-of-Business coverage file) and NASS planted acres → aggregate flashdry predictors →
LEFT-join predictors ⋈ labels on (GEOID, year) → finalize the drought-loss-ratio + binary + coverage
targets. County-years present in the predictor panel but absent from Cause of Loss are genuine
insured-loss negatives (drought_loss_ratio = 0, not significant) and are retained and filled.

Writes ``benchmark.parquet`` + ``manifest.json`` (config snapshot + input fingerprints + a
deterministic build fingerprint) + ``splits.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from ..core.run_identity import canonicalize_config, fingerprint_file
from .config import DroughtConfig
from .labels import build_labels, finalize_targets
from .nass import fetch_planted_acres
from .predictors import aggregate_predictors
from .rma import load_col
from .sob import aggregate_sob, load_sob
from .splits import describe_splits

# County-years with predictors but no Cause of Loss record are true zero-loss negatives.
_COL_FILL = {
    "drought_indemnity": 0.0,
    "total_indemnity": 0.0,
    "col_liability": 0.0,
    "drought_share": 0.0,
}
_SOB_FILL = {"total_liability": 0.0, "total_premium": 0.0, "insured_acres": 0.0}


def assemble_benchmark(cfg: DroughtConfig, *, write: bool = True, nass_api_key: str | None = None) -> pd.DataFrame:
    """Build the benchmark table (and, by default, persist artifacts under ``cfg.output_dir``)."""
    col = load_col(cfg.rma_dir, cfg.years, states=cfg.states, commodity=cfg.crop)
    labels = build_labels(col, cfg)
    labels["GEOID"] = labels["GEOID"].astype(str)

    feature_table = pd.read_parquet(cfg.feature_table)
    feature_table["GEOID"] = feature_table["GEOID"].astype(str)
    predictors = aggregate_predictors(feature_table, cfg)
    predictors["GEOID"] = predictors["GEOID"].astype(str)

    benchmark = predictors.merge(labels, on=["GEOID", "year"], how="left").fillna(_COL_FILL)

    if cfg.sob_dir is not None:
        sob = load_sob(cfg.sob_dir, cfg.years, states=cfg.states, commodity=cfg.crop)
        sob_agg = aggregate_sob(sob)
        sob_agg["GEOID"] = sob_agg["GEOID"].astype(str)
        benchmark = benchmark.merge(sob_agg, on=["GEOID", "year"], how="left").fillna(_SOB_FILL)

    extra_digests: list[dict] = []
    if cfg.add_coverage:
        key = nass_api_key or os.environ.get("NASS_API_KEY")
        if key:
            nass = fetch_planted_acres(cfg.state_alphas, cfg.crop, key)
            nass["GEOID"] = nass["GEOID"].astype(str)
            benchmark = benchmark.merge(nass, on=["GEOID", "year"], how="left")
            # NASS is a live source (no local file); hash the fetched acreage so revised values
            # invalidate the build fingerprint, preserving the reproducibility contract.
            nass_bytes = nass.sort_values(["GEOID", "year"]).to_csv(index=False).encode("utf-8")
            extra_digests.append(
                {"path": f"nass:quickstats:{cfg.crop}", "sha256": hashlib.sha256(nass_bytes).hexdigest()}
            )

    benchmark = finalize_targets(benchmark, cfg)
    benchmark["significant_drought_loss"] = benchmark["significant_drought_loss"].astype(bool)
    benchmark = benchmark.sort_values(["GEOID", "year"]).reset_index(drop=True)

    if write:
        _write_artifacts(benchmark, cfg, extra_digests=extra_digests)
    return benchmark


def load_benchmark(output_dir: Path) -> pd.DataFrame:
    """Load a previously assembled ``benchmark.parquet``."""
    path = Path(output_dir) / "benchmark.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No benchmark at {path}; run `assemble_benchmark` first.")
    return pd.read_parquet(path)


def build_fingerprint(cfg: DroughtConfig, input_digests: list[dict]) -> str:
    """Deterministic build fingerprint over the canonical config + input file digests."""
    hasher = hashlib.sha256()
    hasher.update(canonicalize_config(_config_dict(cfg)))
    for d in sorted(input_digests, key=lambda x: x["path"]):
        hasher.update(d["sha256"].encode("utf-8"))
    return hasher.hexdigest()


def _config_dict(cfg: DroughtConfig) -> dict:
    d = cfg.model_dump()
    return {k: (str(v) if isinstance(v, Path) else v) for k, v in d.items()}


def _rma_paths(cfg: DroughtConfig, prefix: str, directory: Path | None) -> list[Path]:
    if directory is None:
        return []
    out = []
    for year in cfg.years:
        for name in (f"{prefix}_{year}.zip", f"{prefix}{year % 100:02d}.txt", f"{prefix}_{year}.txt"):
            p = Path(directory) / name
            if p.exists():
                out.append(p)
                break
    return out


def _write_artifacts(benchmark: pd.DataFrame, cfg: DroughtConfig, extra_digests: list[dict] | None = None) -> None:
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    benchmark.to_parquet(out / "benchmark.parquet", index=False)

    input_paths = [Path(cfg.feature_table)]
    input_paths += _rma_paths(cfg, "colsom", cfg.rma_dir)
    input_paths += _rma_paths(cfg, "sobcov", cfg.sob_dir)
    input_digests = [fingerprint_file(str(p)) for p in input_paths]
    input_digests += extra_digests or []
    manifest = {
        "schema_version": "2",
        "config": _config_dict(cfg),
        "inputs": input_digests,
        "build_fingerprint": build_fingerprint(cfg, input_digests),
        "n_rows": int(len(benchmark)),
        "n_counties": int(benchmark["GEOID"].nunique()),
        "years": [int(benchmark["year"].min()), int(benchmark["year"].max())],
        "positive_rate": float(benchmark["significant_drought_loss"].mean()),
        "has_coverage_column": bool("insured_acre_fraction" in benchmark.columns),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "splits.json").write_text(json.dumps(describe_splits(cfg), indent=2), encoding="utf-8")
