# Project Research Summary

**Project:** TerraFlow (terraflow-agro)
**Domain:** Research-grade geospatial / agricultural suitability Python library targeting JOSS
**Researched:** 2026-03-18
**Confidence:** MEDIUM-HIGH

## Executive Summary

TerraFlow is a reproducibility-first batch pipeline for agricultural suitability scoring. The 0.2.x codebase already ships a solid foundation: deterministic SHA-256 fingerprinting, OrdinaryKriging with LOOCV, Monte Carlo uncertainty propagation, and a Parquet-centric output contract. The work remaining before JOSS submission is additive, not architectural. Three new analytical modules (sensitivity analysis, model validation, H3 export) integrate as post-pipeline adapters that consume `features.parquet` without touching the core pipeline flow. Two in-place extensions (CRS error hardening in `geo.py`, variogram diagnostics in `climate.py`) close reviewer-visible gaps without introducing new modules.

The recommended approach is strictly sequential: fix the CRS and kriging diagnostic gaps first (they have no dependencies and unblock existing test failures), then build sensitivity analysis, then validation, and finally H3 export. The only new core dependencies are SALib for Sobol/Morris sensitivity analysis and h3-py for hexagonal grid export; everything else leverages existing libraries. This minimal-dependency strategy directly serves JOSS reviewers who will audit the dependency graph.

The most consequential risks are methodological rather than technical. Sensitivity analysis that violates the Sobol' sampling contract (N must be a power of 2) or that feeds unconstrained weight samples through a clipped scorer produces silent false results. Validation against spatially autocorrelated reference data without spatial blocking inflates Cohen's κ to indefensible values. Both are well-understood pitfalls in the spatial statistics literature and have known prevention strategies that must be built into the implementation, not bolted on after the fact.

---

## Key Findings

### Recommended Stack

TerraFlow's existing dependency graph is close to complete. The only additions needed are SALib (Sobol'/Morris sensitivity analysis, MIT licensed, JOSS-citable via doi:10.21105/joss.00097) and h3-py (H3 hexagonal indexing, Apache-2.0). Both are small, platform-safe, and add no transitive dependencies beyond those already present. Spatial cross-validation requires no new library — a hand-rolled LOOCV loop over PyKrige is 15 lines and is more auditable than importing a framework. CRS hardening uses pyproj primitives already in the stack.

Packaging needs configuration hardening, not toolchain changes: tighten pyproject.toml version floors, split `dev` extras into separate `test` and `dev` groups, move `plotly` to an optional `viz` extra, and add PyPI trove classifiers. The existing setuptools + build setup is correct for JOSS; do not migrate to Hatchling or Flit.

**Core technologies:**
- SALib 1.4.6+: Sobol'/Morris sensitivity analysis — JOSS-citable, MIT, exact API match for TerraFlow's use case
- h3-py 3.7+ (or 4.0+ if released stable): H3 hexagonal export — the only Python binding for Uber H3; Apache-2.0
- PyKrige (existing): LOOCV for kriging validation — no new dependency; standard geostatistical LOOCV pattern
- pyproj (existing): CRS validation hardening — all required primitives (`CRS.equals`, `CRSError`) already present
- setuptools (existing): JOSS packaging — already compliant; configuration gaps only

**Version verification required before pinning:**
```
pip index versions SALib    # confirm 1.5 API (ResultDict / .to_df())
pip index versions h3       # confirm 3.x vs 4.x stable series
```

### Expected Features

**Must have (table stakes — JOSS checklist blockers):**
- CRS validation with informative errors — broad `except Exception` in `geo.py` masks CRS bugs; JOSS reviewers test edge cases
- MC uncertainty regression tests — Stage 2 MC path has a test coverage gap; must be closed before submission
- Runnable demo without external data download — `make get-demo-data` synthetic path must work unconditionally
- Quantitative results table in paper.md — currently missing; LOOCV RMSE, MC CI width, Sobol' indices must appear
- paper.md date updated to submission date — currently shows 2025-11-27

**Should have (differentiators that justify the JOSS paper):**
- Sensitivity analysis (Sobol' indices via SALib) — no ag suitability library does this out of the box; enables "w_v drives 62% of variance" claim in paper
- Model validation against reference classification (Cohen's κ with spatial blocking) — transforms reproducibility claim into "reproducible AND directionally correct"
- Variogram diagnostics in report.json — nugget/sill/range per variable; geostatistician reviewers will look for this
- H3 index export — opens TerraFlow to H3-native analytics toolchains; not a JOSS reviewer requirement but a strong ecosystem differentiator

**Defer to post-JOSS:**
- Universal Kriging with elevation covariate (ADR-005 explicit deferral)
- Polygon ROI (requires geopandas refactor; bbox sufficient for demo)
- STAC/COG cloud integration (roadmap Q3 2026+)
- Temporal analysis / time-series kriging (schema v2 required)
- Automated FAO GAEZ / USDA NASS data download (licensing and fragility concerns)

### Architecture Approach

All new modules integrate as thin adapters that consume the completed pipeline output (`features.parquet` as a DataFrame) rather than intercepting pipeline stages. This preserves the run fingerprint contract and means no new module can corrupt existing outputs. The three new modules are `sensitivity.py` (wraps `model.suitability_score_array` as a callable for SALib), `validation.py` (spatial k-fold CV and reference score comparison), and `export.py` (H3 aggregation, optional h3-py dependency). Two in-place extensions touch `geo.py` (CRS error helpers + new `exceptions.py`) and `climate.py` (variogram parameter extraction). `pipeline.py` calls sensitivity and validation modules at the end of the run, gated by optional `SensitivityConfig` / `ValidationConfig` blocks in `PipelineConfig`. H3 export is a library function the caller invokes post-pipeline — it is NOT called from `pipeline.py` to keep h3-py out of the core dependency graph.

**Major components:**
1. `exceptions.py` (NEW, minimal) — `CRSMismatchError` custom ValueError subclass; imported by `geo.py` and `cli.py`
2. `sensitivity.py` (NEW) — `run_sobol(model_fn, param_bounds, n_samples, seed)` returning Pydantic `SobolResult`; calls SALib behind optional import guard
3. `validation.py` (NEW) — `SpatialKFoldCV` and `score_vs_reference`; Pydantic `ValidationResult` serialized to `report.json["validation"]`
4. `export.py` (NEW) — `to_h3(features, resolution, agg)` consuming the pipeline output DataFrame; h3-py behind optional import guard
5. `geo.py` (EXTENDED) — `_assert_crs_compatible`, `_validate_roi_crs` replacing broad except handlers
6. `climate.py` (EXTENDED) — variogram parameters (nugget, sill, range) surfaced in `cv_metrics`; LOOCV residual array retained internally

### Critical Pitfalls

1. **Sobol' sample size must be a power of 2** — SALib executes silently on non-power-of-2 N but produces mathematically invalid confidence intervals. With D=9 parameters, the minimum is N=512 (9,728 evaluations). Default to N=1024. Add a CLI validation that rejects non-power-of-2 values. Record the formula `N*(2D+2)` in `sensitivity_report.json`.

2. **Weight simplex constraint violated during Saltelli sampling** — `w_v + w_t + w_r` must sum to 1.0, but Saltelli samples each weight independently over [0,1]. Scores clip to 1.0 for many samples, destroying variance and producing near-zero S1/ST indices — a false negative. Use constrained parameterization: vary only `w_v` and `w_t` freely and derive `w_r = 1 - w_v - w_t`. Alternatively, normalize the sampled weight triplet before scoring and document the Dirichlet distribution assumption.

3. **Kriging LOOCV on geographic coordinates produces uninterpretable variogram range** — PyKrige accepts raw lat/lon in degrees without complaint. The fitted variogram range is in degree-units, which are ecologically meaningless and not comparable to published values. At minimum, document this limitation explicitly in the module docstring, paper Methods, and `report.json`. Add a warning when ROI centroid latitude exceeds 55° (>10% longitude distortion). Ideally, convert to a local projected CRS (UTM) before fitting.

4. **Validation κ ignores spatial autocorrelation** — Standard `cohen_kappa_score` assumes independent observations. Spatially autocorrelated suitability cells inflate effective N and produce overconfident κ. Use buffered spatial k-fold cross-validation (excluding a buffer zone around test points from training), report Moran's I on residuals, and cite Roberts et al. (2017) explicitly.

5. **H3 resolution not in run fingerprint hash** — If H3 export is pipeline-integrated and H3 resolution is in config but not in `compute_run_fingerprint`, two runs with different resolutions share the same fingerprint and different resolutions silently serve cached results. Keep H3 export as a post-pipeline library call (not in `pipeline.py`) to sidestep this; if it must enter the pipeline config, update `core/run_identity.py` canonicalization and add a determinism regression test.

---

## Implications for Roadmap

### Phase 1: Foundation Hardening
**Rationale:** These items have no dependencies on new analytical modules, unblock existing test failures, and directly address the two most likely mandatory-revision requests from any JOSS reviewer. CRS edge cases and MC path coverage are table-stakes gaps.
**Delivers:** Informative CRS errors with a catchable `CRSMismatchError` exception; test coverage for the MC uncertainty path; expanded variogram diagnostics in `report.json`
**Addresses:** CRS validation (table stakes), MC uncertainty coverage gap, kriging diagnostics (differentiator)
**Avoids:** Pitfall 2 (variogram range units — document limitation); Pitfall 6 (MC CI collapse at station locations — document in report.json)
**Build order:** `exceptions.py` → `geo.py` CRS extension → CRS tests → `climate.py` variogram diagnostics → MC regression tests

### Phase 2: Sensitivity Analysis (Stage 3)
**Rationale:** Sensitivity analysis depends only on `model.py` (an already-stable pure function) and SALib (a new optional dependency). It is fully decoupled from validation and H3. The Sobol' indices are a strong paper differentiator and enable quantitative weight justification — the single biggest gap between TerraFlow's current "reproducible" claim and "scientifically defensible" claim.
**Delivers:** `sensitivity.py` module; `run_sobol` and `run_morris` functions; `SobolResult` Pydantic model; `report.json["sensitivity"]` populated; SALib added to `pyproject.toml`
**Uses:** SALib 1.4.6+ (Saltelli sampler + Sobol/Morris analyzers)
**Implements:** Post-pipeline adapter pattern; config-gated execution via `SensitivityConfig`
**Avoids:** Pitfall 1 (power-of-2 N — CLI validation); Pitfall 4 (weight simplex — constrained parameterization)
**Research flag:** Standard patterns apply; SALib API is well-documented. No additional research phase needed. Verify SALib version API (1.4 vs 1.5 `ResultDict`) before implementation.

### Phase 3: Model Validation (Stage 4)
**Rationale:** Validation requires the `ValidationResult` Pydantic model in `stats.py` and spatial distance math — more moving parts than sensitivity. It also carries the highest risk of methodological mistakes (spatial autocorrelation in κ). Building sensitivity first means the paper's quantitative results section can be populated with Sobol' indices before validation is wired up.
**Delivers:** `validation.py` with `SpatialKFoldCV` and `score_vs_reference`; `ValidationResult` in `stats.py`; `report.json["validation"]` with κ, Pearson r, Spearman ρ, RMSE, Moran's I on residuals; per-fold spatial CV metrics
**Implements:** Buffered spatial k-fold following Roberts et al. (2017); nearest-neighbor spatial join using Haversine distance (scipy, already a dependency)
**Avoids:** Pitfall 3 (spatial autocorrelation in κ — spatial blocking + Moran's I reporting); Pitfall 5 (reviewer cannot run demo — synthetic reference labels in examples/)
**Research flag:** Spatial k-fold buffering implementation details may benefit from a targeted research pass. The Roberts et al. (2017) pattern is well-cited but the specific buffer distance selection for agricultural suitability grids is judgment-dependent.

### Phase 4: H3 Export and Ecosystem Interop
**Rationale:** H3 export is fully decoupled from sensitivity and validation. It is lower JOSS priority (not a checklist item) but opens TerraFlow to H3-native toolchains (DeckGL, pandas-h3, DuckDB spatial). Building it last means it does not block the critical path to JOSS submission.
**Delivers:** `export.py` with `to_h3(features, resolution, agg)` returning an H3-indexed DataFrame; h3-py added to optional dependencies; docs table mapping raster resolutions to recommended H3 resolutions
**Uses:** h3-py 3.7+ or 4.0+ (verify before pinning); h3 behind optional import guard with pip install instructions
**Implements:** Post-pipeline library call pattern (NOT called from `pipeline.py`); mean aggregation as default within H3 cells
**Avoids:** Pitfall 7 (fingerprint corruption — H3 export stays outside pipeline.py); Pitfall 10 (resolution mismatch — emit warning when H3 cell area < 4× raster pixel area)
**Research flag:** h3-py 3.x vs 4.x API decision must be made before implementation. Run `pip index versions h3` to confirm stable series. If 4.x is stable, use `latlng_to_cell` / `cell_to_boundary`. If targeting both: thin adapter function in `export.py`.

### Phase 5: Paper Finalization and JOSS Submission Prep
**Rationale:** Paper finalization depends on having actual numbers from the demo pipeline run after Stages 3 and 4. This phase is last because it consumes outputs from all prior phases. It is not a development phase — it is an editorial and packaging phase.
**Delivers:** Quantitative results table in paper.md (LOOCV RMSE, MC CI width, Sobol' indices, κ); updated paper date; SALib/kriging/MC citations added to biblio.bib; `paper/results_snapshot.json` committed; pyproject.toml packaging hardened (test extra, viz optional, classifiers); Zenodo archive updated; synthetic demo runnable end-to-end without network
**Avoids:** Pitfall 11 (stale paper quantitative claims — results_snapshot.json committed with each stage merge); Pitfall 5 (reviewer cannot reproduce — synthetic demo path)
**Research flag:** No additional research needed. All required changes are known from FEATURES.md JOSS checklist analysis.

### Phase Ordering Rationale

The ordering follows a strict dependency graph: exceptions and geo hardening have no upstream dependencies and unblock existing failures (Phase 1 first). Sensitivity analysis depends only on `model.py`, making it the safest analytical module to build next (Phase 2). Validation needs the `ValidationResult` model and carries spatial statistics complexity that benefits from sensitivity being stable first (Phase 3). H3 export is architecturally independent but lowest JOSS priority (Phase 4). Paper finalization consumes all prior phase outputs and is therefore last (Phase 5).

Key architectural constraint: Phases 2-4 all use the post-pipeline adapter pattern. This means they can be developed and tested in isolation without touching the core pipeline fingerprint contract. The fingerprint contract update (if `SensitivityConfig` affects `features.parquet`) happens only in Phase 2 when `pipeline.py` integration is wired up.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Validation):** Spatial k-fold buffer distance selection for agricultural suitability grids is not standardized. The Roberts et al. (2017) methodology prescribes buffering but leaves the distance as a domain judgment. A targeted research pass on buffer distance selection for 0.5–10 km resolution ag rasters is warranted.
- **Phase 4 (H3 Export):** h3-py version API (3.x vs 4.x function names) must be verified before implementation. This is a lookup task, not deep research, but it gates all implementation decisions in `export.py`.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation Hardening):** pyproj CRS patterns and MC test coverage are well-documented. No research needed.
- **Phase 2 (Sensitivity Analysis):** SALib Saltelli + Sobol workflow is stable and has extensive documentation. The only lookup needed is SALib version API.
- **Phase 5 (Paper Finalization):** JOSS checklist is stable and fully documented. All gaps are known.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Library identities (SALib, h3-py) are HIGH confidence; version floors are MEDIUM — must verify with `pip index versions` before pinning. scikit-gstat is LOW and should remain optional. |
| Features | HIGH | Assessment is grounded in the actual codebase, existing memory files, JOSS guidelines (stable for years), and the project's own bibliography. Ecosystem comparisons are MEDIUM. |
| Architecture | HIGH | Existing TerraFlow layer structure is from direct codebase analysis. Integration patterns (post-pipeline adapter, Pydantic result models, optional import guard) are established in the existing codebase. Peer-library patterns (PySAL, rioxarray) are MEDIUM confidence from training data. |
| Pitfalls | HIGH for code-grounded pitfalls (weight simplex, variogram units, MC CI collapse) | MEDIUM for JOSS reviewer behavior predictions. All code-grounded pitfalls are backed by specific file/line references in the TerraFlow source. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **SALib version API (1.4 vs 1.5):** `analyze()` return type changed to `ResultDict` with `.to_df()` in 1.5. Run `pip index versions SALib` and write implementation against the confirmed stable API. If pinning `>=1.5`, use `.to_df()` throughout; if `>=1.4.6`, use dict-based return.
- **h3-py version API (3.x vs 4.x):** `geo_to_h3` (3.x) vs `latlng_to_cell` (4.x) is a breaking rename. Determine the stable series before writing `export.py`. Write a thin adapter function so only one place needs to change if the version changes.
- **Kriging variogram coordinates (degrees vs metres):** The existing LOOCV in `climate.py` passes raw lat/lon. The decision of whether to (a) reproject to UTM before kriging or (b) document the degree-unit limitation must be made explicitly. Option (b) is lower effort and sufficient for JOSS if documented honestly; option (a) is scientifically preferable. This is a judgment call for the implementing developer to resolve before Phase 1 closes.
- **Spatial k-fold buffer distance:** No standard value for agricultural suitability grids at typical ROI scales (county to regional). A sensible default (e.g., the variogram range from the fitted climate model) with a configurable override is the recommended pattern, but this needs a concrete decision during Phase 3 design.
- **SALib integration into pyproject.toml:** Decision needed on whether SALib goes in core dependencies or optional `[sensitivity]` extra. Recommendation: core dependencies (sensitivity analysis is a key paper claim, not a fringe feature), but this affects the install size for all users.

---

## Sources

### Primary (HIGH confidence — direct codebase analysis)
- `terraflow/climate.py` lines 289–393 — kriging initialisation, LOOCV, single-variable model selection
- `terraflow/pipeline.py` lines 540–583 — Monte Carlo implementation, krig_std usage
- `terraflow/model.py` lines 41–47, 84–89 — weight combination, score clipping
- `terraflow/geo.py` lines 62–105 — CRS handling, reprojection, NaN guard
- `terraflow/core/run_identity.py` — fingerprint canonicalization contract
- `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` — parallel research outputs

### Secondary (MEDIUM confidence — training knowledge, stable domain literature)
- Herman & Usher (2017) JOSS paper doi:10.21105/joss.00097 — SALib citation and API
- Saltelli et al. (2008, 2010) — Sobol' sample size requirements (`N*(2D+2)`)
- Cressie (1993) "Statistics for Spatial Data" — variogram unit requirements
- Roberts et al. (2017) "Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure" — spatial k-fold blocking
- JOSS reviewer guidelines (https://joss.readthedocs.io/en/latest/reviewer_guidelines.html) — checklist items

### Tertiary (LOW confidence — needs live verification)
- scikit-gstat maintenance status and current version — verify only if variogram diagnostics prove insufficient via PyKrige
- h3-py 4.x API stability — training knowledge of h3-py 4.0 pre-release; must verify current stable series on PyPI

---
*Research completed: 2026-03-18*
*Ready for roadmap: yes*
