# Requirements: TerraFlow

**Defined:** 2026-03-18
**Core Value:** Every TerraFlow run produces a verifiable, reproducible result — same inputs always yield the same outputs, with full uncertainty quantification and provenance — making findings publishable and auditable.

## v1 Requirements

### Foundation Hardening

- [ ] **HARD-01**: Pipeline raises `pyproj.CRSError` with an informative message (including the mismatched CRS strings) when raster and climate CRS are incompatible — replacing broad `except Exception` handlers in `geo.py` and `pipeline.py`
- [ ] **HARD-02**: Test suite covers kriging fallback scenarios (fewer than MIN_KRIGING_STATIONS stations) and uncertainty propagation edge cases (zero variance, single sample)
- [ ] **HARD-03**: `report.json` includes variogram diagnostics block with nugget, sill, range, and model name from PyKrige when kriging is used
- [ ] **HARD-04**: `plotly` moved to optional `[viz]` extra in `pyproject.toml`; trove classifiers and `Documentation` URL added for JOSS packaging compliance

### Sensitivity Analysis

- [ ] **SENS-01**: User can run Sobol' first-order and total-order sensitivity indices over all `ModelParams` bounds using SALib — producing citable, JOSS-recognized sensitivity results
- [ ] **SENS-02**: User can run Morris elementary effects screening over `ModelParams` for rapid parameter importance ranking before full Sobol' analysis
- [ ] **SENS-03**: `report.json` includes a `sensitivity` block with Sobol' indices, confidence intervals, and parameter rankings when sensitivity analysis is run
- [ ] **SENS-04**: User can invoke sensitivity analysis via `terraflow sensitivity -c config.yml` CLI subcommand independently of the main pipeline run

### Model Validation

- [ ] **VALD-01**: User can run spatial block cross-validation with buffer-zone excluded folds (Roberts et al. 2017 method) to correctly account for spatial autocorrelation in suitability scores
- [ ] **VALD-02**: User can compute Cohen's kappa comparing TerraFlow suitability classification against a reference classification (FAO GAEZ or synthetic reference dataset)
- [ ] **VALD-03**: Kriging LOOCV RMSE diagnostics are explicitly exposed in `report.json` (already computed in pipeline — surfaced as named output field)
- [ ] **VALD-04**: `report.json` includes a `validation` block with Cohen's kappa, spatial CV metrics (mean accuracy per fold), and LOOCV RMSE

### H3 Export

- [ ] **H3-01**: User can export `features` DataFrame to an H3-indexed structure at a configurable resolution using `terraflow.export.to_h3()` function
- [ ] **H3-02**: `h3-py` is an optional dependency (in `[project.optional-dependencies]`); calling H3 export without it raises `ImportError` with install instructions
- [ ] **H3-03**: H3 resolution parameter is included in the run fingerprint computation so different resolutions produce distinct cached artifacts
- [ ] **H3-04**: User can export results in H3 format via `terraflow export --format h3 -c config.yml` CLI subcommand

### Paper & JOSS Submission

- [ ] **JOSS-01**: `paper.md` includes a quantitative results table using outputs from sensitivity analysis and model validation runs
- [ ] **JOSS-02**: `biblio.bib` includes citations for SALib (Herman & Usher 2017, JOSS), Saltelli et al. (2008), and Cressie (1993) / Matheron (1963) for kriging
- [ ] **JOSS-03**: `paper.md` is updated with the correct submission date and version string matching the PyPI release
- [ ] **JOSS-04**: End-to-end Docker smoke test passes without network access, verifying an independent JOSS reviewer can reproduce results from the repository alone

## v2 Requirements

### Advanced Geostatistics

- **GEO-01**: Directional variogram plots for spatial anisotropy detection (requires scikit-gstat)
- **GEO-02**: Universal Kriging with elevation covariate support
- **GEO-03**: Projected coordinate system (UTM) option for variogram fitting at high latitudes

### Interoperability

- **INTEROP-01**: STAC/COG integration for cloud-native raster ingestion
- **INTEROP-02**: Polygon ROI support (shapefile / GeoJSON) in addition to bounding box
- **INTEROP-03**: Automated reference data download for validation datasets

### ML Extensions

- **ML-01**: Data-driven weight learning from labeled training points

## Out of Scope

| Feature | Reason |
|---|---|
| Web UI / dashboard | Library-first; visualization is caller's responsibility |
| Streaming / real-time ingestion | Batch pipeline; streaming adds complexity without research value |
| Commercial ag operations tooling | Focus is research community |
| Non-Python client SDKs | Python-first for v1 |
| Automated reference data download | Scope risk; requires network and legal clearance per dataset |
| ML-based weight learning | Changes the core model identity; defer to v2 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|---|---|---|
| HARD-01 | Phase 1 | Pending |
| HARD-02 | Phase 1 | Pending |
| HARD-03 | Phase 1 | Pending |
| HARD-04 | Phase 1 | Pending |
| SENS-01 | Phase 2 | Pending |
| SENS-02 | Phase 2 | Pending |
| SENS-03 | Phase 2 | Pending |
| SENS-04 | Phase 2 | Pending |
| VALD-01 | Phase 3 | Pending |
| VALD-02 | Phase 3 | Pending |
| VALD-03 | Phase 3 | Pending |
| VALD-04 | Phase 3 | Pending |
| H3-01 | Phase 4 | Pending |
| H3-02 | Phase 4 | Pending |
| H3-03 | Phase 4 | Pending |
| H3-04 | Phase 4 | Pending |
| JOSS-01 | Phase 5 | Pending |
| JOSS-02 | Phase 5 | Pending |
| JOSS-03 | Phase 5 | Pending |
| JOSS-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after roadmap creation — all 20 requirements mapped*
