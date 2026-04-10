# TerraFlow

## What This Is

TerraFlow is an open-source Python library for reproducible, research-grade agricultural land suitability analysis using geospatial raster and climate data. It provides a configuration-driven pipeline that ingests GeoTIFF rasters and climate station data, runs spatial interpolation (IDW and kriging), scores suitability across a region, and produces deterministic, provenance-stamped output artifacts. TerraFlow targets anyone doing reproducible ag/land suitability work in Python — graduate researchers, government scientists, and open-source geospatial practitioners alike.

## Core Value

Every TerraFlow run produces a verifiable, reproducible result: same inputs always yield the same outputs, with full uncertainty quantification and provenance — making findings publishable and auditable.

## Requirements

### Validated

- ✓ Configuration-driven pipeline with Pydantic validation — existing
- ✓ GeoTIFF raster ingestion with ROI clipping and CRS reprojection — existing
- ✓ Climate interpolation: IDW spatial strategy and station index matching — existing
- ✓ Kriging interpolation with variogram fitting (PyKrige) — existing
- ✓ Suitability scoring with weighted multi-band model — existing
- ✓ Deterministic run fingerprinting and no-op rerun detection — existing
- ✓ Three-artifact output: features.parquet, manifest.json, report.json — existing
- ✓ CLI interface (`terraflow -c config.yml`) — existing
- ✓ Monte Carlo uncertainty propagation (score_ci_low / score_ci_high per cell) — existing
- ✓ 87%+ branch coverage test suite including MC/kriging edge cases — Validated in Phase 1: Foundation Hardening
- ✓ CRS validation: CRSMismatchError with informative messages — Validated in Phase 1: Foundation Hardening
- ✓ Kriging variogram diagnostics in report.json (nugget, sill, range_, model) — Validated in Phase 1: Foundation Hardening
- ✓ Optional plotly [viz] extra; trove classifiers and Documentation URL in pyproject.toml — Validated in Phase 1: Foundation Hardening

### Active

- ✓ Sensitivity analysis — Sobol' and Morris methods via SALib, CLI-invocable, sensitivity_report.json output — Validated in Phase 2: Sensitivity Analysis
- ✓ Model validation — spatial block CV, Cohen's kappa, Moran's I, CLI-invocable (`terraflow validate`), demo notebook — Validated in Phase 3: Model Validation
- ✓ Spatial statistics rigor — kriging LOOCV RMSE in report.json (`kriging_loocv`), Moran's I residual autocorrelation — Validated in Phase 3: Model Validation
- ✓ H3 index export — `terraflow.export.to_h3()` and `terraflow export --format h3` CLI subcommand; optional h3-py dep — Validated in Phase 4: H3 Export
- [ ] JOSS paper finalization — manuscript, figures, and supplementary materials meeting reviewer standards

### Out of Scope

- Real-time or streaming data ingestion — TerraFlow is a batch pipeline; streaming adds complexity without research value
- Web UI or dashboard — library-first; visualization is caller's responsibility
- Commercial ag operations tooling — out of scope; focus is research community
- Non-Python client SDKs — Python-first for v1

## Context

TerraFlow is a brownfield project with an active codebase (~3,600 lines of test code, 10 source modules). A JOSS paper submission is in progress (`paper/paper.md`, `paper/biblio.bib`). Stage 2 (Monte Carlo uncertainty) was recently merged. Key scientific concerns from prior triage:
- The suitability model uses hard-coded weight boundaries without statistical justification — needs sensitivity analysis
- Kriging results lack LOOCV diagnostics in output artifacts — reviewers will ask
- No validation against real-world ag outcomes exists yet
- CRS edge cases produce broad exception handlers instead of informative errors

The library is on branch `feat/stage2-mc-uncertainty`. Phase 1 (foundation hardening) and Phase 2 (sensitivity analysis) complete. Target JOSS submission window is ~2026-05-25.

## Constraints

- **Tech stack**: Python 3.10+, Pydantic v2, Rasterio, PyKrige, Typer — established; no major replacements
- **Reproducibility**: All pipeline changes must preserve or extend deterministic run identity
- **Authorship**: Commits must not include Claude co-author attribution
- **Scientific integrity**: Methods must be grounded in established literature — no black-box additions without citations
- **JOSS standards**: Software must be installable, documented, and testable by an independent reviewer

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Monte Carlo over analytical uncertainty | MC generalizes to any scoring function | — Pending (JOSS review) |
| H3 as export format (not primary grid) | Interop with DeckGL/H3 tools; don't replace pixel grid | — Pending |
| Sobol/Morris for sensitivity analysis | Established, citable methods for variance decomposition | — Pending |
| LOOCV for kriging validation | Standard geostatistical practice; expected by reviewers | — Pending |

---
*Last updated: 2026-04-04 — Phase 4 (H3 Export) complete*
