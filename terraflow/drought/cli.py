"""Typer sub-app for the drought-impact benchmark: ``terraflow drought {fetch,build,evaluate}``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ..utils import logger
from .config import DroughtConfig
from .dataset import assemble_benchmark, load_benchmark
from .evaluate import run_leaderboard
from .rma import download_col_years
from .sob import download_sob_years

drought_app = typer.Typer(
    name="drought",
    help="Impact-labeled drought-loss prediction benchmark (RMA Cause of Loss).",
    add_completion=False,
)

_ConfigOpt = Annotated[
    Path,
    typer.Option("--config", "-c", exists=True, dir_okay=False, readable=True, help="Benchmark YAML config"),
]


@drought_app.command("fetch")
def fetch_cmd(
    rma_dir: Annotated[Path, typer.Option(help="Directory to store RMA Cause of Loss ZIPs")],
    year_min: Annotated[int, typer.Option(help="First commodity year")] = 2000,
    year_max: Annotated[int, typer.Option(help="Last commodity year")] = 2023,
    overwrite: Annotated[bool, typer.Option(help="Re-download existing files")] = False,
    sob_dir: Annotated[Path | None, typer.Option(help="Also fetch SOB coverage files (true liability) here")] = None,
) -> None:
    """Download RMA Cause of Loss (and optionally Summary-of-Business coverage) files."""
    years = list(range(year_min, year_max + 1))
    logger.info(f"Fetching RMA Cause of Loss {year_min}-{year_max} into {rma_dir}")
    paths = download_col_years(years, rma_dir, overwrite=overwrite)
    logger.info(f"Fetched {len(paths)} Cause of Loss files.")
    if sob_dir is not None:
        sob_paths = download_sob_years(years, sob_dir, overwrite=overwrite)
        logger.info(f"Fetched {len(sob_paths)} Summary-of-Business coverage files.")


@drought_app.command("build")
def build_cmd(config: _ConfigOpt) -> None:
    """Assemble the benchmark table + manifest + splits from a config."""
    cfg = DroughtConfig.from_yaml(config)
    logger.info(f"Building drought benchmark → {cfg.output_dir}")
    benchmark = assemble_benchmark(cfg, write=True)
    logger.info(
        f"Built {len(benchmark)} rows over {benchmark['GEOID'].nunique()} counties; "
        f"positive rate {benchmark['significant_drought_loss'].mean():.3f}"
    )


@drought_app.command("evaluate")
def evaluate_cmd(config: _ConfigOpt) -> None:
    """Run the leaderboard on a previously built benchmark."""
    cfg = DroughtConfig.from_yaml(config)
    benchmark = load_benchmark(cfg.output_dir)
    report = run_leaderboard(benchmark, cfg, write_dir=cfg.output_dir)
    top = report["temporal"]["classification"]
    logger.info("Leaderboard (temporal split) written. Classification PR-AUC by model:")
    for model, m in top.items():
        print(f"  {model:28s} PR-AUC={m['pr_auc']:.3f}  ROC-AUC={m['roc_auc']:.3f}")
    print(json.dumps(report["counts"], indent=2))
