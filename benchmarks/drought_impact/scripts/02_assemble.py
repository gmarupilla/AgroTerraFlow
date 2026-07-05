#!/usr/bin/env python
"""Assemble benchmark.parquet + manifest.json (labels ⋈ predictors ⋈ coverage).

Usage: python scripts/02_assemble.py --config configs/v0_corn_6state.yaml
"""

from drought_impact.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["build", *sys.argv[1:]]))
