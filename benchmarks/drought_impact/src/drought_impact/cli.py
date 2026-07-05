"""Thin command-line entry point: ``drought-impact <command> --config <yaml>``.

Commands
--------
- ``fetch``     download RMA COL archives for the configured years.
- ``build``     assemble ``benchmark.parquet`` + ``manifest.json``.
- ``splits``    write ``splits.json`` from an existing ``benchmark.parquet``.
- ``baselines`` fit baselines and print/write the leaderboard.

Uses only argparse (stdlib) — no dependency on TerraFlow's Typer CLI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .assemble import assemble_benchmark
from .baselines import run_baselines
from .config import load_config
from .predictors import extract_centroids
from .rma import download_col_year
from .splits import build_splits, validate_splits, write_splits


def _cmd_fetch(cfg) -> None:
    for year in cfg.years():
        path = download_col_year(year, cfg)
        print(f"  {year}: {path}")


def _cmd_build(cfg) -> None:
    benchmark, manifest = assemble_benchmark(cfg, write=True)
    print(f"  wrote {len(benchmark)} rows → {Path(cfg.output_dir) / 'benchmark.parquet'}")
    print(f"  build_fingerprint = {manifest['build_fingerprint']}")


def _cmd_splits(cfg) -> None:
    benchmark = pd.read_parquet(Path(cfg.output_dir) / "benchmark.parquet")
    centroids = (
        extract_centroids(pd.read_parquet(cfg.feature_table_path))
        if cfg.feature_table_path is not None
        else pd.DataFrame({"GEOID": sorted(benchmark["GEOID"].unique())})
    )
    splits = build_splits(benchmark, centroids, cfg)
    validate_splits(splits)
    path = write_splits(splits, cfg.output_dir)
    print(f"  wrote splits → {path}")


def _cmd_baselines(cfg) -> None:
    import json

    benchmark = pd.read_parquet(Path(cfg.output_dir) / "benchmark.parquet")
    with (Path(cfg.output_dir) / "splits.json").open() as f:
        splits = json.load(f)
    leaderboard = run_baselines(benchmark, splits)
    print(leaderboard.to_string(index=False))
    leaderboard.to_csv(Path(cfg.output_dir) / "leaderboard.csv", index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drought-impact")
    parser.add_argument("command", choices=["fetch", "build", "splits", "baselines"])
    parser.add_argument("--config", required=True, help="path to the benchmark YAML config")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    {
        "fetch": _cmd_fetch,
        "build": _cmd_build,
        "splits": _cmd_splits,
        "baselines": _cmd_baselines,
    }[
        args.command
    ](cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
