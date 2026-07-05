"""Official evaluation splits: temporal held-out, spatial-block, and leave-one-year-out.

Every split is expressed over row keys ``"{GEOID}:{year}"`` so ``splits.json`` is
self-describing and independent of row order in ``benchmark.parquet``.

The spatial-block assignment mirrors ``terraflow/validation.py::_assign_block_ids``: the
lat/lon bounding box is divided into an ``n × n`` grid and each county is placed by its
centroid, so held-out blocks are spatially contiguous (guards against autocorrelation
leakage, per Roberts et al. 2017).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BenchmarkConfig


def row_key(geoid: str, year: int) -> str:
    return f"{geoid}:{int(year)}"


def _row_keys(df: pd.DataFrame) -> list[str]:
    return [row_key(g, y) for g, y in zip(df["GEOID"], df["year"])]


def _assign_block_ids(lats: np.ndarray, lons: np.ndarray, n_blocks_side: int) -> np.ndarray:
    """Assign each point a spatial block ID on a regular n×n grid (mirrors terraflow)."""
    lat_edges = np.linspace(lats.min(), lats.max(), n_blocks_side + 1)
    lon_edges = np.linspace(lons.min(), lons.max(), n_blocks_side + 1)
    row_idx = np.digitize(lats, lat_edges[1:-1])
    col_idx = np.digitize(lons, lon_edges[1:-1])
    return row_idx * n_blocks_side + col_idx


def build_splits(
    benchmark: pd.DataFrame,
    centroids: pd.DataFrame,
    cfg: BenchmarkConfig,
) -> dict:
    """Build the temporal / spatial-block / LOYO splits over the benchmark rows."""
    df = benchmark[["GEOID", "year"]].copy()
    df["year"] = df["year"].astype(int)

    # --- Temporal held-out ---------------------------------------------------------
    test_years = set(cfg.temporal_test_years)
    is_test = df["year"].isin(test_years)
    temporal = {
        "test_years": sorted(test_years),
        "train": _row_keys(df[~is_test]),
        "test": _row_keys(df[is_test]),
    }

    # --- Spatial block -------------------------------------------------------------
    spatial: dict = {"n_blocks_side": cfg.spatial_blocks_side, "folds": []}
    if {"lat", "lon"}.issubset(centroids.columns) and len(centroids) > 0:
        cent = centroids.dropna(subset=["lat", "lon"]).copy()
        block_ids = _assign_block_ids(cent["lat"].to_numpy(), cent["lon"].to_numpy(), cfg.spatial_blocks_side)
        cent["block_id"] = block_ids
        geoid_to_block = dict(zip(cent["GEOID"], cent["block_id"]))
        df_blocks = df.assign(block_id=df["GEOID"].map(geoid_to_block))
        for block in sorted(b for b in df_blocks["block_id"].dropna().unique()):
            test_rows = df_blocks[df_blocks["block_id"] == block]
            train_rows = df_blocks[df_blocks["block_id"] != block]
            spatial["folds"].append(
                {"block_id": int(block), "train": _row_keys(train_rows), "test": _row_keys(test_rows)}
            )

    # --- Leave-one-year-out --------------------------------------------------------
    loyo: dict = {"folds": []}
    for year in sorted(df["year"].unique()):
        test_rows = df[df["year"] == year]
        train_rows = df[df["year"] != year]
        loyo["folds"].append({"year": int(year), "train": _row_keys(train_rows), "test": _row_keys(test_rows)})

    return {"temporal": temporal, "spatial_block": spatial, "loyo": loyo}


def validate_splits(splits: dict) -> None:
    """Assert train/test disjointness for every fold; raise on any leakage."""
    t = splits["temporal"]
    if set(t["train"]) & set(t["test"]):
        raise ValueError("temporal split: train and test overlap")
    for kind in ("spatial_block", "loyo"):
        for fold in splits[kind]["folds"]:
            if set(fold["train"]) & set(fold["test"]):
                raise ValueError(f"{kind} fold {fold}: train and test overlap")


def write_splits(splits: dict, output_dir: str | Path) -> Path:
    """Write ``splits.json`` under ``output_dir`` and return its path."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "splits.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2, sort_keys=True)
    return path
