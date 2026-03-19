# Codebase Concerns

**Analysis Date:** 2026-03-18

## Scientific & Methodological Flaws

### Climate Interpolation Lacks Uncertainty Quantification
- **Issue:** Default `scipy.interpolate.griddata` linear interpolation provides no uncertainty estimates
- **Files:** `terraflow/climate.py` (lines 1-100), `terraflow/config.py` (ClimateConfig)
- **Impact:** Every downstream suitability score is built on interpolated climate values with unquantified error. Users cannot distinguish confident high suitability from uncertain medium suitability. JOSS reviewers will flag this as a critical flaw for a reproducibility-focused tool.
- **Current Mitigation:** Kriging support added (Stage 1 completed via memory notes), produces `{var}_krig_std` columns when `interpolation_method="kriging"` is configured, but default remains linear without uncertainty.
- **Fallback Gap:** Linear method falls back to global mean outside convex hull of stations, not nearest neighbor — scientifically indefensible for sparse station networks.
- **Fix approach:** Kriging is already implemented (Stage 1). Recommend making kriging the default method for new projects; add validation that users explicitly choose linear if they accept no uncertainty quantification.

### Suitability Model Has No Scientific Foundation
- **Issue:** Linear weighted combination of 3 variables with arbitrary weights and label boundaries
- **Files:** `terraflow/model.py` (lines 7-47, 92-116), `terraflow/config.py` (ModelParams, lines 24-94)
- **Impact:** Weights (0.4, 0.3, 0.3 in demo) are invented, not derived from agronomy literature. Label boundaries (0.33, 0.66) lack statistical or agronomic basis. Model assumes independence of temperature and rainfall (spatially correlated in reality). No crop-type specificity (wheat, maize, soybean, cotton all different; model treats all identically). Linear responses are scientifically wrong (crops have threshold responses; frost kills, flooding kills).
- **Current Mitigation:** Config parameters allow customization of weights and bounds; Monte Carlo uncertainty propagation available (Stage 2, via memory notes) when kriging is used.
- **Fix approach:** Stage 3 (Global Sensitivity Analysis via SALib) would identify which parameters dominate output variance. Stage 4 (validation against FAO GAEZ or USDA NASS) is the most critical: benchmark against ground truth to demonstrate directional consistency with known agronomy.

### No Validation Against Ground Truth
- **Issue:** Suitability scores are never compared to actual crop data or reference classifications
- **Files:** Pipeline architecture (`terraflow/pipeline.py`) lacks validation pipeline stage
- **Impact:** Paper claims reproducibility but not utility. Without comparison to USDA NASS county crop yield data, FAO GAEZ suitability classes, or farmer survey data, TerraFlow cannot claim its scores correlate with actual crop success. A JOSS reviewer will ask: "What evidence exists that TerraFlow scores correlate with real-world crop outcomes?"
- **Current Mitigation:** None
- **Fix approach:** Stage 4 (Validation Against Reference Classification) — implement optional `validation` config section that joins TerraFlow scores to reference labels by spatial matching, computes confusion matrix / Cohen's κ / balanced accuracy, and reports in `report.json`. Even synthetic validation (e.g., deriving reference labels from FAO crop temperature/rainfall tables) would demonstrate the validation infrastructure and directional consistency.

## Tech Debt & Fragile Areas

### Broad Exception Handling in Geo Module
- **Issue:** `except Exception as e:` in `clip_raster_to_roi` (geo.py, line 88) catches all exceptions
- **Files:** `terraflow/geo.py` (line 88)
- **Impact:** Masks potential unintended exceptions; hard to debug when rasterio or pyproj raises unexpected errors. Reduces ability to distinguish user input errors (invalid ROI) from library bugs.
- **Safe modification:** Replace `except Exception` with specific exception types: catch `(rasterio.errors.WindowError, ValueError, TypeError)` from rasterio operations, let other exceptions propagate or wrap as `RuntimeError`.
- **Test coverage:** No tests specifically for degenerate projection scenarios that trigger this catch.

### Multiple Bare Exception Handlers in Pipeline
- **Issue:** `except Exception:` appears 5+ times in `pipeline.py`; some have context loss
- **Files:** `terraflow/pipeline.py` (lines at offsets 80-100+, based on grep results)
- **Impact:** Silent failures without diagnostic info; hard to debug failures in production runs. Risk of hiding data corruption or partial output.
- **Safe modification:** Add specific exception types and logging context; at minimum log exception chain with `logger.exception()`.
- **Priority:** Medium — existing error messages in config/ingest modules are well-scoped; pipeline.py is where aggregation happens.

### Hard-Coded Label Boundaries
- **Issue:** Suitability label thresholds (0.33, 0.66) are hard-coded in `suitability_label()` function
- **Files:** `terraflow/model.py` (lines 112-116)
- **Impact:** Users cannot customize label boundaries. If future stages add Bayesian or threshold-response models, hard-coded boundaries will prevent adoption without code modification.
- **Fix approach:** Move thresholds to config: add `model.label_boundaries: [0.33, 0.66]` to `ModelParams` or `PipelineConfig`; validate that boundaries are monotonically increasing; pass to `suitability_label()` function. Backward-compatible default to [0.33, 0.66].

## Performance Bottlenecks

### Potential Memory Issues with Large Rasters
- **Issue:** Pipeline currently loads entire clipped raster into memory via `raster.read(1, ...)` in `clip_raster_to_roi()`
- **Files:** `terraflow/geo.py` (line 108), `terraflow/pipeline.py` (sampling strategy)
- **Impact:** Rasters >2 GB may cause out-of-memory errors. ROADMAP (lines 130-140) acknowledges this as "Large Raster Optimization" but recommends window-based reads with stride instead of current approach.
- **Current Mitigation:** Documented in ROADMAP as v1.0 planned feature; not yet implemented.
- **Improvement path:** Implement windowed/strided processing: read raster in overlapping windows, process in batches, write to parquet incrementally. Requires refactor of `pipeline.run_pipeline()` and output schema.

### Kriging Variogram Selection LOOCV Cost
- **Issue:** Automatic variogram model selection (spherical, exponential, Gaussian) runs LOOCV on all 3 models at initialization
- **Files:** `terraflow/climate.py` (lines 321-350, `_init_kriging()`)
- **Impact:** For datasets with 100+ climate stations, 3× LOOCV iterations (~N² operations per model) can be slow (~10-60 seconds depending on N). No caching or async option for repeated runs with same climate data.
- **Current Mitigation:** Logs performance metrics; falls back to linear if all models fail.
- **Improvement path:** Cache best variogram model; add config option `interpolation.cache_variogram: true` to reuse model across runs.

## Fragile Areas

### Climate Data Column Validation
- **Issue:** Numeric climate columns are auto-detected from DataFrame without explicit config spec
- **Files:** `terraflow/climate.py` (lines 214-237, `_validate_columns()`), `terraflow/ingest.py`
- **Why fragile:** If CSV has extra numeric columns (e.g., ID, year), they are automatically included as climate variables. No config-level specification of *which* columns to use. Silently processes unintended variables.
- **Test coverage:** `test_climate.py` tests nominal case; no tests for spurious numeric columns.
- **Safe modification:** Add `climate.variables: [mean_temp, total_rain]` to config; validate that these columns exist and are numeric; only pass specified columns to interpolator. Backward-compatible via auto-detect if config key is absent.

### Raster CRS Handling Edge Cases
- **Issue:** Non-linear projections (e.g., UTM with convergence) are handled by reprojecting 4 corner points, but some pathological cases may produce degenerate windows
- **Files:** `terraflow/geo.py` (lines 64-105)
- **Impact:** Guard against `math.isnan(window.width)` added (line 99), but rasterio can still produce valid-looking windows that are numerically invalid after reprojection. No test coverage for:
  - Rasters in very high latitudes (polar stereographic)
  - ROI that straddles dateline in geographic coordinates
  - ROI in projected space, raster in geographic
- **Test coverage:** No regression tests for these edge cases.
- **Safe modification:** Add integration tests with sample rasters in 5-10 different projections; add logging of reprojected bounds for debugging.

## Dependencies at Risk

### PyKrige Maturity & Support
- **Issue:** `pykrige>=1.7` added as hard dependency in `pyproject.toml` (line 28)
- **Files:** `pyproject.toml`, `terraflow/climate.py` (imports at line 299+)
- **Impact:** PyKrige is pure-Python but has limited active maintenance compared to numpy/scipy. If PyKrige is abandoned, TerraFlow's kriging feature becomes unmaintained. PyKrige also has known edge cases (e.g., singular covariance matrices with perfectly collinear points).
- **Current mitigation:** Graceful fallback to linear interpolation if kriging fails (climate.py, lines 335-343); optional dependency via config.
- **Recommendation:** Document fallback behavior in user guide; add warning log when kriging falls back; consider SALib and PyKrige as "Recommended" rather than strict dependencies.

### Pydantic v2 Strict Validation
- **Issue:** All config models use Pydantic v2 with `ConfigDict(extra="forbid")`
- **Files:** `terraflow/config.py` (all BaseModel classes), `terraflow/climate.py` (CoordinateRange)
- **Impact:** Forward compatibility risk — if user config has extra fields (e.g., from future version of TerraFlow or from copy-paste), validation fails immediately. Config validation error messages don't always hint at the correct field names.
- **Current mitigation:** Comprehensive error messages in field validators; help text in CLI.
- **Recommendation:** Monitor Pydantic v3 release; test config migration path.

## Missing Critical Features (Blocking JOSS Publication)

### No Validation Against Reference Classification
- **Problem:** Paper cannot claim accuracy without benchmarking against FAO GAEZ or USDA NASS data
- **Files:** `terraflow/pipeline.py`, `terraflow/stats.py` (no validation stage)
- **Blocks:** JOSS reviewer will request validation before acceptance
- **Priority:** HIGH — Stage 4 in research roadmap (2 weeks estimated effort)

### No Global Sensitivity Analysis (SALib)
- **Problem:** Weights w_v, w_t, w_r are presented as "user-configurable" but no guidance on how to set them
- **Files:** `terraflow/config.py` (ModelParams), `terraflow/model.py`
- **Blocks:** Paper cannot claim parameter sensitivity is understood
- **Priority:** MEDIUM — Stage 3 in research roadmap (1 week effort); provides quantitative Sobol' indices for weight justification.

## Test Coverage Gaps

### Climate Interpolation Edge Cases
- **What's not tested:**
  - Kriging with <5 stations (fallback to linear)
  - All three variogram models failing during LOOCV
  - Duplicate lat/lon coordinates in climate data
  - Extrapolation far outside convex hull
- **Files:** `terraflow/climate.py` (entire interpolation module), tests assume ≥5 well-distributed stations
- **Risk:** Silent fallback from kriging to linear; user assumes kriging results
- **Priority:** Medium — add regression tests for fallback scenarios

### Raster CRS Reprojection
- **What's not tested:**
  - Non-linear projections (UTM, polar stereographic, etc.)
  - ROI crossing dateline
  - Raster in projected CRS, ROI in geographic
  - Tiny or degenerate windows
- **Files:** `terraflow/geo.py` (clip_raster_to_roi)
- **Risk:** Subtle bugs in coordinate transformation; edge cases produce empty windows
- **Priority:** Medium — add integration tests with sample GeoTIFFs in 5 different CRS

### Uncertainty Propagation (Monte Carlo)
- **What's not tested:**
  - `model.uncertainty_samples > 0` code path coverage
  - Correctness of CI computation
  - Performance of 1000+ samples on large cell sets
- **Files:** `terraflow/pipeline.py` (uncertainty path), `terraflow/model.py` (suitability_score_array)
- **Risk:** Untested code path; CI bounds may be incorrectly computed
- **Priority:** Low (Stage 2 code path, but covered by smoke tests)

---

*Concerns audit: 2026-03-18*
