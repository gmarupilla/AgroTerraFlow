"""TerraFlow CLI — Typer-based subcommand interface."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from .pipeline import run_pipeline
from .utils import logger

app = typer.Typer(
    name="terraflow",
    help="TerraFlow: reproducible geospatial agricultural modeling.",
    add_completion=False,
)


@app.command("run")
def run_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run the geospatial modeling pipeline."""
    logger.info("TerraFlow run starting with config: %s", config)
    try:
        run_pipeline(config)
    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        print(f"ERROR: Pipeline failed - {e}", file=sys.stderr)
        raise SystemExit(1)
    logger.info("TerraFlow run completed successfully")


@app.command("sensitivity")
def sensitivity_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run Sobol' and/or Morris sensitivity analysis."""
    # Import here to avoid circular imports and allow Plan 02 to create sensitivity.py
    from .sensitivity import run_sensitivity
    run_sensitivity(config)


def main() -> None:
    """Entry point for the terraflow CLI."""
    app()


if __name__ == "__main__":
    main()
