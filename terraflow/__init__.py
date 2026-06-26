"""
TerraFlow: A reproducible workflow for geospatial agricultural modeling.

This package provides utilities to:
- Load and validate input data (rasters, climate CSVs)
- Perform basic geospatial operations
- Compute simple suitability scores
- Run an end-to-end, configurable pipeline
"""

from .config import PipelineConfig, load_config
from .core.run_identity import compute_run_fingerprint
from .export import to_h3
from .pipeline import run_pipeline
from .stats import (
    ClimateSummary,
    RasterSummary,
    RunReport,
    batch_summarize,
    compare_rasters,
    summarize_raster,
    summarize_raster_file,
)
from .validation import run_validation

__all__ = [
    "PipelineConfig",
    "compute_run_fingerprint",
    "load_config",
    "run_pipeline",
    "run_validation",
    "to_h3",
    "RasterSummary",
    "ClimateSummary",
    "RunReport",
    "summarize_raster",
    "summarize_raster_file",
    "compare_rasters",
    "batch_summarize",
]


__version__ = "0.4.0"
