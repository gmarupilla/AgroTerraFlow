# Architecture Patterns

**Domain:** Research-grade geospatial ag-suitability Python library
**Researched:** 2026-03-18
**Confidence:** MEDIUM (codebase analysis = HIGH; peer-library integration patterns = MEDIUM from training knowledge, unverifiable without network access)

---

## Recommended Architecture for New Modules

The three new functional areas — sensitivity analysis, spatial cross-validation / validation,
and H3 export — must integrate into TerraFlow's existing layered pipeline without violating
its core invariants: determinism, atomic I/O, and strict separation between compute and
output layers.

The recommended integration pattern, drawn from how well-regarded libraries (PySAL, rioxarray,
GeoPandas) structure optional analytical modules, is: **thin adapter modules that consume
already-computed pipeline outputs, not replacements for pipeline stages**.

---

## Current Architecture (Ground Truth from Codebase)

TerraFlow's layers in dependency order, innermost first:

```
utils.py (logger, normalize, ensure_dir)
    ↑
config.py (Pydantic models: ModelParams, ClimateConfig, PipelineConfig, ROI)
    ↑
core/run_identity.py (SHA256 fingerprinting, config canonicalization)
    ↑
ingest.py (DataCatalog, RasterLayer, ClimateLayer — metadata only, no pixel data)
    ↑
geo.py (clip_raster_to_roi — CRS reprojection, masked array)
    ↑
climate.py (ClimateInterpolator — linear/kriging/IDW, LOOCV at init)
    ↑
model.py (suitability_score, suitability_score_array — pure computation, no I/O)
    ↑
stats.py (RasterSummary, ClimateSummary, RunReport — QA serialization)
    ↑
pipeline.py (run_pipeline — orchestrates all above, atomic artifact writes)
    ↑
cli.py (Typer entry point — argument parsing, error handling)
```

Visualization (`viz.py`) sits outside the main flow: consumed by notebooks and external
callers, never called by `pipeline.py`.

---

## Component Boundaries for New Modules

### Sensitivity Analysis Module (`terraflow/sensitivity.py`)

**What it does:** Quantify which ModelParams inputs drive output score variance (Sobol or Morris indices).

**Boundary:** Consumes `model.suitability_score_array` and `config.ModelParams` directly.
Does NOT touch the pipeline, rasters, or climate data. Operates on a parameter sample space,
not on a spatial grid. This is the pattern used by SALib (Herman & Usher, 2017) —
the analysis function is decoupled from the system under analysis, receiving only a callable
and a parameter definition dict.

**Interface contract:**
```
sensitivity.run_sobol(
    model_fn: Callable,          # wraps suitability_score_array
    param_bounds: dict,          # {param_name: [low, high]}
    n_samples: int,              # Saltelli sample count
    seed: int,                   # for determinism
) -> SobolResult                 # first-order, total-order indices + confidence intervals
```

**Communicates with:**
- `model.py` — the scoring function as a black box
- `config.py` — ModelParams bounds define the parameter space
- `pipeline.py` — results written to `report.json` under a `sensitivity` key
  (pipeline calls sensitivity module after feature computation if enabled)

**Does NOT communicate with:** `ingest.py`, `geo.py`, `climate.py`, `core/run_identity.py`

**Confidence:** MEDIUM — SALib integration pattern is well-established in the Python SA
community; the specific TerraFlow interface is designed here, not extracted from external docs.

---

### Validation Module (`terraflow/validation.py`)

**What it does:** Cross-validate suitability scores against reference datasets or
known ag outcomes; extend kriging LOOCV from `climate.py` into spatial k-fold CV.

**Boundary:** Consumes `features.parquet` output (the DataFrame from `pipeline.run_pipeline`)
and an optional reference dataset (CSV or GeoDataFrame). The validation module is a
**post-pipeline analysis layer** — it never participates in the pipeline run itself. This
mirrors PySAL's `esda` and `spopt` pattern: spatial analysis runs after geometry assembly,
not during it. (Confidence: MEDIUM — based on training knowledge of PySAL module structure.)

Two sub-components:

**a) Spatial Cross-Validation (`SpatialKFoldCV`)**

Standard k-fold but with spatially buffered train/test splits to avoid spatial autocorrelation
leakage — the pattern used by `sklearn.model_selection` extensions and spatial ML literature.

```
SpatialKFoldCV:
    input:  features DataFrame (lat, lon, score columns)
    method: buffer_distance — exclude neighbors within distance of test points from training
    output: CVResult — per-fold RMSE, MAE, R², spatial autocorrelation of residuals
```

**b) Reference Dataset Comparison (`score_vs_reference`)**

Join suitability scores to a reference DataFrame on spatial proximity (nearest-neighbor
join within a tolerance) or on an explicit cell ID, then compute agreement metrics.

```
score_vs_reference:
    input:  features DataFrame, reference DataFrame (lat, lon, ground_truth_column)
    method: spatial join (Haversine distance or cell_id match)
    output: ValidationResult — Pearson r, Spearman ρ, RMSE, bias
```

**Communicates with:**
- `pipeline.py` — consumes `features.parquet` result (passed in as DataFrame)
- `stats.py` — `ValidationResult` is a Pydantic model following the RunReport pattern
- `pipeline.py` (write path) — results optionally written to `report.json` under `validation` key

**Does NOT communicate with:** `ingest.py`, `geo.py`, `climate.py`, `model.py` directly

---

### CRS Validation Utilities (`terraflow/geo.py` — extend in place)

**What it does:** Replace broad except handlers with informative CRS-mismatch errors.

**Boundary:** This is NOT a new module. CRS validation helpers belong in `geo.py` as
private functions called at the clipping step. This follows rioxarray's pattern: CRS
checking is co-located with the reprojection operation, not in a separate validator module.
(Confidence: HIGH — rioxarray source and TerraFlow's existing `geo.py` both confirm this.)

Concretely:
- `_assert_crs_compatible(src_crs, dst_crs)` — raises `CRSMismatchError` (custom ValueError
  subclass) with specific diagnostic: what the source CRS is, what the target CRS is, and
  what the user should change in their config.
- `_validate_roi_crs(roi_crs_str)` — raises `ValueError` with a clear message if the EPSG
  code cannot be parsed by PyProj before any transformation is attempted.

The `CRSMismatchError` class should live in `terraflow/exceptions.py` (new, minimal file)
so it can be caught specifically by callers without importing `geo.py`.

**Communicates with:**
- `geo.py` — CRS validation helpers used inside `clip_raster_to_roi`
- `cli.py` — catches `CRSMismatchError` for user-facing message formatting

---

### Kriging Diagnostics (extend `terraflow/climate.py`)

**What it does:** Surface variogram parameters, LOOCV metrics per variable, and
nugget-sill-range estimates in the output artifact.

**Boundary:** Already partially implemented — `ClimateInterpolator.cv_metrics` stores
LOOCV RMSE/MAE per variable. The gap is: (1) variogram parameters (nugget, sill, range)
are not extracted from the fitted PyKrige object; (2) LOOCV residuals themselves are not
returned, only aggregated RMSE/MAE.

Extend `_init_kriging` to populate a `variogram_params` dict alongside `cv_metrics`, and
extend `_loocv` to return the residual array (not just summary stats), stored privately for
optional downstream use by `validation.py`.

**Communicates with:** `climate.py` internal — no new cross-module dependency introduced.
The `cv_metrics` dict (already written to `report.json`) gains new keys.

---

### H3 Export Layer (`terraflow/export.py`)

**What it does:** Convert per-cell `features.parquet` results (lat/lon point grid)
into H3 cell indices at a caller-specified resolution, then aggregate scores within
each H3 cell.

**Boundary:** Pure output transformation. Consumes the `features` DataFrame from
`pipeline.run_pipeline`. Does not touch spatial rasters, climate data, or the pipeline
orchestrator. This matches how GeoPandas handles driver-specific exports (`to_file`,
`to_postgis`) — format adapters are thin wrappers on a complete GeoDataFrame, not
part of the analysis pipeline.

**Interface contract:**
```
export.to_h3(
    features: pd.DataFrame,     # output of run_pipeline (lat, lon, score, ...)
    resolution: int,            # H3 resolution 0–15 (7–9 recommended for field scale)
    agg: str = "mean",          # aggregation within H3 cell: "mean", "max", "min"
) -> pd.DataFrame               # h3_index, score_agg, score_ci_low_agg, score_ci_high_agg
```

**H3 indexing pattern** (MEDIUM confidence — based on h3-py training knowledge, API
may have changed):
- `h3.latlng_to_cell(lat, lon, resolution)` → returns H3 index string per point
- Group by H3 index, aggregate score columns
- Return a flat DataFrame: one row per H3 cell, columns for index + aggregated scores

The `h3-py` library (Uber's Python binding) is an optional dependency — raise a clear
`ImportError` with install instructions if not present. Do not add to core
`[project.dependencies]`; add to `[project.optional-dependencies]` under an `h3` key.

**Communicates with:**
- `pipeline.py` — consumes the output DataFrame (passed in, not imported from pipeline)
- `viz.py` — H3 export results can be passed to visualization helpers independently

**Does NOT communicate with:** Any upstream pipeline module.

---

## Recommended Module Layout After Changes

```
terraflow/
├── cli.py               (extended: catches CRSMismatchError)
├── pipeline.py          (extended: optional sensitivity + validation calls, artifact write)
├── config.py            (extended: SensitivityConfig, ValidationConfig optional blocks)
├── ingest.py            (unchanged)
├── geo.py               (extended: _assert_crs_compatible, _validate_roi_crs)
├── climate.py           (extended: variogram_params in cv_metrics, residuals in _loocv)
├── model.py             (unchanged — pure computation)
├── stats.py             (extended: ValidationResult Pydantic model)
├── sensitivity.py       (NEW — Sobol/Morris, wraps model.suitability_score_array)
├── validation.py        (NEW — SpatialKFoldCV, score_vs_reference)
├── export.py            (NEW — to_h3, optional h3-py dependency)
├── exceptions.py        (NEW — CRSMismatchError, minimal)
├── viz.py               (unchanged — existing scatter plot)
├── utils.py             (unchanged)
└── core/
    └── run_identity.py  (unchanged — fingerprinting contract must not change)
```

---

## Data Flow

### Existing Flow (unchanged)

```
YAML config → PipelineConfig → run_fingerprint → [cache check]
                                                        ↓
                               DataCatalog (ingest) → clip_raster (geo)
                                                        ↓
                               ClimateInterpolator (climate) → per-cell values
                                                        ↓
                               suitability_score_array (model) → scores
                                                        ↓
                               Monte Carlo draws (model/pipeline) → CI bounds
                                                        ↓
                               features.parquet + manifest.json + report.json (pipeline)
```

### New Flow (additions, not replacements)

```
features.parquet (existing pipeline output)
        ↓
[Optional] sensitivity.run_sobol(model_fn, param_bounds) → SobolResult
        ↓ (appended to report.json["sensitivity"])

[Optional] validation.score_vs_reference(features, reference_df) → ValidationResult
        ↓ (appended to report.json["validation"])

[Optional] export.to_h3(features, resolution) → h3_df
        ↓ (caller writes to h3_features.parquet or passes to viz)
```

The sensitivity and validation calls happen inside `pipeline.py` after feature assembly,
gated by presence of `SensitivityConfig` or `ValidationConfig` in `PipelineConfig`.
The H3 export is NOT called from `pipeline.py` — it is a post-pipeline library function
the caller invokes explicitly. This avoids adding h3-py as a transitive dependency for
users who don't need grid export.

---

## Patterns to Follow

### Pattern 1: Pydantic Result Models
**What:** Every new analysis result type (SobolResult, ValidationResult) is a Pydantic
BaseModel with JSON round-trip safety.
**When:** Any result written to `report.json` or returned from a public function.
**Why:** Matches `RunReport`, `RasterSummary`, `ClimateSummary` — consistent, serializable,
mypy-checkable. Reviewers expect structured output for reproducibility.

### Pattern 2: Optional Dependencies via ImportError
**What:** Gate optional libraries (SALib for Sobol, h3-py for H3 export) behind try/import
with an explicit `ImportError` message that includes the pip install command.
**When:** Any library not in core `[project.dependencies]`.
**Why:** `climate.py` already uses this pattern for PyKrige — consistent and JOSS-reviewer
friendly (independent install path).

```python
# Example from climate.py (existing pattern):
import importlib.util
if importlib.util.find_spec("pykrige") is None:
    raise ImportError(
        "PyKrige is required for kriging interpolation. "
        "Install with: pip install pykrige"
    )
```

### Pattern 3: Post-Pipeline Adapter, Not Pipeline Stage
**What:** New analytical modules (sensitivity, validation, H3 export) receive the pipeline
output DataFrame as input — they do not intercept the pipeline run.
**When:** Any module whose inputs are fully determined by `features.parquet`.
**Why:** Preserves run fingerprint stability. Adding a new analysis module cannot change
the run fingerprint (which is deterministic over config + inputs, not analysis choices).
This mirrors how PySAL's `esda` analysis runs on a GeoDataFrame after GeoPandas assembles
geometry — the assembly and analysis are cleanly separated.

### Pattern 4: Config-Gated Execution in Pipeline
**What:** Sensitivity and validation config blocks are optional in `PipelineConfig`
(default None). Pipeline only runs these modules when the block is present.
**When:** Any feature that is opt-in for users.
**Why:** Zero performance cost for existing users; backward-compatible YAML configs
continue to work without modification.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Sensitivity Analysis Inside the Scoring Loop
**What goes wrong:** Running Saltelli samples for every spatial cell during normal
pipeline execution.
**Why bad:** Sobol analysis requires O(N * (2k + 2)) model evaluations where N is
the Saltelli sample count and k is the number of parameters. For a 500-cell grid with
N=1024 and k=9 parameters, this is ~10M evaluations — orders of magnitude more expensive
than the pipeline itself.
**Instead:** Sensitivity analysis runs once on the model function in parameter space (not
spatial space). It characterizes how ModelParams bounds affect scores globally, not
per-cell.

### Anti-Pattern 2: Spatial Validation With Random K-Fold
**What goes wrong:** Using standard (non-spatial) cross-validation folds on spatially
autocorrelated suitability data.
**Why bad:** Moran's I on agricultural suitability scores is typically positive (nearby
cells are similar). Random splits allow training data to be spatially adjacent to test data,
creating optimistic performance estimates. Reviewers familiar with geostatistics will
flag this immediately.
**Instead:** Use buffered spatial k-fold (exclude a buffer zone around test points from
training) or block CV following Roberts et al. (2017, Ecography).

### Anti-Pattern 3: H3 as Primary Grid
**What goes wrong:** Replacing the raster pixel grid with H3 cells as the primary
unit of computation.
**Why bad:** H3 cells are irregular in area, do not align with raster pixels, and require
areal interpolation to assign pixel values to cells — introducing resampling error. H3 is
appropriate for export and visualization, not for computation over raster data.
**Instead:** Keep raster pixels as the primary computational unit; H3 is a post-processing
export format only (confirmed by the existing PROJECT.md key decision: "H3 as export format,
not primary grid").

### Anti-Pattern 4: Breaking the Run Identity Contract
**What goes wrong:** Adding new computation in `pipeline.py` that modifies what gets
hashed into the run fingerprint without updating `core/run_identity.py`.
**Why bad:** Two logically different runs (one with sensitivity enabled, one without)
would share the same fingerprint, causing false cache hits.
**Instead:** Any new config block that changes output content (e.g., `SensitivityConfig`)
must be included in the canonicalized config dict that feeds `compute_run_fingerprint`.
Config blocks that do not affect `features.parquet` content (e.g., export options) should
be excluded from the fingerprint.

---

## Component Boundaries Summary

| Component | Inputs | Outputs | Must Not Touch |
|-----------|--------|---------|----------------|
| `sensitivity.py` | `ModelParams` bounds, `model.suitability_score_array` | `SobolResult` (Pydantic) | rasters, climate, ingest, run_identity |
| `validation.py` | `features` DataFrame, optional reference DataFrame | `ValidationResult` (Pydantic) | rasters, climate, ingest, model, run_identity |
| `export.py` | `features` DataFrame, resolution: int | H3 DataFrame | all pipeline modules |
| `geo.py` (extended) | CRS strings | raises `CRSMismatchError` | model, stats, pipeline |
| `exceptions.py` | — | `CRSMismatchError` class | all modules (imported only) |
| `climate.py` (extended) | existing | `variogram_params` in `cv_metrics` | no new cross-module deps |

---

## Suggested Build Order

Dependencies between the new components determine ordering:

**Phase 1 — Foundation (no upstream deps on new modules)**
1. `exceptions.py` — no dependencies; needed by `geo.py` and `cli.py`
2. `geo.py` CRS validation extension — depends only on `exceptions.py` (new) and PyProj (existing)
3. `climate.py` kriging diagnostics extension — internal only; no new cross-module deps

**Phase 2 — Analytical modules (depend on model.py and existing pipeline output)**
4. `sensitivity.py` — depends on `model.py` (existing) + SALib (new optional dep)
5. `validation.py` — depends on `stats.py` (new `ValidationResult` model) + spatial math

**Phase 3 — Export and config integration**
6. `export.py` — depends on h3-py (optional dep); no other new deps
7. `config.py` extensions (`SensitivityConfig`, `ValidationConfig`) — gating the above
8. `pipeline.py` integration — calls sensitivity and validation modules; adds optional config blocks to fingerprint

**Rationale for this order:**
- `exceptions.py` and `geo.py` fixes have no dependencies and unblock CRS-related test failures immediately
- Kriging diagnostics extend `climate.py` internally — can be done in isolation before sensitivity
- `sensitivity.py` depends only on `model.py` (pure function, no I/O) — safest to implement and test in isolation
- `validation.py` needs `ValidationResult` Pydantic model in `stats.py` before it can be finalized
- H3 export is fully decoupled from analysis modules — can be built in parallel with validation
- Pipeline integration comes last because it touches the run fingerprint contract

---

## Scalability Considerations

| Concern | At 500 cells (current max) | At 10K cells | At 100K cells |
|---------|---------------------------|--------------|---------------|
| Sensitivity analysis | Negligible — runs in param space, not spatial space | Same | Same |
| LOOCV (kriging) | O(n²) in stations, not cells — fine for typical station counts | Same | Same |
| Spatial k-fold CV | O(n_cells × n_folds) distance computation — fast with vectorized Haversine | May need spatial index (scipy.spatial.KDTree) | Requires spatial index |
| H3 export | O(n_cells) — trivial | O(n_cells) | O(n_cells) |
| Monte Carlo uncertainty | O(n_cells × n_samples) — current bottleneck | Needs numpy vectorization (already in place) | Memory-bound at ~100M floats |

The `max_cells: 500` default in `PipelineConfig` gates the spatial scaling concern at the
pipeline level. Research users exceeding this will tune it explicitly and accept the runtime.

---

## Interop with H3 / Alternative Grid Systems

**Pattern (MEDIUM confidence — training knowledge of h3-py ≤ 4.x API):**

The h3-py library exposes `h3.latlng_to_cell(lat, lon, resolution)` returning a hex string
index. Applied to every row of `features.parquet`, this produces an H3 cell column. Groupby
aggregation then reduces the pixel-resolution results to H3-resolution results.

Resolution guidance for agricultural use: H3 resolution 7 (~5.16 km² cells) to resolution 9
(~0.105 km²) covers most field-scale ag analysis. Resolution 8 (~0.74 km²) is a practical
default for county-level studies.

The H3 export DataFrame schema should include:
- `h3_index` (str) — hex H3 cell identifier
- `score_mean`, `score_max`, `score_min` — aggregated suitability
- `cell_count` — number of pixels contributing to each H3 cell
- `score_ci_low_mean`, `score_ci_high_mean` — MC uncertainty bounds (if present)

DeckGL and Pandas H3 (h3pandas) downstream consumers expect the `h3_index` column to be
the primary key — name it consistently.

**Caveat:** h3-py v4 introduced breaking API changes vs v3 (function renames). The
`latlng_to_cell` name is h3-py v4. If targeting both: check `h3.__version__` at call
time and branch, or pin to h3-py >= 4.0 in optional dependencies.

---

## Sources and Confidence Notes

| Claim | Confidence | Source |
|-------|------------|--------|
| Existing TerraFlow layer structure | HIGH | Direct codebase analysis (`pipeline.py`, `climate.py`, `model.py`, `config.py`, `geo.py`) |
| Current ClimateInterpolator LOOCV implementation | HIGH | Direct codebase analysis (`climate.py` lines 289–393) |
| Current ModelParams fields and scoring function | HIGH | Direct codebase analysis (`config.py`, `model.py`) |
| SALib integration pattern (post-pipeline, callable-wrapping) | MEDIUM | Training knowledge of SALib 1.x/2.x — unverifiable without network access |
| PySAL esda post-geometry analysis pattern | MEDIUM | Training knowledge of PySAL v2.x — unverifiable without network access |
| Spatial k-fold CV / buffered splits (Roberts et al. 2017) | MEDIUM | Well-cited methodology; specific PySAL implementation details unverified |
| h3-py v4 API (`latlng_to_cell`) | MEDIUM | Training knowledge — h3-py v4 released 2023, may have further changes by 2026 |
| H3 resolution guidance for ag scale | MEDIUM | Training knowledge of H3 resolution specs |
| CRS validation pattern from rioxarray | MEDIUM | Training knowledge — rioxarray co-locates CRS checks with reprojection |
| Run fingerprint must include new config blocks | HIGH | Direct codebase analysis of `core/run_identity.py` canonicalization contract |

---

*Architecture analysis: 2026-03-18*
*Note: No external network access was available during this research session. All peer-library
pattern claims are from training knowledge (cutoff August 2025) and are marked MEDIUM confidence.
Verify h3-py API against current docs before implementing `export.py`.*
