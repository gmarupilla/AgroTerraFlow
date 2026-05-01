---
title: Roadmap
description: TerraFlow phased roadmap to JOSS submission — completed phases, active phase, and v2 ideas.
icon: material/road-variant
tags:
  - Development
  - Reference
---

# TerraFlow Roadmap

This roadmap mirrors `.planning/ROADMAP.md` (the single source of truth for in-flight work). The work from here to JOSS submission is additive: close two reviewer-visible gaps in the foundation (CRS errors, kriging diagnostics), add three analytical modules (sensitivity, validation, H3 export) as post-pipeline adapters, then finalize the paper with quantitative results drawn from those modules.

JOSS submission target: **2026-05-25**.

## Phase Status

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation Hardening | mostly delivered in 0.2.x — 0.3.0 | Released | 2026-04-23 (v0.3.0) |
| 2. Sensitivity Analysis | 3/3 | Complete | 2026-03-28 |
| 3. Model Validation | 3/3 | Complete | 2026-03-31 |
| 4. H3 Export | 3/3 | Complete | 2026-04-04 |
| 5. Paper and JOSS Submission | in flight | Active | — |

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

## Phase 3 — Model Validation ✓

Spatial block cross-validation (Roberts et al. 2017), Cohen's kappa, and Moran's I on residuals. Invoked with `terraflow validate -c config.yml`. Results appended to `report.json` under the `validation` key.

## Phase 4 — H3 Export ✓

Optional H3-indexed output for interop with H3-native toolchains. `terraflow export --format h3 -c config.yml` writes `h3_resolution_N.parquet` to the run directory. `h3-py` is an optional dep installed via `pip install terraflow-agro[h3]`.

## Phase 5 — Paper and JOSS Submission (Active)

**Goal:** the paper contains quantitative results drawn from the prior phases, packaging meets JOSS reviewer requirements, and the repository passes an end-to-end smoke test without network access.

Active work:

- `paper/paper.md` reproducibility section — quantitative results table populated from a full demo run (v0.3.0).
- `paper/biblio.bib` — SALib (Herman & Usher 2017), Saltelli et al. (2008), Cressie (1993) entries with DOIs (v0.3.0).
- `make docker-smoke` — Docker pipeline runs with `--network none`, asserted in CI via `docker-smoke-offline` job (v0.3.0).
- Final pass on submission date and version string sync between `paper/paper.md` and the PyPI release.

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
