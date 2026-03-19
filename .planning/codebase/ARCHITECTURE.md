# Architecture

**Analysis Date:** 2026-03-18

## Pattern Overview

**Overall:** Modular pipeline with layered data flow

**Key Characteristics:**
- Deterministic, reproducible workflow with content-addressed run identity
- Strict separation between ingest (metadata), computation, and I/O layers
- Configuration-driven with Pydantic validation
- Atomic writes and caching to detect and skip identical runs
- Spatial data focus: raster clipping, coordinate transformation, interpolation

## Layers

**CLI Layer:**
- Purpose: Command-line interface and entry point
- Location: `terraflow/cli.py`
- Contains: Argument parsing, error handling, user-facing messages
- Depends on: `pipeline.run_pipeline`, `utils.logger`
- Used by: External users; invoked via `terraflow -c config.yml`

**Pipeline Orchestration Layer:**
- Purpose: Coordinate all steps in the end-to-end workflow
- Location: `terraflow/pipeline.py`
- Contains: `run_pipeline()` function (747 lines), atomic I/O, run identity computation, step sequencing
- Depends on: All other modules (ingest, geo, climate, model, stats, config, core.run_identity)
- Used by: CLI; testing harness
- Key responsibilities:
  - Load and validate configuration
  - Compute deterministic run fingerprint (via `core.run_identity`)
  - Detect and return cached results if identical run already executed
  - Orchestrate data catalog build, raster clip, climate interpolation, feature computation
  - Atomically write three artifacts: `features.parquet`, `manifest.json`, `report.json`

**Configuration Layer:**
- Purpose: Define, validate, and load configuration contracts
- Location: `terraflow/config.py`
- Contains: Pydantic models for `ModelParams`, `ClimateConfig`, `PipelineConfig`
- Depends on: PyYAML, Pydantic validators
- Used by: Pipeline, tests

**Data Ingest Layer:**
- Purpose: Resolve input files, validate availability, collect metadata without reading pixel data
- Location: `terraflow/ingest.py`
- Contains: `DataCatalog`, `RasterLayer`, `ClimateLayer` models; `load_raster()`, `load_climate_csv()`, `build_data_catalog()`
- Depends on: Rasterio, Pandas, Pydantic
- Used by: Pipeline orchestrator
- Boundary: This layer MUST NOT orchestrate pipeline steps or write final features—it only resolves datasets and collects provenance metadata (SHA256 fingerprints, bounds, CRS, dtype)

**Geospatial Operations Layer:**
- Purpose: Handle spatial operations (clipping, CRS transformation)
- Location: `terraflow/geo.py`
- Contains: `clip_raster_to_roi()` function with automatic CRS reprojection
- Depends on: Rasterio, PyProj
- Used by: Pipeline (clipping step), stats (summary computation)

**Climate Interpolation Layer:**
- Purpose: Match climate station data to raster cells using multiple strategies
- Location: `terraflow/climate.py`
- Contains: `ClimateInterpolator` class with three interpolation methods (linear, kriging, IDW)
- Depends on: SciPy (griddata), PyKrige, Pandas, Pydantic
- Used by: Pipeline (per-cell climate values)
- Key features:
  - **Linear** (default): Fast Delaunay-based interpolation, no uncertainty
  - **Kriging**: Geostatistically optimal with automatic variogram selection; returns per-cell standard deviations
  - **IDW**: Inverse Distance Weighting; no uncertainty
  - Fallback strategy when kriging has insufficient stations
  - Cross-validation metrics computed at initialization (kriging only)

**Model/Scoring Layer:**
- Purpose: Compute suitability scores from normalized inputs
- Location: `terraflow/model.py`
- Contains: `suitability_score()` (scalar), `suitability_score_array()` (vectorized), `suitability_label()` (categorical)
- Depends on: NumPy (for vectorized version), `config.ModelParams`
- Used by: Pipeline (per-cell scoring)
- Scope: Pure computation; no I/O or side effects

**Statistics & Reporting Layer:**
- Purpose: Generate summaries of raster data, climate inputs, and pipeline runs
- Location: `terraflow/stats.py`
- Contains: `RasterSummary`, `ClimateSummary`, `RunReport` models; functions like `summarize_raster()`, `compare_rasters()`
- Depends on: Rasterio, Pandas, Pydantic
- Used by: Pipeline (for QA summaries in report.json), external analysis code

**Run Identity Layer:**
- Purpose: Compute deterministic fingerprints for reproducibility and caching
- Location: `terraflow/core/run_identity.py`
- Contains: `compute_run_fingerprint()`, `canonicalize_config()`, `fingerprint_file()`, ROI geometry hashing
- Depends on: Shapely, standard library hashlib/json
- Used by: Pipeline orchestrator
- Key contract: Given same inputs (config, ROI, input file contents), produces identical fingerprint

**Visualization Layer:**
- Purpose: Create interactive maps of results
- Location: `terraflow/viz.py`
- Contains: `plot_suitability_scatter()` using Plotly
- Depends on: Plotly, Pandas
- Used by: Notebooks, external analysis

**Utilities Layer:**
- Purpose: Shared helpers for logging, path management, normalization
- Location: `terraflow/utils.py`
- Contains: `logger`, `ensure_dir()`, `normalize()`
- Depends on: Python standard library
- Used by: All modules

## Data Flow

**End-to-end pipeline execution:**

1. **Configuration Loading** (`cli.py` → `pipeline.py`)
   - CLI reads YAML config file path
   - `run_pipeline()` parses YAML, validates via `PipelineConfig` (Pydantic)
   - Relative paths resolved against config file directory

2. **Run Identity** (`pipeline.py` → `core.run_identity.py`)
   - Canonicalize config dict to JSON (deterministic key order)
   - Hash ROI geometry (bbox or GeoJSON file)
   - Collect all input file paths (glob expansion if needed)
   - Compute SHA256 fingerprints of all input files
   - `compute_run_fingerprint()` = hash(config, roi_geometry, input_fingerprints)
   - Determines output directory: `output_dir/runs/<run_fingerprint>/`

3. **Cache Detection** (`pipeline.py`)
   - Check if `features.parquet`, `manifest.json`, `report.json` all exist in run directory
   - If yes: load parquet, set `df.attrs["run_fingerprint"]`, return (no recomputation)
   - If no: proceed to full pipeline

4. **Data Catalog Build** (`pipeline.py` → `ingest.py`)
   - `build_data_catalog()` resolves raster and climate file paths
   - Opens each raster with Rasterio (metadata only, no pixel read)
   - Collects: CRS, bounds, dtype, shape, nodata value, SHA256
   - Loads climate CSV, validates coordinates, collects variable list
   - Returns immutable `DataCatalog` object

5. **Data Load** (`pipeline.py` → `ingest.py`)
   - `load_raster()` opens raster file for band 1
   - `load_climate_csv()` loads climate stations DataFrame

6. **Raster Clipping** (`pipeline.py` → `geo.py`)
   - `clip_raster_to_roi()` clips raster to ROI bounds
   - If ROI CRS differs from raster CRS: reproject ROI, compute intersection
   - Returns: masked array (band 1) + Affine transform
   - Compute coverage metrics: total cells, valid cells, nodata cells

7. **Climate Interpolation** (`pipeline.py` → `climate.py`)
   - Initialize `ClimateInterpolator` with parsed climate DataFrame
   - For each valid raster cell (latitude, longitude):
     - If strategy="spatial": interpolate using configured method (linear/kriging/IDW)
     - If strategy="index": look up station by cell_id_column
   - Kriging: compute LOOCV metrics at initialization
   - Returns: DataFrame with mean_temp, total_rain (+ uncertainty if kriging)

8. **Feature Computation** (`pipeline.py` → `model.py`, `utils.py`)
   - For each valid cell:
     - Normalize vegetation index, temperature, rainfall using ModelParams bounds
     - Compute suitability score = w_v·v_norm + w_t·t_norm + w_r·r_norm
     - Convert score to label (low/medium/high) via thresholds
   - Vectorized via `suitability_score_array()` for efficiency
   - Per-cell uncertainty (if kriging + uncertainty_samples > 0):
     - Monte Carlo sampling: draw from Normal(value, std) for temp/rain
     - Compute confidence interval on score

9. **Results Assembly** (`pipeline.py`)
   - Build DataFrame with columns: run_id, cell_id, lat, lon, v_index, mean_temp, total_rain, score, label
   - Schema version in Parquet metadata
   - Optional: uncertainty columns (score_ci_low, score_ci_high)

10. **Artifact Output** (`pipeline.py`)
    - **Atomic writes** (write-to-temp, atomic rename):
      - `features.parquet`: Per-cell results with schema metadata
      - `manifest.json`: Config snapshot, run identity, input provenance
      - `report.json`: QA summaries (raster stats, climate stats, coverage metrics, step timings)
      - `results.csv` (legacy backward-compat): Same data as parquet

**State Management:**
- Configuration is immutable after loading (Pydantic models are frozen by default)
- Run fingerprints are deterministic given inputs → same inputs = same output directory = cache hit
- No global mutable state; all state passed as function arguments or returned from functions

## Key Abstractions

**PipelineConfig:**
- Purpose: Validates and holds pipeline configuration with all required/optional parameters
- Examples: `terraflow/config.py` classes `ModelParams`, `ClimateConfig`, `PipelineConfig`
- Pattern: Pydantic BaseModel with field validators and type coercion

**DataCatalog:**
- Purpose: Immutable metadata snapshot (no pixel data)
- Examples: `terraflow/ingest.py`; models `RasterLayer`, `ClimateLayer`, `DataCatalog`
- Pattern: Pydantic-based provenance objects for serialization to manifest.json

**ClimateInterpolator:**
- Purpose: Encapsulate climate matching logic and pre-computed LOOCV metrics
- Pattern: Initialized once per pipeline run; stateless interpolation methods
- Examples: `terraflow/climate.py`; supports linear, kriging, IDW strategies

**RasterSummary, ClimateSummary, RunReport:**
- Purpose: Serializable summary objects for QA/reporting
- Pattern: Pydantic BaseModel with optional fields; safe JSON round-trip
- Used in: `report.json`, test assertions

## Entry Points

**CLI Entry Point:**
- Location: `terraflow/cli.py:main()`
- Triggers: User runs `terraflow -c config.yml`
- Responsibilities:
  - Parse command-line arguments
  - Validate config file exists
  - Call `run_pipeline(config_path)`
  - Catch and log errors
  - Exit with appropriate status codes

**Library Entry Point:**
- Location: `terraflow/pipeline.py:run_pipeline(config_path)`
- Triggers: Imported by external Python code or tests
- Responsibilities: Execute full pipeline, return results DataFrame
- Contract: Atomic writes; cached results on rerun

**Test Entry Points:**
- Fixtures in `tests/conftest.py` create synthetic rasters and climate CSVs
- Test functions exercise individual layers (ingest, geo, model, climate) and full pipeline

## Error Handling

**Strategy:** Fail fast with clear messages; log detailed context

**Patterns:**

- **Configuration errors** (ValueError): Logged before exit; reported to stderr
  - Examples: Missing/invalid ROI, mismatched CRS, invalid bounds
  - Handler: `cli.py` catches ValueError, prints to stderr, exits(1)

- **File not found** (FileNotFoundError): Logged before exit
  - Examples: Config file, raster file, climate CSV
  - Handler: `cli.py` catches FileNotFoundError, prints to stderr, exits(1)

- **Data validation errors** (Pydantic ValidationError): Caught during config loading
  - Examples: Type mismatches, out-of-range values
  - Handler: Config build raises ValueError with details

- **Empty ROI** (ValueError): Raised if no valid raster cells in clipped region
  - Handler: Pipeline catches, logs error message, re-raises

- **Interpolation fallback** (warning): Kriging downgraded to linear if < 5 stations
  - Handler: Logger.warning in climate.py; continues with fallback method

**Logging:**
- All major steps logged at INFO level via `terraflow.logger` (configured in `utils.py`)
- Errors logged at ERROR level with traceback (exc_info=True)

## Cross-Cutting Concerns

**Logging:**
- Module: `terraflow/utils.py:logger`
- Pattern: Centralized logger named "terraflow" with INFO level default
- Applied: Imported in every module; major steps logged in pipeline, geo, climate, ingest

**Validation:**
- Framework: Pydantic v2
- Applied: Config validation in `config.py` (ModelParams, PipelineConfig); coordinate validation in `climate.py` (CoordinateRange)
- Behavior: Automatic type coercion and field validation; raises ValidationError on failure

**Authentication/Authorization:**
- Not applicable (local file-based processing; no external APIs or auth)

**Coordinate Systems:**
- Convention: Latitudes and longitudes always written in WGS84 (EPSG:4326) in output
- Rasters may use any CRS; automatically reprojected via PyProj when clipping to ROI
- Climate stations always matched in geographic degrees (EPSG:4326)

**Determinism:**
- Run fingerprints are content-addressed (config + ROI geometry + input file contents)
- Config canonicalized to JSON with sorted keys before hashing
- Same inputs guarantee identical output location and cached results on rerun

---

*Architecture analysis: 2026-03-18*
