# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **H3-indexed export** (`terraflow export --format h3 -c config.yml`): re-indexes suitability results by H3 hexagonal cell for interop with DeckGL, Kepler.gl, and h3pandas. Output written to `h3_resolution_N.parquet` in the run directory. New `to_h3()` function in `terraflow.export` and `run_export()` orchestrator. Optional `[h3]` extra: `pip install terraflow-agro[h3]`.
- `ExportConfig` Pydantic model with `h3_resolution` field (validated 0–15) in `terraflow.config`.
- `export` CLI subcommand with `--format` (required), `--config`/`-c`, and optional `--resolution`/`-r` override.
- Notebook `04_h3_export.ipynb` demonstrating H3 export with synthetic data.
- **Sensitivity analysis** (`terraflow sensitivity -c config.yml`): Sobol' first-order / total-order indices and Morris elementary effects for all `ModelParams` weights via SALib. Results written to `sensitivity_report.json` in the run directory. New `sensitivity:` config block; `SensitivityConfig` in `terraflow.config`.
- **Model validation** (`terraflow validate -c config.yml`): spatial block cross-validation (Roberts et al. 2017), Cohen's kappa against an optional reference CSV, and Moran's I on score residuals. Results appended to `report.json` under `"validation"` key. New `validation:` config block; `ValidationConfig` in `terraflow.config`.
- `terraflow/sensitivity.py` — `run_sensitivity()` public API.
- `terraflow/validation.py` — `run_validation()`, `_spatial_block_cv()`, `_morans_i()`, `_compute_kappa()` public/internal API.
- `pipeline.resolve_run_dir(config_path)` — deterministic run-directory lookup without re-running the pipeline.
- `scikit-learn>=1.0` runtime dependency (BSD-3-Clause); used for `cohen_kappa_score` and `GroupKFold`.
- `SALib>=1.5` runtime dependency (MIT); used for Sobol' and Morris sampling/analysis.
- Notebooks: `02_sensitivity_analysis.ipynb`, `03_model_validation.ipynb` (also rendered in docs).
- **CRS error handling**: `CRSMismatchError` raised with both CRS strings when raster and ROI CRS disagree.
- **Variogram diagnostics block** in `report.json` (`kriging_diagnostics`) when kriging is used: model name, psill, nugget, sill, range, range units.
- **Kriging LOOCV RMSE** in `report.json` (`kriging_loocv`) per climate variable when kriging is configured.
- **Monte Carlo uncertainty coverage** in `report.json` when `uncertainty_samples` is set.
- `plotly` moved to optional `[viz]` extra (`pip install terraflow-agro[viz]`).

- **Ordinary Kriging interpolation** (`interpolation_method: "kriging"` in climate
  config): uses `pykrige.ok.OrdinaryKriging` with automatic variogram model selection
  (spherical / exponential / Gaussian) via Leave-One-Out Cross-Validation.  Requires
  ≥ 5 stations; falls back to `"linear"` with a warning for sparse networks.
- **Per-cell kriging uncertainty**: `features.parquet` gains `{var}_krig_std` columns
  (kriging prediction standard deviation) when `interpolation_method: "kriging"`.
- **Interpolation cross-validation**: `report.json` gains an `interpolation_cv` section
  with LOOCV RMSE and MAE per climate variable when kriging is configured.
- **IDW interpolation** (`interpolation_method: "idw"`): inverse distance weighting
  (power=2) as a lightweight no-dependency spatial alternative.
- `climate.interpolation_method` config field (choices: `linear` [default],
  `kriging`, `idw`); existing configs without the field default to `"linear"`.
- `pykrige>=1.7` runtime dependency (BSD-3-Clause).
- ADR-005 documenting the kriging design decision.
- Determinism regression test suite (`tests/test_determinism.py`): four tests covering
  seeded cell-set stability, score stability, fingerprint presence, and fingerprint
  stability across independent runs.
- `synthetic_climate_csv_dense` pytest fixture (8 stations) for kriging tests.
- **Homebrew tap**: `brew tap gmarupilla/terraflow && brew install terraflow` for macOS — handles GDAL and PROJ system-library installation automatically. Formula at `packaging/homebrew/Formula/terraflow.rb`.
- `publish-homebrew.yml`: auto-updates `gmarupilla/homebrew-terraflow` formula (url + sha256) on every `v*.*.*` tag push. ADR-006 documents the tap-vs-Core decision.

### Fixed
- **Reproducibility**: cell sampling in `run_pipeline` now uses a
  `numpy.random.default_rng` seeded from the SHA-256 of the run fingerprint.
  Identical inputs always produce the same cell set, closing the known limitation
  acknowledged in v0.2.1.

### Changed
- `ClimateInterpolator.__init__` accepts a new `interpolation_method` keyword argument
  (default `"linear"`, fully backward compatible).
- `paper/paper.md` reproducibility section updated: removed the "known limitation"
  paragraph, added seeded-sampling bullet; "Future Work" seeded-sampling bullet removed.

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
