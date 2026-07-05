"""Drought-Impact Prediction Benchmark — v0.

An impact-labeled, prediction-ready drought benchmark whose target is *insured drought
loss* (USDA RMA Cause-of-Loss indemnity), not severity (USDM) or yield. Self-contained
and spin-out ready — no dependency on the surrounding TerraFlow package.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config import BenchmarkConfig, load_config
from .fingerprint import compute_build_fingerprint

__all__ = ["BenchmarkConfig", "load_config", "compute_build_fingerprint", "__version__"]
