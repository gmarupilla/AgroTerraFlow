# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] — 2026-03-15

### Fixed
- Broadened Python support floor from 3.13 to **3.10** (`requires-python`, mypy target, CI matrix now tests 3.10/3.11/3.12).
- `rasterio.CRS` has no `.equals()` method — replaced with `==` / `!=` in `geo.py` and `pipeline.py`.
- Docker build: added missing `curl` to apt deps; fixed `uv` install path (`UV_INSTALL_DIR=/usr/local/bin`); copied `data/` and `scripts/` into image; generate synthetic demo raster at build time so container runs end-to-end with no external data.

### Added
- `CITATION.cff` with both authors and ORCIDs for Zenodo/GitHub citation support.
- Deterministic run fingerprinting: `core/run_identity` module (`compute_run_fingerprint`, `hash_roi_geometry`, `fingerprint_file`).
- Shapely dependency for geometry normalisation in ROI hashing.
- Run identity tests and documentation.
- `[tool.ruff]` configuration in `pyproject.toml`; notebooks and scripts excluded from linting.
- `.dockerignore` to keep build context lean.
- CI `docker-e2e` job: builds image, runs demo pipeline, verifies `features.parquet`, `manifest.json`, `report.json`.
- Demo notebook converted from broken marimo iframe to a 30-cell Jupyter `.ipynb` rendered via `mkdocs-jupyter`.

### Changed
- README: corrected test count (127), Python badge (3.10+), CLI invocation (`terraflow --config`, not `terraflow run --config`).
- Demo raster (`data/usda_cdl.tif`) removed from git; now downloaded from USDA CropScape or generated synthetically via `make get-demo-data`.
- Removed `fly.toml` (unrelated web deployment config) and aspirational `docs/joss-readiness.md` / `docs/ard-readiness.md`.
- `.gitignore`: added `.vscode/`, `.claude/`, `.cursor/`, `.aider*`, `__marimo__/`, `test_outputs/`.

## [0.2.0] — 2026-02-24

### Added
- `DataCatalog` abstraction in `ingest`: collects CRS, bounds, nodata, dtype, shape, and SHA-256 fingerprint for each input layer without performing pixel reads.
- Schema-versioned output artifacts: `features.parquet` (v1), `manifest.json`, `report.json` written atomically under `<output_dir>/runs/<fingerprint>/`.
- `features.parquet` schema contract enforced in tests: columns `run_id`, `cell_id`, `lat`, `lon`, `v_index`, `mean_temp`, `total_rain`, `score`, `label` with stable dtypes.
- `manifest.json` records config snapshot, input fingerprints, `DataCatalog` metadata, code version, git SHA, and UTC timestamp.
- `report.json` records per-layer coverage fraction, nodata cell counts, raster and climate statistics, and per-step wall-clock timings.
- `stats` module: `RasterSummary`, `ClimateSummary`, `RunReport` Pydantic models; `summarize_raster`, `compare_rasters`, `batch_summarize` functions.
- End-to-end smoke tests using fully synthetic rasters and climate data (no external data dependency).
- Artifact contract tests covering column presence, dtype stability, label cardinality, and `run_id` linkage across artifacts.
- Architecture Decision Records: ADR-001 (band selection), ADR-002 (bbox ROI), ADR-003 (climate interpolation), ADR-004 (CRS reprojection).
- MkDocs documentation site with Material theme, deployed to GitHub Pages.
- `docs/architecture/artifacts.md` and `docs/architecture/run-identity.md` documenting output contracts.

### Changed
- `pipeline` refactored to use `DataCatalog` for metadata collection, separating ingest metadata from orchestration.
- Atomic artifact writes: each file is written to a temp path and renamed on success to prevent partial outputs.
- CRS enforcement: output cell coordinates are always WGS84 geographic degrees regardless of input raster projection.
- Pydantic v2 throughout: `PipelineConfig`, `ModelParams`, `ROI`, all stats models.

## [0.1.2] — 2025-11-29

### Fixed
- CI workflow: refined virtualenv setup, linting targets, and dependency installation steps.
- PyPI publish action updated to latest release; metadata verification disabled for initial publish.

## [0.1.1] — 2025-11-29

### Fixed
- CI workflow and Makefile: separated linting and testing steps; corrected `src` vs `terraflow` target paths.
- Removed deprecated `create_raster.py` script.

## [0.1.0] — 2025-11-25

### Added
- Initial release of TerraFlow.
- Config-driven pipeline: YAML configuration loaded and validated with Pydantic.
- Raster ingestion via `rasterio`: single-band GeoTIFF loading with nodata masking.
- ROI clipping: bounding-box windowed reads with CRS reprojection via `pyproj`.
- Climate CSV loading via `pandas`: tabular temperature and rainfall observations.
- Spatial interpolation of climate observations to raster cell centroids (`scipy.interpolate.griddata`) with nearest-neighbour fallback.
- Parametric suitability model: normalised weighted composite of vegetation index, mean temperature, and total rainfall.
- `results.csv` output with per-cell scores and categorical labels.
- CLI entry point: `terraflow -c config.yml`.
- GitHub Actions CI: lint (ruff + black) and test on push and pull request.
- Automated PyPI publishing on version tags.
- MIT License.
