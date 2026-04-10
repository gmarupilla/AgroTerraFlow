# Roadmap: TerraFlow

## Overview

TerraFlow is a brownfield research library with a solid pipeline core. The work from here to JOSS submission is additive: close two reviewer-visible gaps in the foundation (CRS errors, kriging diagnostics), add three new analytical modules (sensitivity analysis, model validation, H3 export) as post-pipeline adapters, then finalize the paper with quantitative results drawn from those modules. Each phase delivers a coherent, independently testable capability. The JOSS submission target is 2026-05-25.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation Hardening** - Close the CRS error and kriging diagnostic gaps that block JOSS reviewer acceptance
- [x] **Phase 2: Sensitivity Analysis** - Add Sobol'/Morris sensitivity analysis via SALib; justify model weights quantitatively (completed 2026-03-28)
- [ ] **Phase 3: Model Validation** - Add spatially-blocked cross-validation and Cohen's kappa against reference data
- [x] **Phase 4: H3 Export** - Add optional H3-indexed output for interop with H3-native toolchains (completed 2026-04-04)
- [ ] **Phase 5: Paper and JOSS Submission** - Populate paper with quantitative results; harden packaging; ship

## Phase Details

### Phase 1: Foundation Hardening
**Goal**: The pipeline surface visible to JOSS reviewers is free of broad exception handlers and missing diagnostics — CRS mismatches produce informative errors, kriging diagnostics appear in report.json, and test coverage closes the MC uncertainty gap
**Depends on**: Nothing (first phase)
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04
**Success Criteria** (what must be TRUE):
  1. Running the pipeline with mismatched raster/climate CRS raises `CRSMismatchError` with the two CRS strings in the message, not a bare `Exception`
  2. `report.json` includes a `kriging_diagnostics` block with `nugget`, `sill`, `range_`, and `model` fields when any climate variable uses kriging interpolation
  3. The test suite passes with >=85% branch coverage including kriging fallback (fewer than MIN_KRIGING_STATIONS), MC zero-variance, and MC single-sample edge cases
  4. `pip install terraflow` installs without pulling in `plotly`; `pip install terraflow[viz]` installs plotly; `pyproject.toml` includes PyPI trove classifiers and a `Documentation` URL
**Plans:** 0/3 plans executed

Plans:
- [ ] 01-01-PLAN.md — Demote plotly to optional [viz] extra; add trove classifiers and Documentation URL
- [ ] 01-02-PLAN.md — Add CRSMismatchError with CRS guard; surface kriging variogram diagnostics in report.json
- [ ] 01-03-PLAN.md — Add targeted tests for kriging fallback, MC edge cases, CRS mismatch, and kriging diagnostics

### Phase 2: Sensitivity Analysis
**Goal**: Users can quantify which model parameters drive output variance using citable Sobol' and Morris methods, with results surfaced in report.json and invocable from the CLI
**Depends on**: Phase 1
**Requirements**: SENS-01, SENS-02, SENS-03, SENS-04
**Success Criteria** (what must be TRUE):
  1. User can run `terraflow sensitivity -c config.yml` and receive Sobol' first-order (S1) and total-order (ST) indices for every `ModelParams` bound with confidence intervals
  2. User can run Morris elementary effects screening over `ModelParams` bounds as a faster pre-screening step before full Sobol' analysis
  3. `report.json` includes a `sensitivity` block containing Sobol' S1/ST indices, confidence intervals, and parameter rankings when sensitivity analysis is run
  4. Running `terraflow sensitivity -c config.yml` with a non-power-of-2 sample size (`n_samples`) produces a clear CLI validation error before any computation starts
**Plans:** 3/3 plans complete

Plans:
- [x] 02-01-PLAN.md — Add SALib/Typer deps, SensitivityConfig models, migrate CLI to Typer subcommands
- [x] 02-02-PLAN.md — Implement sensitivity analysis engine (Sobol/Morris via SALib) with tests
- [x] 02-03-PLAN.md — Wire sensitivity CLI subcommand, add CLI integration tests, human verification

### Phase 3: Model Validation
**Goal**: Users can validate suitability scores against reference data using spatially-blocked cross-validation that correctly accounts for spatial autocorrelation, with metrics in report.json
**Depends on**: Phase 2
**Requirements**: VALD-01, VALD-02, VALD-03, VALD-04
**Success Criteria** (what must be TRUE):
  1. User can run spatial block cross-validation with a buffer-zone excluded fold (Roberts et al. 2017) and receive per-fold accuracy metrics that account for spatial autocorrelation
  2. User can compute Cohen's kappa comparing TerraFlow's suitability classification against a reference classification (FAO GAEZ or the bundled synthetic reference dataset in `examples/`)
  3. `report.json` includes a `kriging_loocv` field with LOOCV RMSE for each climate variable that used kriging — surfaced from the existing PyKrige computation, not newly computed
  4. `report.json` includes a `validation` block with Cohen's kappa, Moran's I on residuals, mean per-fold accuracy, and LOOCV RMSE when validation is run
**Plans:** 3/3 plans complete

Plans:
- [x] 03-01-PLAN.md — Surface kriging_loocv in report.json, add ValidationConfig, create synthetic reference CSV, scaffold tests
- [x] 03-02-PLAN.md — Implement validation module (spatial block CV, Cohen's kappa, Moran's I, run_validation)
- [x] 03-03-PLAN.md — Wire validate CLI subcommand, demo config, notebook, human verification

### Phase 4: H3 Export
**Goal**: Users can export pipeline output to an H3-indexed DataFrame at a configurable resolution using an optional library function and CLI subcommand, without h3-py being a core dependency
**Depends on**: Phase 1
**Requirements**: H3-01, H3-02, H3-03, H3-04
**Success Criteria** (what must be TRUE):
  1. User can call `terraflow.export.to_h3(features, resolution=8)` and receive a DataFrame indexed by H3 cell ID with suitability scores aggregated within each cell
  2. Calling `to_h3()` without `h3-py` installed raises `ImportError` with a message that includes the `pip install terraflow[h3]` install command
  3. User can run `terraflow export --format h3 -c config.yml` from the CLI and produce the H3-indexed output artifact
  4. Two pipeline runs with identical config except different H3 resolutions produce distinct run fingerprints (no silent cache collision)
**Plans:** 3/3 plans complete

Plans:
- [x] 04-01-PLAN.md — ExportConfig model, to_h3() core function, optional h3 dep wiring, unit tests
- [x] 04-02-PLAN.md — run_export() orchestrator, artifact writing, fingerprint distinctness tests
- [x] 04-03-PLAN.md — CLI export subcommand, notebook, docs, PR checklist artifacts

### Phase 5: Paper and JOSS Submission
**Goal**: The JOSS paper contains quantitative results drawn from prior phases, packaging meets JOSS reviewer requirements, and the repository passes an end-to-end smoke test without network access
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: JOSS-01, JOSS-02, JOSS-03, JOSS-04
**Success Criteria** (what must be TRUE):
  1. `paper/paper.md` includes a quantitative results table with LOOCV RMSE, MC confidence interval width, Sobol' S1 indices, and Cohen's kappa drawn from actual pipeline runs
  2. `paper/biblio.bib` contains entries for SALib (Herman & Usher 2017), Saltelli et al. (2008), and Cressie (1993) / Matheron (1963), each with correct DOIs
  3. `paper/paper.md` submission date and version string match the PyPI release version in `pyproject.toml`
  4. The Docker smoke test (`make docker-smoke`) completes without network access and produces `features.parquet`, `manifest.json`, and `report.json` from the synthetic demo data
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5
Note: Phase 4 depends on Phase 1 only; it can begin after Phase 1 completes. Phase 5 depends on Phases 2, 3, and 4.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Hardening | 0/3 | Planned    |  |
| 2. Sensitivity Analysis | 3/3 | Complete   | 2026-03-28 |
| 3. Model Validation | 3/3 | Complete   | 2026-03-31 |
| 4. H3 Export | 3/3 | Complete   | 2026-04-04 |
| 5. Paper and JOSS Submission | 0/TBD | Not started | - |
