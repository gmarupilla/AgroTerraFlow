"""terraflow.drought — impact-labeled drought-loss prediction benchmark.

Predicts *insured drought loss* (USDA RMA Cause of Loss) from within-season climate/vegetation
predictors — a decision-relevant impact target distinct from drought *severity* (USDM D2+) and
crop *yield* benchmarks.
"""

from __future__ import annotations

__all__ = [
    "baselines",
    "config",
    "dataset",
    "evaluate",
    "labels",
    "metrics",
    "nass",
    "predictors",
    "rma",
    "sob",
    "splits",
]
