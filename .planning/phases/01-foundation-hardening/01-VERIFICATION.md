---
phase: 01-foundation-hardening
verified: 2026-03-27T00:00:00Z
status: passed
score: 4/4 must-haves verified
gaps: []
human_verification:
  - test: "Install terraflow without viz extra and confirm plotly is absent"
    expected: "pip install terraflow; python -c 'import plotly' raises ImportError"
    why_human: "Cannot uninstall packages in the active dev environment during verification"
---

# Phase 01: Foundation Hardening Verification Report

**Phase Goal:** The pipeline surface visible to JOSS reviewers is free of broad exception handlers and missing diagnostics — CRS mismatches produce informative errors, kriging diagnostics appear in report.json, and test coverage closes the MC uncertainty gap
**Verified:** 2026-03-27
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running the pipeline with mismatched/None raster CRS raises `CRSMismatchError` with both CRS strings in the message, not a bare `Exception` | VERIFIED | `terraflow/exceptions.py` defines `CRSMismatchError(CRSError)`; `pipeline.py` lines 417-428 raise it for both None CRS and incompatible CRS, embedding both CRS strings; test passes with `match="has no CRS"` |
| 2 | `report.json` includes a `kriging_diagnostics` block with `nugget`, `sill`, `range_`, and `model` fields when kriging is used | VERIFIED | `climate.py` lines 364-371 populate `variogram_params` dict with all 6 fields; `pipeline.py` lines 720-721 write it to report; `test_kriging_diagnostics_in_report` passes asserting all keys |
| 3 | Test suite passes with >=85% branch coverage including kriging fallback, MC zero-variance, and MC single-sample edge cases | VERIFIED | 160 passed, 2 skipped; 87.20% branch coverage; all 5 targeted new tests pass individually and in suite |
| 4 | `pip install terraflow` does not pull in plotly; `pip install terraflow[viz]` installs plotly; `pyproject.toml` has trove classifiers and Documentation URL | VERIFIED | `pyproject.toml`: plotly absent from `dependencies`, present only under `[project.optional-dependencies] viz`; 9 trove classifiers present; `Documentation = "https://gmarupilla.github.io/AgroTerraFlow/"` present |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Optional viz dep, trove classifiers, Documentation URL | VERIFIED | `viz = ["plotly>=5.0.0"]` under optional-deps; 9 classifiers including `Topic :: Scientific/Engineering :: GIS`; Documentation URL present; plotly absent from core deps |
| `terraflow/viz.py` | Plotly import guard with `_PLOTLY_AVAILABLE` flag | VERIFIED | try/except guard at lines 7-11; `_PLOTLY_AVAILABLE` set True or False; `if not _PLOTLY_AVAILABLE: raise ImportError(...)` at line 60 with pip install hint |
| `terraflow/exceptions.py` | `CRSMismatchError` subclassing `pyproj.exceptions.CRSError` | VERIFIED | File exists; `class CRSMismatchError(CRSError)` at line 6; `from pyproj.exceptions import CRSError` import confirmed; `issubclass(CRSMismatchError, CRSError)` returns True |
| `terraflow/pipeline.py` | CRS validation guard + kriging_diagnostics in report builder | VERIFIED | CRS guard at lines 414-428 (None check + incompatible check); `kriging_diagnostics` write at lines 720-721; wired via `from .exceptions import CRSMismatchError` import |
| `terraflow/climate.py` | `variogram_params` dict from full-data PyKrige fit | VERIFIED | `self.variogram_params: dict = {}` at line 190; populated at lines 364-371 with model, psill, nugget, sill, range_, range_units after full OrdinaryKriging fit |
| `tests/conftest.py` | `synthetic_climate_csv_sparse` fixture (2 stations) | VERIFIED | Fixture at line 87; creates 2-row DataFrame with lat, lon, mean_temp, total_rain; correctly below MIN_KRIGING_STATIONS |
| `tests/test_climate.py` | `test_kriging_fallback_sparse_stations` | VERIFIED | Defined at line 858; asserts `interpolator.interpolation_method == "linear"` after sparse data init; passes |
| `tests/test_uncertainty.py` | `test_mc_zero_variance_ci_collapsed` and `test_mc_single_sample_ci_width_zero` | VERIFIED | Both in `TestMCEdgeCases` class at lines 405 and 439; zero-variance uses monkeypatch to zero `_krig_std` columns; single-sample uses `uncertainty_samples=1`; both pass |
| `tests/test_pipeline.py` | `test_crs_mismatch_error_none_crs` and `test_kriging_diagnostics_in_report` | VERIFIED | Both defined at lines 293 and 311; CRS test uses `pytest.raises(CRSMismatchError, match="has no CRS")`; diagnostics test asserts all 6 keys; both pass |
| `tests/test_viz.py` | `pytest.importorskip("plotly")` guard | VERIFIED | `pytest.importorskip("plotly")` at line 6 as first executable line |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml` | `terraflow/viz.py` | plotly removed from core deps; viz.py guards import | VERIFIED | `viz = ["plotly>=5.0.0"]` in optional-deps; viz.py has `_PLOTLY_AVAILABLE` guard |
| `tests/test_viz.py` | `terraflow/viz.py` | `pytest.importorskip("plotly")` | VERIFIED | `pytest.importorskip("plotly")` at line 6; `from terraflow.viz import plot_suitability_scatter` at line 10 |
| `terraflow/pipeline.py` | `terraflow/exceptions.py` | `from .exceptions import CRSMismatchError` | VERIFIED | Import at line 42/49 (duplicate found — see anti-patterns); raise sites at lines 418 and 425 |
| `terraflow/pipeline.py` | `terraflow/climate.py` | reads `interpolator.variogram_params` to build kriging_diagnostics | VERIFIED | `if interpolator.variogram_params:` at line 720; `report["kriging_diagnostics"] = interpolator.variogram_params` at line 721 |
| `terraflow/climate.py` | pykrige | reads `ok.variogram_model_parameters` after full-data fit | VERIFIED | `_ok_full = OrdinaryKriging(...)` at line 357; `p = _ok_full.variogram_model_parameters` at line 363; dict built from p at lines 364-371 |
| `tests/test_climate.py` | `terraflow/climate.py` | `ClimateInterpolator` with sparse data triggers fallback branch | VERIFIED | Imports `ClimateInterpolator, MIN_KRIGING_STATIONS`; creates 2-row sparse_df; asserts fallback to `"linear"` |
| `tests/test_pipeline.py` | `terraflow/exceptions.py` | `pytest.raises(CRSMismatchError)` on None-CRS raster | VERIFIED | `from terraflow.exceptions import CRSMismatchError` in test body; `pytest.raises(CRSMismatchError, match="has no CRS")` passes |
| `tests/test_pipeline.py` | `terraflow/pipeline.py` | kriging_diagnostics verified in report.json output | VERIFIED | `run_pipeline(cfg_path)` called; report.json read; `"kriging_diagnostics" in report` asserted; all 6 keys checked |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `terraflow/climate.py` | `variogram_params` | `OrdinaryKriging.variogram_model_parameters` from PyKrige full-data fit | Yes — real kriging model parameters extracted from station data | FLOWING |
| `terraflow/pipeline.py` | `kriging_diagnostics` in report | `interpolator.variogram_params` (non-empty only when kriging ran) | Yes — conditional write; test confirms non-empty dict in report.json | FLOWING |
| `terraflow/pipeline.py` | `CRSMismatchError` message | `raster.crs` value (None or incompatible string) | Yes — raster CRS read from file, embedded in message string | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `CRSMismatchError` subclasses `pyproj.exceptions.CRSError` | `python -c "from terraflow.exceptions import CRSMismatchError; from pyproj.exceptions import CRSError; assert issubclass(CRSMismatchError, CRSError); print('PASS')"` | `CRSMismatchError inherits CRSError: PASS` | PASS |
| kriging fallback test | `pytest tests/test_climate.py -x -q -k kriging_fallback` | `2 passed, 44 deselected in 1.29s` | PASS |
| CRS mismatch + kriging diagnostics tests | `pytest tests/test_pipeline.py -x -q -k "crs_mismatch or kriging_diagnostics"` | `2 passed, 5 deselected in 2.06s` | PASS |
| MC edge case tests | `pytest tests/test_uncertainty.py -x -q -k "zero_variance or single_sample"` | `2 passed, 13 deselected in 3.14s` | PASS |
| Full suite with branch coverage | `pytest tests/ --cov=terraflow --cov-branch -q` | `160 passed, 2 skipped; 87.20% branch coverage; Required 85.0% reached` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|----------|
| HARD-01 | 01-02, 01-03 | Pipeline raises `pyproj.CRSError` with informative message including both CRS strings | SATISFIED | `CRSMismatchError(CRSError)` in exceptions.py; guard in pipeline.py lines 417-428 with CRS strings in both messages; test passes |
| HARD-02 | 01-03 | Test suite covers kriging fallback, zero-variance MC, single-sample MC | SATISFIED | All 5 tests implemented and passing: `test_kriging_fallback_sparse_stations`, `test_mc_zero_variance_ci_collapsed`, `test_mc_single_sample_ci_width_zero`, `test_crs_mismatch_error_none_crs`, `test_kriging_diagnostics_in_report` |
| HARD-03 | 01-02, 01-03 | `report.json` includes variogram diagnostics block with nugget, sill, range, model when kriging used | SATISFIED | `variogram_params` dict in climate.py; `kriging_diagnostics` written in pipeline.py; test verifies all 6 keys in report.json |
| HARD-04 | 01-01 | plotly optional `[viz]` extra; trove classifiers; Documentation URL | SATISFIED | `viz = ["plotly>=5.0.0"]` in pyproject.toml optional-deps; 9 trove classifiers; Documentation URL present |

**REQUIREMENTS.md tracking discrepancy:** HARD-02 is still marked `[ ]` (pending) in REQUIREMENTS.md and the traceability table shows "Pending" for HARD-02, but the implementation and tests are fully complete. The checkbox was not updated when plan 01-03 completed. This is a documentation-only gap — the code fully satisfies the requirement.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `terraflow/pipeline.py` | 34, 38 | Duplicate `from pyproj.exceptions import CRSError as _PyProjCRSError` import | Info | No runtime impact; cleanup candidate |
| `terraflow/pipeline.py` | 42, 49 | Duplicate `from .exceptions import CRSMismatchError` import | Info | No runtime impact; cleanup candidate |

No blocker or warning anti-patterns. The duplicate imports are cosmetic issues that do not affect correctness or JOSS review surface.

### Human Verification Required

#### 1. Clean install without plotly

**Test:** Create a fresh virtual environment, run `pip install terraflow-agro` (or `pip install -e . --no-extras`), then `python -c "import plotly"`.
**Expected:** `ModuleNotFoundError` — plotly is not installed.
**Why human:** Cannot uninstall packages from the active development environment during automated verification without disrupting the dev setup.

#### 2. `pip install terraflow[viz]` installs plotly

**Test:** In the same fresh venv, run `pip install 'terraflow-agro[viz]'`, then `python -c "import plotly; print(plotly.__version__)"`.
**Expected:** Plotly version string prints without error.
**Why human:** Requires a clean venv to verify the optional dependency resolves correctly.

### Gaps Summary

No implementation gaps. All four success criteria are met by real, wired, tested code.

One tracking issue: REQUIREMENTS.md still shows HARD-02 as `[ ]` pending — the checkbox and traceability table should be updated to mark it complete. This does not affect the phase goal or code correctness.

---

_Verified: 2026-03-27_
_Verifier: Claude (gsd-verifier)_
