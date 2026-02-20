---
title: Output Artifact Contract
description: The guaranteed output files written by every TerraFlow run — results.csv, manifest.json, and report.json schemas.
icon: material/file-check-outline
tags:
  - Architecture
  - Reference
  - Outputs
---

# Artifact Contract

Each run writes a consistent set of artifacts under:

```
outputs/<run_name>/
```

For example, `output_dir: "outputs/demo_run"` yields `outputs/demo_run/results.csv`.

## Required outputs

| File | Purpose |
| --- | --- |
| `results.csv` | Tabular features and scores generated per sampled cell. |
| `manifest.json` | Run metadata including configuration and input fingerprints. |
| `report.json` | Summary statistics and model outputs for quick inspection. |

## Notes for v0.1

- Artifacts are **local-only**; there is no remote storage integration yet.
- The run directory is treated as immutable once written.
- Downstream tooling should rely on `manifest.json` for provenance.
