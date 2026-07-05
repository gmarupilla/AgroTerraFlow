#!/usr/bin/env python
"""Write splits.json (temporal / spatial-block / LOYO) from benchmark.parquet.

Usage: python scripts/03_splits.py --config configs/v0_corn_6state.yaml
"""

from drought_impact.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["splits", *sys.argv[1:]]))
