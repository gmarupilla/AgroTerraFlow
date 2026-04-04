"""TerraFlow CLI — Typer-based subcommand interface."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

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
        typer.Option(..., "--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run the geospatial modeling pipeline."""
    logger.info(f"TerraFlow run starting with config: {config}")
    try:
        run_pipeline(config)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"ERROR: Pipeline failed - {e}", file=sys.stderr)
        raise SystemExit(1)
    logger.info("TerraFlow run completed successfully")


@app.command("sensitivity")
def sensitivity_cmd(
    config: Annotated[
        Path,
        typer.Option(..., "--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run Sobol' and/or Morris sensitivity analysis."""
    from .sensitivity import run_sensitivity
    try:
        report_path = run_sensitivity(config)
        logger.info(f"Sensitivity analysis complete. Report: {report_path}")
    except ValueError as e:
        logger.error(f"Sensitivity analysis configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Sensitivity analysis failed: {e}", exc_info=True)
        print(f"ERROR: Sensitivity analysis failed - {e}", file=sys.stderr)
        raise SystemExit(1)


@app.command("validate")
def validate_cmd(
    config: Annotated[
        Path,
        typer.Option(..., "--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run model validation (spatial CV, Cohen's kappa, Moran's I)."""
    logger.info(f"TerraFlow validation starting with config: {config}")
    try:
        from .validation import run_validation
        run_validation(config)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        print(f"ERROR: Validation failed - {e}", file=sys.stderr)
        raise SystemExit(1)
    logger.info("TerraFlow validation completed successfully")


@app.command("export")
def export_cmd(
    config: Annotated[
        Path,
        typer.Option(..., "--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
    format: Annotated[
        str,
        typer.Option(..., "--format", "-f", help="Export format (currently: h3)"),
    ],
    resolution: Annotated[
        int | None,
        typer.Option("--resolution", "-r", help="H3 resolution override (0-15)"),
    ] = None,
) -> None:
    """Export pipeline results to an alternative format."""
    logger.info(f"TerraFlow export starting with config: {config}, format: {format}")
    try:
        from .export import run_export
        output_path = run_export(config, resolution_override=resolution, format=format)
        logger.info(f"Export complete: {output_path}")
    except ValueError as e:
        logger.error(f"Export configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        print(f"ERROR: Export failed - {e}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    """Entry point for the terraflow CLI."""
    app()


if __name__ == "__main__":
    main()
