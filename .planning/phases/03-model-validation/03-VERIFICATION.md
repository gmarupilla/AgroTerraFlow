---
phase: 03-model-validation
verified: 2026-03-31T23:45:00Z
status: passed
score: 11/11 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 7/11
  gaps_closed:
    - "User can run `terraflow validate -c config.yml` from the CLI"
    - "CLI exits 1 with clear error if config has no validation section"
    - "demo_config.yml includes a validation section with reference_csv pointing to synthetic_reference.csv"
    - "Notebook demonstrates the validation workflow with explanatory text"
    - "run_validation is exported from the terraflow public API"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "End-to-end validate command against real pipeline output"
    expected: "`terraflow validate -c examples/demo_config.yml` exits 0; report.json in the latest run dir contains a `validation` key with `cohen_kappa`, `morans_i_residuals`, `mean_fold_accuracy`, and `kriging_loocv_rmse` populated."
    why_human: "Requires a prior `terraflow run` output with real features.parquet; synthetic raster fixture would be needed for a fully automated check."
---

# Phase 3: Model Validation Verification Report

**Phase Goal:** Implement and wire model validation — spatial block CV, Cohen's kappa, Moran's I — with CLI subcommand, demo notebook, and all VALD requirements satisfied.
**Verified:** 2026-03-31T23:45:00Z
**Status:** passed
**Re-verification:** Yes — after cherry-picking feat(03-03) commits onto main branch

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | report.json contains kriging_loocv key with per-variable RMSE when kriging is used | VERIFIED | pipeline.py line 677-683: dict comprehension extracts per_variable RMSE under `report["kriging_loocv"]`; `interpolation_cv` retained on line 683 |
| 2 | interpolation_cv key retained for backward compatibility | VERIFIED | pipeline.py line 683: `report["interpolation_cv"] = interpolator.cv_metrics` |
| 3 | ValidationConfig Pydantic model exists with correct fields and defaults | VERIFIED | config.py line 235: `class ValidationConfig(BaseModel)`; PipelineConfig line 274 adds `validation: Optional[ValidationConfig] = None` |
| 4 | Synthetic reference CSV exists with lat, lon, label columns covering demo ROI | VERIFIED | examples/synthetic_reference.csv: 30 rows, headers {lat, lon, label}, coords lat 38-40 lon -101 to -94 |
| 5 | terraflow/validation.py implements all 4 private functions and run_validation | VERIFIED | 353-line module: `_assign_block_ids`, `_spatial_block_cv`, `_compute_kappa`, `_morans_i`, `run_validation` all present and substantive |
| 6 | All 9 validation tests pass | VERIFIED | `pytest tests/test_validation.py -x -q`: 9 passed |
| 7 | User can run `terraflow validate -c config.yml` from the CLI | VERIFIED | cli.py lines 70-91: `@app.command("validate")` and `def validate_cmd(` present with late import pattern |
| 8 | CLI exits 1 with clear error if config has no validation section | VERIFIED | validate_cmd catches ValueError → SystemExit(1); `pytest -k validate` selects 2 tests, both pass; spot-check confirms exit_code=1 with clear stderr message |
| 9 | demo_config.yml includes validation section with reference_csv | VERIFIED | examples/demo_config.yml lines 52-55: `validation:` block with `n_blocks_side: 4`, `buffer_deg: 0.5`, `reference_csv: "synthetic_reference.csv"` |
| 10 | Notebook demonstrates validation workflow with explanatory text | VERIFIED | notebooks/03_model_validation.ipynb: nbformat=4, 6 cells (3 code, 3 markdown), contains run_validation call, kappa interpretation, Roberts et al. 2017 citation, deterministic-model caveat |
| 11 | run_validation exported from terraflow public API | VERIFIED | `from terraflow import run_validation` succeeds; `__init__.py` line 13: `from .validation import run_validation`; `__all__` line 28: `"run_validation"` present |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `terraflow/pipeline.py` | kriging_loocv key in report dict | VERIFIED | Lines 677-683: dict comprehension + interpolation_cv retained |
| `terraflow/config.py` | ValidationConfig Pydantic model | VERIFIED | Lines 235-248: class with n_blocks_side=4, buffer_deg=0.5, reference_csv=None |
| `examples/synthetic_reference.csv` | 30-row bundled reference dataset | VERIFIED | 30 rows, lat/lon/label, within demo ROI |
| `tests/test_validation.py` | 9-test scaffold, all green | VERIFIED | 9 tests pass; TestSpatialBlockCV, TestCohensKappa, TestMoransI, TestReportValidationBlock present |
| `terraflow/validation.py` | Full module: 5 functions, 150+ lines | VERIFIED | 353 lines; all 5 functions substantive; GroupKFold, cohen_kappa_score, KDTree, cdist all imported and used |
| `terraflow/cli.py` | validate subcommand | VERIFIED | Lines 70-91: `@app.command("validate")`, `def validate_cmd(`, late import, ValueError + Exception handling with SystemExit(1) |
| `examples/demo_config.yml` | validation: section | VERIFIED | Lines 52-55: validation block with correct field values; reference_csv points to synthetic_reference.csv |
| `notebooks/03_model_validation.ipynb` | 5+ cell demo notebook | VERIFIED | 6 cells, valid nbformat=4 JSON; contains run_validation, kappa interpretation, Roberts et al. 2017 citation |
| `terraflow/__init__.py` | run_validation in __all__ | VERIFIED | Line 13: `from .validation import run_validation`; line 28: `"run_validation"` in __all__ |
| `tests/test_cli.py` | TestValidateCLI class | VERIFIED | Lines 387-409: `class TestValidateCLI` with `test_validate_missing_config_section` and `test_validate_help`; both pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `terraflow/pipeline.py` | `interpolator.cv_metrics` | dict comprehension extracting per_variable RMSE | WIRED | Line 678-683: `per_variable` dict extraction with None guard; backward compat line intact |
| `terraflow/config.py` | `PipelineConfig` | `Optional[ValidationConfig]` field | WIRED | Line 274: `validation: Optional[ValidationConfig] = None` mirrors SensitivityConfig pattern |
| `terraflow/validation.py` | `sklearn.model_selection.GroupKFold` | import and use in `_spatial_block_cv` | WIRED | Line 16 import; line 102 instantiation; line 105 split call |
| `terraflow/validation.py` | `sklearn.metrics.cohen_kappa_score` | import and use in `_compute_kappa` | WIRED | Line 15 import; line 171 call |
| `terraflow/validation.py` | `report.json` | atomic read-modify-write in `run_validation` | WIRED | Lines 324-350: reads existing report.json, sets `report["validation"]`, writes via `_atomic_write_json` |
| `terraflow/cli.py` | `terraflow/validation.py` | late import of `run_validation` in `validate_cmd` | WIRED | cli.py line 81: `from .validation import run_validation` inside validate_cmd body |
| `examples/demo_config.yml` | `examples/synthetic_reference.csv` | `reference_csv` field | WIRED | demo_config.yml line 55: `reference_csv: "synthetic_reference.csv"`; examples/synthetic_reference.csv confirmed present |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `terraflow/validation.py` run_validation | `df` (features DataFrame) | `pd.read_parquet(features_path)` from latest run dir | Yes — reads live parquet from pipeline output | FLOWING |
| `terraflow/validation.py` run_validation | `kappa` | `_compute_kappa(df, reference_df)` via `cohen_kappa_score` | Yes — KDTree nearest-neighbor + sklearn computation | FLOWING |
| `terraflow/validation.py` run_validation | `fold_accs` | `_spatial_block_cv` with GroupKFold + cdist buffer | Yes — non-trivial per-fold accuracy from majority-label baseline | FLOWING |
| `terraflow/validation.py` run_validation | `morans_i_val` | `_morans_i(lats, lons, scores - mean)` | Yes — Cliff & Ord formula, returns None on degeneracy | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ValidationConfig importable with correct defaults | `python -c "from terraflow.config import ValidationConfig; v = ValidationConfig(); assert v.n_blocks_side == 4"` | Passes | PASS |
| validation module imports all 5 functions | `python -c "from terraflow.validation import run_validation, _assign_block_ids, _spatial_block_cv, _compute_kappa, _morans_i; print('OK')"` | "imports OK" | PASS |
| 9 validation tests pass | `pytest tests/test_validation.py -x -q` | 9 passed | PASS |
| Full test suite (no regressions) | `pytest tests/ -x -q` | 182 passed, 2 skipped | PASS |
| run_validation in public API | `python -c "from terraflow import run_validation"` | import OK | PASS |
| validate CLI subcommand present | `grep "def validate_cmd" terraflow/cli.py` | match found line 71 | PASS |
| CLI validate tests exist and pass | `pytest tests/test_cli.py -k validate` | 2 passed | PASS |
| demo_config.yml has validation section | `grep "validation:" examples/demo_config.yml` | match found line 52 | PASS |
| Demo notebook exists and valid | `python -c "import json; nb=json.load(open('notebooks/03_model_validation.ipynb')); assert nb['nbformat']==4; assert len(nb['cells'])>=5"` | 6 cells OK | PASS |
| validate --help shows subcommand | `runner.invoke(app, ['validate', '--help'])` | exit_code=0, shows usage | PASS |
| validate exits 1 on bad config | `runner.invoke(app, ['validate', '-c', minimal_no_section_cfg])` | exit_code=1, clear stderr | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| VALD-01 | 03-01, 03-02, 03-03 | Spatial block CV with buffer-zone excluded folds (Roberts et al. 2017) | SATISFIED | `_spatial_block_cv` in validation.py: GroupKFold + cdist buffer exclusion; 9 tests green |
| VALD-02 | 03-02, 03-03 | Cohen's kappa vs reference classification | SATISFIED | `_compute_kappa` in validation.py: KDTree nearest-neighbor + cohen_kappa_score; test_kappa_* tests green |
| VALD-03 | 03-01, 03-03 | kriging LOOCV RMSE exposed in report.json | SATISFIED | pipeline.py line 678: `report["kriging_loocv"]` dict comprehension with per-variable RMSE floats |
| VALD-04 | 03-02, 03-03 | report.json validation block with kappa, CV metrics, LOOCV RMSE; user-accessible via CLI | SATISFIED | `run_validation()` writes complete validation block to report.json; `terraflow validate -c config.yml` is registered, functional, and documented in demo_config.yml and demo notebook |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `terraflow/validation.py` | 332 | `report = {}` (fallback when report.json absent) | Info | Graceful fallback — not a stub; only triggers when validation is run before a pipeline run, in which case FileNotFoundError fires first via the run_dirs check |

No TODO/FIXME/placeholder comments found in any phase-3 artifacts. No empty handlers or return-null stubs detected in cli.py additions, validation.py, pipeline.py, or __init__.py changes. No hardcoded empty props in notebook cells.

---

### Human Verification Required

#### 1. End-to-End validate command against real pipeline output

**Test:** After a successful `terraflow run -c examples/demo_config.yml`, run `terraflow validate -c examples/demo_config.yml` from the repo root.
**Expected:** Command exits 0; `report.json` in the latest run dir contains a `validation` key with `cohen_kappa`, `morans_i_residuals`, `mean_fold_accuracy`, and `kriging_loocv_rmse` populated with non-null numeric values.
**Why human:** Requires a prior `terraflow run` output with real features.parquet; cannot be exercised without real raster/climate inputs or a full synthetic fixture pipeline.

---

### Summary

All 11 observable truths now verified. The five gaps from the initial verification were closed by cherry-picking the feat(03-03) commits onto the main branch:

- `terraflow/cli.py` — `@app.command("validate")` / `validate_cmd` present, using late import and proper error handling
- `terraflow/__init__.py` — `run_validation` imported and listed in `__all__`
- `examples/demo_config.yml` — `validation:` section added with correct fields pointing to `synthetic_reference.csv`
- `notebooks/03_model_validation.ipynb` — 6-cell notebook (nbformat=4) with code, interpretation, and Roberts et al. 2017 citation
- `tests/test_cli.py` — `TestValidateCLI` class with 2 passing tests

The full test suite (182 passed, 2 skipped) confirms no regressions. All four VALD requirements are now fully satisfied, including the user-facing CLI surface of VALD-04 which was the only remaining partial item.

---

_Verified: 2026-03-31T23:45:00Z_
_Verifier: Claude (gsd-verifier)_
