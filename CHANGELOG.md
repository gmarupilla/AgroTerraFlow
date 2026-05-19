# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Optional `[geoai]` extra (`pip install terraflow-agro[geoai]`) bringing in `geoai-py` and `torch` for the upcoming `terraflow geoai` subcommand (#91, epic #90).
- `GeoAIConfig` Pydantic block accepted under `geoai:` in pipeline configs, with validation for engine name (`fields`/`landcover`/`canopy`), power-of-two `chip_size` (≥ 32), `confidence_threshold` in [0, 1], and positive `batch_size`.
- Internal `terraflow.core.run_identity.compute_geoai_fingerprint()` for deterministic GeoAI-run identity. Hashes config, inputs (`{sha256, size_bytes}` shape now enforced), and `name`/`weights_sha256`/`geoai_major_minor`; optionally also `device` and `torch_major_minor`.
- `terraflow.geoai_engine` module with `run_fields()`, `run_landcover()`, `run_canopy()` orchestrators (#92). Validates `config.geoai.engine`, fingerprints inputs + device/torch, writes artifacts to `<output_dir>/runs/<geoai_fingerprint>/geoai/`, emits `geoai_manifest.json` and `report.json`, seeds `torch.manual_seed` from the fingerprint, and skips inference on cache hits. Engine bodies are placeholders that land in #94.

## [0.3.0] — 2026-04-23

### Added
- `climate.variogram_mode` config for kriging. The default `standard` mode keeps the existing spherical/exponential/Gaussian candidate set; `extended` mode also evaluates nested variogram candidates and records LOOCV candidate scores in `report.json`.
- Notebook `05_extended_variogram_mode.ipynb` demonstrating extended kriging variogram selection with synthetic station data.
- `raster_band` top-level config field (default `1`): selects the 1-based rasterio band for multi-band inputs (CDL stacks, Sentinel rasters) so users no longer need to pre-extract bands (#42). Out-of-range values raise `ValueError` at pipeline start-up; the selected band is captured in `manifest.json` via the config snapshot.
- `report.json` now includes an `interpolation_fallback` block with per-variable fallback-to-mean counts (`fallback_cells_by_variable`) plus the aggregate total, whenever `fallback_to_mean` is enabled (#38). A WARNING is logged for any variable whose fallback ratio exceeds 10 % of sampled cells, flagging poor spatial coverage before users read the report.
- `docs/reproducibility.md`: consolidated documentation of what the run fingerprint covers, what it excludes, known sources of non-determinism (pykrige variogram fit across scipy versions, qhull triangulation tie-breaking, BLAS-dependent summation order), cache-invalidation behaviour, and a reviewer-oriented citation and verification checklist (#46). Linked from the README and the MkDocs nav.
- `paper/biblio.bib`: added `herman2017salib` (SALib JOSS paper, doi:10.21105/joss.00097), `saltelli2008global` (Global Sensitivity Analysis: The Primer), and `cressie1993spatial` (Statistics for Spatial Data) BibTeX entries (#65). Cited in `paper/paper.md` alongside descriptions of the Ordinary Kriging climate path and the Sobol'/Morris sensitivity and spatial-validation analyses.
- `make docker-smoke` target that builds the Docker image and runs the demo pipeline with `--network none`, asserting `features.parquet`, `manifest.json`, and `report.json` land under the mounted output directory (#67). Added as a dedicated `docker-smoke-offline` job in `.github/workflows/ci.yml` so every push verifies air-gapped reproducibility.
- `paper/paper.md` rewritten to comply with the 2026 JOSS structural requirements: required sections now include Summary, Statement of Need, State of the Field, Software Design, Research Impact Statement, AI Usage Disclosure, Acknowledgements, and References (#66). The submission date is synced to the current v0.2.2 release, kriging and uncertainty quantification are described as shipped features rather than Future Work, and the JOSS-required AI usage disclosure is provided.
- `paper/paper.md` "Research impact statement" now includes a quantitative results table produced by a full end-to-end run on the bundled demo (`terraflow run`, `sensitivity`, `validate`): kriging LOOCV RMSE per climate variable, MC confidence-interval widths, Sobol' S1 / ST indices, spatial-block-CV accuracy, Cohen's κ, and Moran's I on residuals (#64). Numbers are reproducible with `make get-demo-data && terraflow run/sensitivity/validate -c examples/demo_config.yml`.

### Changed
- `examples/demo_config.yml` now uses kriging interpolation with 200-sample Monte-Carlo uncertainty propagation and samples 2 000 cells, so the demo exercises the uncertainty and sensitivity pipelines end-to-end and produces the metrics table in `paper.md` (#64).
- `data/demo_climate.csv` expanded from 5 clustered stations to 20 stations distributed across the full demo ROI, with a plausible west-to-east temperature and precipitation gradient.
- `scripts/make_demo_raster.py` now generates a 609×234 raster at 1 km pixels covering the full demo ROI (western Kansas, lon -101..-94, lat 38..40) in EPSG:5070. Previous version produced a 779×779 patch at 30 m pixels that spanned only ~23 km × 23 km in eastern Kansas — inconsistent with the configured ROI.

### Fixed
- `terraflow sensitivity` now resolves `output_dir` relative to the config file's parent directory, matching `terraflow run` (#64 discovery). Previously, a relative `output_dir` was evaluated against the caller's working directory, so `sensitivity_report.json` could land outside the project tree when invoked from the repo root with a config that used `output_dir: ../outputs/...`.

### Changed
- Removed decorative section-banner comments and self-evident inline comments throughout `pipeline.py`, `ingest.py`, `geo.py`, and `climate.py`; comments now appear only at genuinely complex logic.
- Refactored `run_pipeline()` into four extracted helpers (`_project_cells_to_wgs84`, `_score_cells`, `_apply_monte_carlo`, `_build_report`) reducing the function from 425 lines to ~130 lines of orchestration and cutting cognitive complexity below SonarQube thresholds.
- Moved `import math` inline call in `geo.py` to module-level import.

### Fixed
- ROI clipping now snaps requested bounds to an intersecting pixel window so very small ROIs avoid oversized raster reads.
- Closed resolved issues: H3-01 (#60), H3-02 (#61), H3-03 (#62), H3-04 (#63), and #40 (all implemented in prior phases).
- `ClimateInterpolator` now resolves duplicate station coordinates by averaging numeric values at initialisation instead of only warning (#43). This prevents the singular-covariance failure mode in Ordinary Kriging when input CSVs contain repeated lat/lon entries (common with aggregated NOAA summaries); resolution count is logged at INFO.
- Pipeline cache hits now verify the `terraflow_schema_version` embedded in `features.parquet` against the current `FEATURES_SCHEMA_VERSION` and re-run instead of silently returning stale artifacts when the version is mismatched or missing (#39). A WARNING log is emitted when invalidation occurs.

### Tests
- Added `TestMaxCellsBoundary` regression coverage in `tests/test_determinism.py` for `max_cells == n_valid_cells` and `max_cells > n_valid_cells`, pinning the seeded-sampling contract at the boundary (#37).

## [0.2.2] — 2026-04-12

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
