---
title: Architecture Overview
description: Module boundaries, data flow, and reproducibility model for TerraFlow's geospatial pipeline.
icon: material/sitemap
tags:
  - Architecture
  - Reference
---

# TerraFlow Architecture Overview

TerraFlow is a config-driven geospatial pipeline for agricultural suitability modeling. Given a raster (land-cover GeoTIFF) and a climate CSV, it produces scored, location-stamped cell features with full provenance tracking.

## Data Flow

```
YAML config → PipelineConfig (Pydantic v2)
                 ↓
DataCatalog  ← ingest.py (metadata only; no pixel reads)
                 ↓
run_fingerprint ← core/run_identity.py (SHA256 of config + inputs)
                 ↓
geo.py  → clip raster to ROI bbox; reproject to EPSG:4326
                 ↓
climate.py → ClimateInterpolator (linear | kriging | IDW)
                 ↓
model.py → suitability_score() + suitability_label()
                 ↓
pipeline.py → write features.parquet, manifest.json, report.json
                 ↓
climate_impact.py → (auto-invoked when temporal_aggregations + scenarios)
                    temporal.py × hazard.py → kriging to cells
                 ↓
pipeline.py → write climate_features.parquet to same run directory
```

## Module Map

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Typer CLI — `run`, `sensitivity`, `validate` subcommands |
| `config.py` | Pydantic v2 models — `PipelineConfig`, `ModelParams`, `ROI`, `ClimateConfig` (`temporal_aggregations`, `scenarios`, `timeseries_csv`), `TemporalAggregation`, `Scenario`, `SensitivityConfig`, `ValidationConfig` |
| `ingest.py` | `RasterLayer`, `ClimateLayer`, `DataCatalog` — metadata only, no pixel I/O |
| `geo.py` | ROI clipping, CRS reprojection; invariant: all output in EPSG:4326 |
| `climate.py` | `ClimateInterpolator` — linear / kriging / IDW; LOOCV variogram selection |
| `climate_impact.py` | `run_climate_impact_features` — auto-invoked from `pipeline.run_pipeline` when `temporal_aggregations` + `scenarios` are set; writes `climate_features.parquet` |
| `temporal.py` | Multi-temporal aggregation engine — outer-product over rules × scenarios |
| `hazard.py` | WMO/ETCCDI-aligned indicators — `growing_degree_days`, `frost_days`, `heat_stress_days`, simplified Thornthwaite `spei` |
| `cmip6.py` | CMIP6 NetCDF ingest behind `[cmip6]` optional extra — handles non-Gregorian calendars |
| `model.py` | `suitability_score()`, `suitability_label()`, `suitability_score_array()` |
| `pipeline.py` | Orchestration — fingerprint → load → clip → interpolate → score → write; auto-invokes `climate_impact` when configured |
| `sensitivity.py` | Sobol' / Morris via SALib — triggered by `terraflow sensitivity` |
| `validation.py` | Spatial-block CV only (Cohen's κ + Moran's I removed in v0.5.0) — triggered by `terraflow validate` |
| `core/run_identity.py` | Deterministic SHA256 fingerprint of canonicalized config + input files |

## Output Artifacts

All artifacts land under `<output_dir>/runs/<run_fingerprint>/`:

| File | Schema | Contents |
|------|--------|----------|
| `features.parquet` | v1 | `run_id, cell_id, lat, lon, v_index, mean_temp, total_rain, score, label` (+ kriging std + CI columns when configured) |
| `climate_features.parquet` | v1 | (v0.5.0) Cell-indexed; one column per `<rule>__<scenario>` pair. Only written when `temporal_aggregations` + `scenarios` are set. Merge with `features.parquet` on `cell_id`. |
| `manifest.json` | v1 | Config snapshot, input fingerprints (raster + climate CSV + `timeseries_csv` when set), code version, git SHA |
| `report.json` | v1 | Coverage fractions, raster/climate stats, score stats, timings; `kriging_loocv`, `kriging_diagnostics`, `uncertainty`, and `validation` blocks appended when the relevant features are enabled |
| `results.csv` | — | Same data as `features.parquet` in CSV format (backward compatibility) |
| `sensitivity_report.json` | — | Sobol' and/or Morris indices per `ModelParams` weight (written by `terraflow sensitivity`) |

## Key Invariants

- **CRS:** always EPSG:4326 in output. `geo.py` reprojects any input that differs.
- **Determinism:** identical inputs always produce the same `run_fingerprint`. Cell sampling is seeded from the fingerprint SHA256 so that the same config yields the same cell set across independent runs.
- **Cache:** if all three required artifacts exist in the run directory, the pipeline returns immediately without re-running.
- **Coverage:** runs fail if no valid raster cells are found in the ROI; coverage fractions are always reported in `report.json`.
- **Atomicity:** all artifacts are written with a write-to-temp + rename pattern to prevent partial writes.

## Reproducibility Model

The `run_fingerprint` is a SHA256 over:
1. Canonicalized (key-sorted) YAML config
2. A stable ROI geometry hash (bbox dict or GeoJSON file hash)
3. SHA256 fingerprints of all input files (raster + climate CSV + `timeseries_csv` when set for the climate-impact path)

This makes each run directory immutable. Re-running with identical inputs is a no-op; changing any input or config parameter produces a new directory.

## Geospatial Correctness

- ROI bounds in any CRS are reprojected to raster CRS before windowing (all four corners, then axis-aligned bounding box to handle non-linear projections).
- Degenerate windows (NaN dimensions after reprojection) raise `ValueError` with diagnostic information.
- NoData cells are masked and excluded from sampling; coverage fractions are reported.
- Climate station coordinates are validated against `[-90, 90]` / `[-180, 180]` ranges at load time.

## Non-goals

- Remote dataset downloads or cloud-hosted rasters.
- Real-time or streaming data ingestion.
- GUI or web application layer.
- General-purpose raster processing (use `rioxarray` or `rasterstats` instead).
