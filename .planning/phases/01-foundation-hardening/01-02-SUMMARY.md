---
phase: 01-foundation-hardening
plan: 02
subsystem: core-pipeline
tags: [crs, error-handling, kriging, diagnostics, report-json]
requirements: [HARD-01, HARD-03]

dependency_graph:
  requires: []
  provides: [CRSMismatchError, kriging_diagnostics_in_report]
  affects: [terraflow/exceptions.py, terraflow/pipeline.py, terraflow/climate.py]

tech_stack:
  added: []
  patterns:
    - pyproj.exceptions.CRSError subclassing for domain-specific CRS errors
    - Full-data PyKrige OrdinaryKriging fit for variogram parameter extraction

key_files:
  created:
    - terraflow/exceptions.py
  modified:
    - terraflow/pipeline.py
    - terraflow/climate.py

decisions:
  - "CRSMismatchError subclasses pyproj.exceptions.CRSError so callers can catch either the specific or base CRS error"
  - "variogram_params extracted from a full-data OrdinaryKriging fit (not the LOOCV sub-fits) to get stable parameter estimates"
  - "range_units field set to degrees_geographic to document the coordinate-system limitation for JOSS reviewers"

metrics:
  duration_minutes: 8
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
  completed_date: "2026-03-27"
---

# Phase 1 Plan 2: CRS Error Hardening and Kriging Diagnostics Summary

**One-liner:** CRSMismatchError with informative messages replaces broad exception handling; kriging variogram parameters (psill, nugget, sill, range_, model) surfaced in report.json.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create CRSMismatchError and add CRS guard to pipeline.py | 98d4968 | terraflow/exceptions.py, terraflow/pipeline.py |
| 2 | Surface kriging variogram diagnostics in report.json | 07954b4 | terraflow/climate.py, terraflow/pipeline.py |

## What Was Built

**Task 1 — CRSMismatchError:**
- Created `terraflow/exceptions.py` with `CRSMismatchError(CRSError)` — a domain-specific exception subclassing `pyproj.exceptions.CRSError`, allowing callers to catch it as either `CRSMismatchError` or `CRSError`
- Added CRS validation guard in `pipeline.py` immediately after raster load, before any coordinate reprojection:
  - Raises `CRSMismatchError` with raster path and CRS strings when `raster.crs` is `None`
  - Raises `CRSMismatchError` naming both CRS strings when `Transformer.from_crs` fails due to incompatible CRS
  - Added `from pyproj.exceptions import CRSError as _PyProjCRSError` import to enable precise exception handling

**Task 2 — Kriging diagnostics:**
- Added `self.variogram_params: dict = {}` to `ClimateInterpolator.__init__`
- After variogram model selection in `_init_kriging`, added a full-data `OrdinaryKriging` fit to extract `variogram_model_parameters = [psill, range, nugget]`
- Populated `self.variogram_params` dict with keys: `model`, `psill`, `nugget`, `sill` (= psill + nugget), `range_`, `range_units` (= `"degrees_geographic"`)
- Added `kriging_diagnostics` block to `pipeline.py`'s report.json builder: written when `interpolator.variogram_params` is non-empty

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- `python -c "from terraflow.exceptions import CRSMismatchError; from pyproj.exceptions import CRSError; assert issubclass(CRSMismatchError, CRSError)"` exits 0
- `grep -n 'CRSMismatchError' terraflow/pipeline.py` shows guard code at lines 416 and 423
- `grep -n 'kriging_diagnostics' terraflow/pipeline.py` shows report builder addition at line 719
- `grep -n 'variogram_params' terraflow/climate.py` shows attribute init at line 190 and population at line 364
- `pytest tests/ -x -q` — 155 passed, 2 skipped, 0 failures

## Known Stubs

None.

## Self-Check: PASSED

- `terraflow/exceptions.py` exists with `class CRSMismatchError`
- `terraflow/pipeline.py` contains `from .exceptions import CRSMismatchError` and both `raise CRSMismatchError` sites
- `terraflow/climate.py` contains `self.variogram_params: dict = {}` and `self.variogram_params = {`
- Commits 98d4968 and 07954b4 verified in git log
