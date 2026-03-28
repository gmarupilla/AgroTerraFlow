---
phase: 02-sensitivity-analysis
plan: 02
subsystem: sensitivity-engine
tags: [SALib, sobol, morris, sensitivity-analysis, salib-1.5, numpy, rich]

# Dependency graph
requires:
  - 02-01 (SensitivityConfig models, sensitivity.py stub, SALib>=1.5 dependency)
provides:
  - run_sensitivity() function implementing Sobol' and Morris methods via SALib 1.5
  - sensitivity_report.json written atomically with sobol and/or morris blocks
  - Ranked parameter tables printed to stdout via rich.table.Table
  - 7 passing tests covering SENS-01, SENS-02, SENS-03
affects: [02-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SALib 1.5 API: SALib.sample.sobol (not deprecated saltelli), Morris analyze() requires X as 2nd arg
    - Vectorized model evaluator using param_values @ fixed dot product — avoids ModelParams weight-sum validator
    - Atomic JSON write using tempfile.NamedTemporaryFile + Path.replace() (consistent with pipeline.py)
    - Late import of SALib inside functions (_run_sobol, _run_morris) to keep module importable even if SALib not installed
    - Rich tables imported inside _print_* functions to minimize import cost

key-files:
  created: [tests/test_sensitivity.py]
  modified: [terraflow/sensitivity.py]

key-decisions:
  - "Vectorized dot product evaluator (param_values @ fixed) used instead of ModelParams construction — avoids weight-sum validator rejection of sensitivity sweep samples"
  - "Morris n_trajectories = max(4, min(n_samples // 10, 50)) — reasonable default since n_samples is Sobol' base count, not Morris trajectory count"
  - "seed=42 fixed in both sample and analyze calls for full reproducibility of sensitivity results across runs"
  - "model evaluator uses midpoint of normalization bounds as fixed inputs — represents a typical cell; sensitivity measures weight influence, not input data influence"

# Metrics
duration: 4min
completed: 2026-03-28
---

# Phase 02 Plan 02: Sensitivity Analysis Engine Summary

**Sobol' and Morris sensitivity analysis engine implemented in terraflow/sensitivity.py using SALib 1.5; sensitivity_report.json written atomically; 7 tests all pass at 87.69% total coverage**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-28T02:10:57Z
- **Completed:** 2026-03-28T02:14:36Z
- **Tasks:** 2 (TDD: 1 RED commit + 1 GREEN commit)
- **Files modified:** 2

## Accomplishments

- Created `tests/test_sensitivity.py` with 7 test functions covering all SENS-01/SENS-02/SENS-03 requirements (TDD RED phase)
- Implemented full `terraflow/sensitivity.py` replacing the stub:
  - `_build_problem()` converts SensitivityConfig to SALib problem dict
  - `_evaluate_model()` vectorized evaluator using `param_values @ fixed` dot product — avoids ModelParams weight-sum validator entirely
  - `_run_sobol()` uses `SALib.sample.sobol` (not deprecated `saltelli`), seed=42 for reproducibility
  - `_run_morris()` uses `morris_analyze(problem, X, Y, ...)` with X as 2nd arg (critical correctness)
  - `_atomic_write_json()` uses tempfile+rename pattern consistent with pipeline.py
  - `_print_sobol_table()` and `_print_morris_table()` output ranked tables via rich
  - `run_sensitivity()` orchestrates loading, analysis, writing, and printing; raises ValueError for missing sensitivity config

## Task Commits

1. **Task 1: Create test_sensitivity.py (RED phase)** - `5d1919d` (test)
2. **Task 2: Implement sensitivity.py (GREEN phase)** - `338a030` (feat)

## Files Created/Modified

- `tests/test_sensitivity.py` - 7 test functions with shared fixture; n_samples=64 for speed
- `terraflow/sensitivity.py` - Full 287-line implementation replacing 7-line stub

## Decisions Made

- Vectorized dot product evaluator (`param_values @ fixed`) avoids ModelParams construction — the weight-sum validator rejects sensitivity sweep samples that don't sum to 1.0
- Morris trajectory count derived as `max(4, min(n_samples // 10, 50))` — appropriate since n_samples is a Sobol' base count concept; Morris uses trajectory count
- Fixed `seed=42` in both SALib sample and analyze calls for reproducible sensitivity indices across runs
- Model evaluator uses midpoint of each normalization range as "typical" fixed input values — sensitivity measures weight influence holding cell values constant

## Verification Results

```
tests/test_sensitivity.py::test_sobol_produces_s1_st PASSED
tests/test_sensitivity.py::test_sobol_index_bounds PASSED
tests/test_sensitivity.py::test_morris_produces_mu_star PASSED
tests/test_sensitivity.py::test_report_json_schema PASSED
tests/test_sensitivity.py::test_report_written_to_output_dir PASSED
tests/test_sensitivity.py::test_method_both_produces_sobol_and_morris PASSED
tests/test_sensitivity.py::test_missing_sensitivity_section_raises PASSED
7 passed in 3.70s

Combined suite: 168 passed, 2 skipped at 87.69% coverage (>= 85% threshold)
sensitivity.py coverage: 97%
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. `run_sensitivity()` is fully implemented and wired. All report fields are populated from actual SALib analysis results.

## Next Phase Readiness

- Plan 03 (CLI integration and `--sensitivity` flag finalization) can now call `run_sensitivity()` from `terraflow sensitivity -c config.yml`
- `sensitivity_report.json` schema is stable: `schema_version`, `method`, `n_samples`, `parameters`, `bounds`, `sobol`/`morris` blocks with full ranking arrays
- SALib 1.5 API usage is correct: `SALib.sample.sobol` (not saltelli), Morris analyze with X matrix

---
*Phase: 02-sensitivity-analysis*
*Completed: 2026-03-28*
