#!/usr/bin/env python
"""Download RMA Cause-of-Loss archives for the configured years.

Usage: python scripts/01_fetch_rma.py --config configs/v0_corn_6state.yaml

Requires network egress to the RMA host. If blocked, download the archives manually and
place them in the config's ``rma_data_dir`` — the remaining steps are offline.
"""

from drought_impact.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["fetch", *sys.argv[1:]]))
