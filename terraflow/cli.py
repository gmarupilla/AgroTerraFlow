"""TerraFlow CLI — Typer-based subcommand interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, Callable

import typer

from .pipeline import run_pipeline
from .utils import logger

app = typer.Typer(
    name="terraflow",
    help="TerraFlow: reproducible geospatial agricultural modeling.",
    add_completion=False,
)

from .drought.cli import drought_app  # noqa: E402 (registered after app is created)

app.add_typer(drought_app, name="drought")


def _config_option() -> Any:
    return typer.Option(
        ...,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to YAML config file",
    )


ConfigPath = Annotated[Path, _config_option()]


def _invoke(name: str, fn: Callable[[], Any]) -> Any:
    """Run *fn* and translate known exceptions into uniform CLI exits."""
    try:
        return fn()
    except ValueError as e:
        logger.error(f"{name} configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except FileNotFoundError as e:
        logger.error(f"{name} file not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except ImportError as e:
        logger.error(f"{name} missing dependency: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except NotImplementedError as e:
        logger.error(f"{name} not yet implemented: {e}")
        print(f"ERROR: {name} not yet implemented - {e}", file=sys.stderr)
        raise SystemExit(2) from e
    except Exception as e:
        logger.error(f"{name} failed: {e}", exc_info=True)
        print(f"ERROR: {name} failed - {e}", file=sys.stderr)
        raise SystemExit(1) from e


@app.command("run")
def run_cmd(config: ConfigPath) -> None:
    """Run the geospatial modeling pipeline."""
    logger.info(f"TerraFlow run starting with config: {config}")
    _invoke("Pipeline", lambda: run_pipeline(config))
    logger.info("TerraFlow run completed successfully")


@app.command("sensitivity")
def sensitivity_cmd(config: ConfigPath) -> None:
    """Run Sobol' and/or Morris sensitivity analysis."""
    from .sensitivity import run_sensitivity

    report_path = _invoke("Sensitivity analysis", lambda: run_sensitivity(config))
    logger.info(f"Sensitivity analysis complete. Report: {report_path}")


@app.command("validate")
def validate_cmd(config: ConfigPath) -> None:
    """Run model validation (spatial-block cross-validation)."""
    logger.info(f"TerraFlow validation starting with config: {config}")
    from .validation import run_validation

    _invoke("Validation", lambda: run_validation(config))
    logger.info("TerraFlow validation completed successfully")


def main() -> None:
    """Entry point for the terraflow CLI."""
    app()


if __name__ == "__main__":
    main()
