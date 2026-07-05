"""Assemble the drought-impact benchmark table and load it back.

Pipeline: parse RMA Cause of Loss → build labels → aggregate flashdry predictors → LEFT-join
predictors ⋈ labels on (GEOID, year). County-years present in the predictor panel but absent from
Cause of Loss are genuine *insured-loss negatives* (drought_loss_ratio = 0, not significant), so
they are retained and filled — this both completes the panel and provides the negative class.

Writes ``benchmark.parquet`` + ``manifest.json`` (config snapshot + input fingerprints + a
deterministic build fingerprint) + ``splits.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from ..core.run_identity import canonicalize_config, fingerprint_file
from .config import DroughtConfig
from .labels import build_labels
from .predictors import aggregate_predictors
from .rma import load_col
from .splits import describe_splits

_LABEL_FILL = {
    "drought_indemnity": 0.0,
    "total_indemnity": 0.0,
    "liability": 0.0,
    "drought_share": 0.0,
    "drought_loss_ratio": 0.0,
    "significant_drought_loss": False,
}


def assemble_benchmark(cfg: DroughtConfig, *, write: bool = True) -> pd.DataFrame:
    """Build the benchmark table (and, by default, persist artifacts under ``cfg.output_dir``)."""
    col = load_col(cfg.rma_dir, cfg.years, states=cfg.states, commodity=cfg.crop)
    labels = build_labels(col, cfg)

    feature_table = pd.read_parquet(cfg.feature_table)
    feature_table["GEOID"] = feature_table["GEOID"].astype(str)
    predictors = aggregate_predictors(feature_table, cfg)
    predictors["GEOID"] = predictors["GEOID"].astype(str)

    labels["GEOID"] = labels["GEOID"].astype(str)
    benchmark = predictors.merge(labels, on=["GEOID", "year"], how="left")
    benchmark = benchmark.fillna(_LABEL_FILL)
    benchmark["significant_drought_loss"] = benchmark["significant_drought_loss"].astype(bool)
    benchmark = benchmark.sort_values(["GEOID", "year"]).reset_index(drop=True)

    if write:
        _write_artifacts(benchmark, cfg, col_files=_col_paths(cfg))
    return benchmark


def load_benchmark(output_dir: Path) -> pd.DataFrame:
    """Load a previously assembled ``benchmark.parquet``."""
    path = Path(output_dir) / "benchmark.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No benchmark at {path}; run `assemble_benchmark` first.")
    return pd.read_parquet(path)


def build_fingerprint(cfg: DroughtConfig, input_digests: list[dict]) -> str:
    """Deterministic build fingerprint over the canonical config + input file digests."""
    payload = canonicalize_config(_config_dict(cfg))
    hasher = hashlib.sha256()
    hasher.update(payload)
    for d in sorted(input_digests, key=lambda x: x["path"]):
        hasher.update(d["sha256"].encode("utf-8"))
    return hasher.hexdigest()


def _config_dict(cfg: DroughtConfig) -> dict:
    d = cfg.model_dump()
    return {k: (str(v) if isinstance(v, Path) else v) for k, v in d.items()}


def _col_paths(cfg: DroughtConfig) -> list[Path]:
    out = []
    for year in cfg.years:
        for name in (f"colsom_{year}.zip", f"colsom{year % 100:02d}.txt", f"colsom_{year}.txt"):
            p = Path(cfg.rma_dir) / name
            if p.exists():
                out.append(p)
                break
    return out


def _write_artifacts(benchmark: pd.DataFrame, cfg: DroughtConfig, col_files: list[Path]) -> None:
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    benchmark.to_parquet(out / "benchmark.parquet", index=False)

    input_digests = [fingerprint_file(str(cfg.feature_table))]
    input_digests += [fingerprint_file(str(p)) for p in col_files]
    manifest = {
        "schema_version": "1",
        "config": _config_dict(cfg),
        "inputs": input_digests,
        "build_fingerprint": build_fingerprint(cfg, input_digests),
        "n_rows": int(len(benchmark)),
        "n_counties": int(benchmark["GEOID"].nunique()),
        "years": [int(benchmark["year"].min()), int(benchmark["year"].max())],
        "positive_rate": float(benchmark["significant_drought_loss"].mean()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "splits.json").write_text(json.dumps(describe_splits(cfg), indent=2), encoding="utf-8")
