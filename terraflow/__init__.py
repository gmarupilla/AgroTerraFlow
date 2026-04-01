"""
TerraFlow: A reproducible workflow for geospatial agricultural modeling.

This package provides utilities to:
- Load and validate input data (rasters, climate CSVs)
- Perform basic geospatial operations
- Compute simple suitability scores
- Run an end-to-end, configurable pipeline
"""

from .config import PipelineConfig, load_config
from .pipeline import run_pipeline
from .validation import run_validation
from .stats import (
    ClimateSummary,
    RasterSummary,
    RunReport,
    batch_summarize,
    compare_rasters,
    summarize_raster,
    summarize_raster_file,
)

__all__ = [
    "PipelineConfig",
    "load_config",
    "run_pipeline",
    "run_validation",
    "RasterSummary",
    "ClimateSummary",
    "RunReport",
    "summarize_raster",
    "summarize_raster_file",
    "compare_rasters",
    "batch_summarize",
]


__version__ = "0.2.1"
