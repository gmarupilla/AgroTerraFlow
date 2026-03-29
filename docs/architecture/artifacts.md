---
title: Output Artifact Contract
description: The guaranteed output files written by every TerraFlow run — features.parquet, manifest.json, and report.json schemas.
icon: material/file-check-outline
tags:
  - Architecture
  - Reference
  - Outputs
---

# Artifact Contract

Every pipeline run produces a deterministic, immutable set of output files
under a **run directory** named after the run fingerprint:

```
<output_dir>/runs/<run_fingerprint>/
├── features.parquet    # canonical tidy/wide feature table (schema v1)
├── results.csv         # backward-compatible CSV (same data as Parquet)
├── manifest.json       # config snapshot + input provenance
└── report.json         # QA summaries + coverage + timings
```

The `run_fingerprint` is a base64url-encoded SHA-256 derived exclusively from
content-addressable components (see [Run Identity](run-identity.md)).

---

## features.parquet

**Schema version:** `1` (stored in Parquet file-level metadata as
`terraflow_schema_version`).

**Format:** Tidy/wide — one row per sampled raster cell, one column per
feature.  This matches the output convention of `rasterstats`,
`geopandas.sjoin`, and standard GIS zonal-statistics pipelines.  Adding new
climate variables in future releases appends columns and remains
backward-compatible via nullable new columns.

**Always present:**

| Column | Type | Description |
|---|---|---|
| `run_id` | `string` | `run_fingerprint` — join key to `manifest.json` |
| `cell_id` | `int64` | 0-based sampled-cell index (stable within a run) |
| `lat` | `float64` | WGS84 latitude (degrees N) — always geographic |
| `lon` | `float64` | WGS84 longitude (degrees E) — always geographic |
| `v_index` | `float64` | Raster band-1 value (vegetation / crop index) |
| `mean_temp` | `float64` | Interpolated mean temperature (°C) |
| `total_rain` | `float64` | Interpolated total rainfall (mm) |
| `score` | `float64` | Composite suitability score in `[0.0, 1.0]` |
| `label` | `string` | Categorical label: `low` / `medium` / `high` |

**Present when `interpolation_method: kriging`:**

| Column | Type | Description |
|---|---|---|
| `mean_temp_krig_std` | `float64` | Kriging std dev for temperature at this cell |
| `total_rain_krig_std` | `float64` | Kriging std dev for rainfall at this cell |

**Present when `interpolation_method: kriging` and `uncertainty_samples > 0`:**

| Column | Type | Description |
|---|---|---|
| `score_ci_low` | `float64` | 5th-percentile score from Monte Carlo draws |
| `score_ci_high` | `float64` | 95th-percentile score from Monte Carlo draws |

**CRS guarantee:** `lat` and `lon` are always WGS84 geographic degrees
(EPSG:4326), regardless of the native CRS of the input raster.  The pipeline
reprojects cell centroids before writing.

**Reading the file:**

```python
import pandas as pd
df = pd.read_parquet("runs/<fingerprint>/features.parquet")
```

---

## manifest.json

**Schema version:** `1` (field `schema_version`).

Contains the full provenance record for a run.  Downstream tools should
treat `manifest.json` as the authoritative provenance source.

```json
{
  "schema_version": "1",
  "run_fingerprint": "<base64url-sha256>",
  "code_version": "0.2.0",
  "git_sha": "<optional>",
  "created_at_utc": "2026-02-22T12:00:00+00:00",
  "config": { "<full YAML config as parsed dict>" },
  "input_fingerprints": [
    {
      "path": "/absolute/path/to/input.tif",
      "sha256": "<64-hex-char>",
      "size_bytes": 12345,
      "mtime": 1700000000
    }
  ],
  "catalog": {
    "raster_layers": [ { "layer_name": "primary", "crs": "EPSG:4326", ... } ],
    "climate_layers": [ { "n_rows": 3, "variables": ["mean_temp", "total_rain"], ... } ]
  },
  "output_files": ["features.parquet", "results.csv", "manifest.json", "report.json"]
}
```

!!! note "mtime in input_fingerprints"
    `mtime` is recorded for human-readable provenance tracing but is
    **intentionally excluded** from the run fingerprint hash.  The fingerprint
    is content-based (SHA-256 + byte-size) so it remains stable across
    filesystem copies and CI re-checks.

---

## report.json

**Schema version:** `1` (field `schema_version`).

Contains QA summaries, per-layer coverage metrics, and step timings.

```json
{
  "schema_version": "1",
  "run_fingerprint": "<base64url-sha256>",
  "coverage": {
    "n_raster_cells_total": 25,
    "n_roi_valid_cells": 20,
    "n_roi_nodata_cells": 5,
    "roi_coverage_fraction": 0.8,
    "roi_nodata_fraction": 0.2
  },
  "raster_stats": {
    "count": 20, "mean": 12.0, "std": 7.5, "min": 0.0, "max": 24.0
  },
  "climate_stats": {
    "n_rows": 3,
    "variables": {
      "mean_temp": { "mean": 19.0, "min": 18.0, "max": 20.0, "n_nodata": 0 },
      "total_rain": { "mean": 120.0, "min": 100.0, "max": 140.0, "n_nodata": 0 }
    }
  },
  "n_cells_sampled": 10,
  "score_stats": { "mean": 0.52, "std": 0.15, "min": 0.3, "max": 0.75 },
  "timings_sec": {
    "build_catalog": 0.02,
    "load_inputs": 0.05,
    "clip_roi": 0.01,
    "interpolate_climate": 0.01,
    "score_cells": 0.005,
    "write_outputs": 0.03,
    "total": 0.125
  },
  // Present when interpolation_method="kriging":
  "interpolation_cv": {
    "mean_temp": { "rmse": 1.2, "mae": 0.9, "r2": 0.94, "variogram_model": "spherical" },
    "total_rain": { "rmse": 18.5, "mae": 14.1, "r2": 0.89, "variogram_model": "spherical" }
  },
  // Present when uncertainty_samples > 0:
  "uncertainty": {
    "n_samples": 500,
    "score_ci_low_mean": 0.41,
    "score_ci_high_mean": 0.63
  }
}
```

**Coverage invariant:** `roi_coverage_fraction + roi_nodata_fraction == 1.0`
(within floating-point tolerance).

---

## Rerun behaviour

If `runs/<run_fingerprint>/` already contains all three required artifacts
when a run is invoked with identical inputs, the pipeline detects the
identical run and returns the cached `features.parquet` **without re-scoring**
(no-op rerun).  The run directory is treated as immutable once written.

To force a fresh run with the same inputs, delete or rename the run directory.

---

## Failure modes

| Situation | Outcome |
|---|---|
| ROI entirely outside raster extent | `ValueError` — no valid cells found |
| Input file missing | `FileNotFoundError` with path |
| YAML config malformed | `ValueError` with parse error |
| ROI CRS not reprojectable | `pyproj.exceptions.CRSError` |
| No write permission to `output_dir` | `PermissionError` from OS |

All errors propagate with a descriptive message to `stderr` and exit code `1`
when invoked via the CLI.
