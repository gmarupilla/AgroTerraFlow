---
title: Roadmap
description: TerraFlow phased roadmap to JOSS submission — completed phases, active phase, and v2 ideas.
icon: material/road-variant
tags:
  - Development
  - Reference
---

# TerraFlow Roadmap

This roadmap tracks completed phases and current state. v0.5.0 (2026-06-30) refocused the surface on the climate-impact flagship: removed GeoAI + H3 wrappers, narrowed validation to spatial-block CV, and shipped scenario × hazard fan-out with CMIP6 NetCDF support. Package restructure into `terraflow.io.*` + `terraflow.climate.*` sub-packages is planned for v0.6.0 (issue #148).

JOSS pre-review submitted 2026-06-08, rejected 2026-06-24 on impact criteria. **Resubmission gated on adoption signal**, not code (see internal strategy repo).

## Phase Status

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation Hardening | delivered | Released | 2026-04-23 (v0.3.0) |
| 2. Sensitivity Analysis | 3/3 | Released | 2026-04-23 (v0.3.0) |
| 3. Model Validation | narrowed to spatial-block CV | Released | 2026-06-30 (v0.5.0) |
| 4. H3 Export | cut | Removed | 2026-06-30 (v0.5.0; PR #135) |
| 5. GeoAI Engine | cut | Removed | 2026-06-30 (v0.5.0; PR #134) |
| 6. Climate-impact assessment | shipped | Released | 2026-06-30 (v0.5.0; issue #138) |
| 7. JOSS Resubmission | pending adoption signal | Blocked | — |

## Phase 1 — Foundation Hardening

Close the CRS error and kriging diagnostic gaps that block JOSS reviewer acceptance.

**Delivered (v0.2.2 / v0.3.0):**

- `CRSMismatchError` raised with both CRS strings when raster and ROI CRS disagree.
- `kriging_diagnostics` block in `report.json` — model name, psill, nugget, sill, range, range units.
- `kriging_loocv` RMSE in `report.json` per kriged climate variable.
- `plotly` demoted to optional `[viz]` extra; trove classifiers + Documentation URL added to `pyproject.toml`.
- `interpolation_fallback` block in `report.json` with per-variable fallback-to-mean counts plus aggregate total (v0.3.0).
- Coverage floor maintained at 85 % branch coverage with kriging-fallback and Monte-Carlo edge-case tests.

## Phase 2 — Sensitivity Analysis ✓

Sobol' first-order / total-order indices and Morris elementary effects for `ModelParams` weights via SALib. Invoked with `terraflow sensitivity -c config.yml`. Results written to `sensitivity_report.json`.

## Phase 3 — Model Validation (narrowed in v0.5.0) ✓

Spatial-block cross-validation (Roberts et al. 2017) via `terraflow validate -c config.yml`; results appended to `report.json` under the `validation` key. Cohen's κ and Moran's I wrappers were removed in v0.5.0 (PR #142 / issue #136) — call `sklearn.metrics.cohen_kappa_score` and `esda.Moran` directly on `features.parquet`. See [Migration v0.4 → v0.5](migration-v0.4-to-v0.5.md).

## Phase 4 — H3 Export (cut) ✗

Removed in v0.5.0 (PR #135 / issue #135). The module was a thin `h3-py` + pandas wrapper; downstream users now call `h3-py` directly on `features.parquet` (five-line recipe in the migration guide).

## Phase 5 — GeoAI Engine (cut) ✗

Removed in v0.5.0 (PR #134 / issue #134). Engine bodies were `NotImplementedError` stubs and downstream citations went to `geoai-py`, not TerraFlow. A separate `terraflow-geoai` package is parked post-JOSS pending demand signal.

## Phase 6 — Climate-impact assessment ✓

Shipped in v0.5.0 (issue #138, PRs #144–#150). Multi-scenario climate driver (historical + CMIP6 SSP windows) × seven WMO/ETCCDI-aligned hazard indicators (annual mean, seasonal mean, growing-degree days, frost days, heat-stress days, precipitation percentiles, simplified Thornthwaite SPEI). Writes a sibling `climate_features.parquet` alongside `features.parquet`; the historical artifact contract is unchanged. See `examples/demo_config_climate_impact.yml` and notebook `docs/notebooks/07_climate_impact_crop_suitability.ipynb`.

## Phase 7 — JOSS Resubmission (blocked on adoption)

JOSS pre-review (#10686) rejected 2026-06-24 with the note: "If/when in the future this software is used more widely, please resubmit." The fix is calendar-time adoption work (university outreach, AGU Fall poster, blog posts, CGIAR / AgMIP contact), not code. Resubmission gate criteria and outreach planning live in the internal strategy repo (see `project_post_coding_adoption_plan` memory).

## v2 Ideas

These are not planned for v1 (not on the JOSS critical path) but are worth tracking:

- **Directional variograms** for spatial anisotropy detection (scikit-gstat).
- **Universal Kriging** with elevation covariates.
- **UTM-projected variograms** for high-latitude fits.
- **STAC / COG** ingestion for cloud-native rasters.
- **Polygon ROI** support (shapefile / GeoJSON).
- **Data-driven weight learning** from labeled training points.

## Out of Scope

| Feature | Reason |
|---|---|
| Web UI or dashboard | Library-first; visualization is the caller's responsibility. |
| Streaming / real-time ingestion | Batch pipeline; streaming adds complexity without research value. |
| Commercial ag operations tooling | Focus is the research community. |
| Non-Python client SDKs | Python-first for v1. |

## References

- [Architecture Overview](architecture/overview.md)
- [Configuration Schema](config/schema.md)
- [Reproducibility](reproducibility.md)
