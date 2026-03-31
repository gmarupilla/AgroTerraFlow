---
phase: 03-model-validation
plan: 01
subsystem: testing
tags: [kriging, loocv, pydantic, validation, spatial-cv, cohens-kappa, morans-i]

# Dependency graph
requires:
  - phase: 02-sensitivity-analysis
    provides: SensitivityConfig pattern used as template for ValidationConfig
  - phase: 01-foundation-hardening
    provides: kriging cv_metrics structure in interpolator, PipelineConfig base

provides:
  - kriging_loocv key in report.json with per-variable RMSE floats
  - interpolation_cv key retained for backward compatibility
  - ValidationConfig Pydantic model (n_blocks_side, buffer_deg, reference_csv)
  - PipelineConfig optional validation field
  - examples/synthetic_reference.csv (30 rows, lat/lon/label, demo ROI)
  - tests/test_validation.py scaffold (9 tests, Wave 0 RED state)

affects: [03-02, 03-03, report.json consumers, JOSS paper validation section]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ValidationConfig mirrors SensitivityConfig: Optional field in PipelineConfig with ConfigDict(extra='forbid')"
    - "Wave 0 RED scaffolding: deferred imports inside test methods allow collection before module exists"
    - "kriging_loocv dict comprehension filters None RMSE values for clean report output"

key-files:
  created:
    - examples/synthetic_reference.csv
    - tests/test_validation.py
  modified:
    - terraflow/pipeline.py
    - terraflow/config.py

key-decisions:
  - "kriging_loocv is a flat dict {var: rmse_float} for easy JSON consumption; interpolation_cv retains full cv_metrics dict for backward compat"
  - "ValidationConfig placed before PipelineConfig in config.py, following the SensitivityConfig ordering convention"
  - "Synthetic reference CSV coordinates stay within demo ROI (lat 38-40, lon -101 to -94) to be usable in integration tests later"

patterns-established:
  - "Wave 0 RED scaffolding: tests import from not-yet-created module inside test body so file can be collected by pytest"
  - "Optional config submodel pattern: add field to PipelineConfig as Optional[SubConfig] = None"

requirements-completed: [VALD-03]

# Metrics
duration: 10min
completed: 2026-03-31
---

# Phase 3 Plan 01: Validation Infrastructure Summary

**kriging_loocv per-variable RMSE surfaced in report.json, ValidationConfig Pydantic model added to config.py, synthetic reference CSV bundled, and 9-test Wave 0 scaffold created for Plans 02/03**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-31T13:54:00Z
- **Completed:** 2026-03-31T14:04:21Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- pipeline.py now writes `kriging_loocv` (flat dict of per-variable RMSE floats) alongside existing `interpolation_cv` for backward compatibility
- `ValidationConfig` Pydantic model added with `n_blocks_side=4`, `buffer_deg=0.5`, `reference_csv=None` defaults; `PipelineConfig` gains optional `validation` field
- `examples/synthetic_reference.csv` bundled: 30 rows covering demo ROI (lat 38-40, lon -101 to -94) with `low/medium/high` labels for non-trivial kappa
- `tests/test_validation.py` scaffold: 9 tests across `TestSpatialBlockCV`, `TestCohensKappa`, `TestMoransI`, `TestReportValidationBlock` — all fail with `ModuleNotFoundError` (correct Wave 0 RED state)
- Existing test suite: 171 passed, 2 skipped — zero regressions

## Task Commits

1. **Task 1: Surface kriging_loocv in pipeline.py + add ValidationConfig to config.py** - `7189357` (feat)
2. **Task 2: Create synthetic_reference.csv and scaffold test_validation.py** - `073b9d4` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `terraflow/pipeline.py` - Added `kriging_loocv` dict comprehension; retained `interpolation_cv` for compat
- `terraflow/config.py` - Added `ValidationConfig` class; added `validation` field to `PipelineConfig`
- `examples/synthetic_reference.csv` - 30-row bundled reference dataset for VALD-02 kappa testing
- `tests/test_validation.py` - 9-test Wave 0 scaffold covering VALD-01, VALD-02, VALD-04

## Decisions Made

- `kriging_loocv` is a flat `{var: rmse_float}` dict (not nested) for clean, direct JSON consumption by downstream tools and the JOSS paper
- `interpolation_cv` retained as-is so any existing consumers of `report.json` are not broken
- `ValidationConfig` follows the exact same pattern as `SensitivityConfig` — `ConfigDict(extra="forbid")` with `Optional[ValidationConfig] = None` in `PipelineConfig`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (block CV + kappa implementation) can proceed: `ValidationConfig` is in place, test scaffold is ready, reference CSV is bundled
- Plan 03 (Moran's I + report integration) depends on Plan 02 completing
- `terraflow/validation.py` module does not exist yet — Plans 02/03 will create it and turn the 9 RED tests GREEN

---
*Phase: 03-model-validation*
*Completed: 2026-03-31*

## Self-Check: PASSED

- terraflow/pipeline.py: FOUND
- terraflow/config.py: FOUND
- examples/synthetic_reference.csv: FOUND
- tests/test_validation.py: FOUND
- .planning/phases/03-model-validation/03-01-SUMMARY.md: FOUND
- Commit 7189357: FOUND
- Commit 073b9d4: FOUND
