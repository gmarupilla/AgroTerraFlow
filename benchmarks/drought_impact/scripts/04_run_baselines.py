#!/usr/bin/env python
"""Fit baselines and write the leaderboard (leaderboard.csv).

Usage: python scripts/04_run_baselines.py --config configs/v0_corn_6state.yaml
"""

from drought_impact.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["baselines", *sys.argv[1:]]))
