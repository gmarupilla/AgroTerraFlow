---
phase: 02-sensitivity-analysis
plan: 03
subsystem: cli
tags: [typer, SALib, sensitivity-analysis, integration-tests, error-handling]

# Dependency graph
requires:
  - 02-01 (Typer CLI foundation with sensitivity_cmd stub, SensitivityConfig models)
  - 02-02 (run_sensitivity() implementation with Sobol/Morris engine)
provides:
  - sensitivity_cmd with ValueError/Exception error handling (exit code 1)
  - 3 CLI integration tests: success path, non-power-of-2 error, missing section error
  - examples/demo_config.yml sensitivity: section for documentation and end-to-end demo
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - CLI error handling: sensitivity_cmd mirrors run_cmd pattern (ValueError -> exit 1, Exception -> exit 1)
    - CLI integration tests use patch.object(sys, 'argv') with pytest.raises(SystemExit) for Typer standalone mode

key-files:
  created: []
  modified: [terraflow/cli.py, tests/test_cli.py, examples/demo_config.yml]

key-decisions:
  - "sensitivity_cmd catches ValueError (from power-of-2 and missing sensitivity section) and general Exception, both exit 1 with stderr message"
  - "test_sensitivity_cmd_success asserts exit code 0 and sensitivity_report.json exists (Typer standalone exits 0)"

patterns-established:
  - "Sensitivity CLI error pattern: ValueError -> 'ERROR: {e}' to stderr + exit 1; Exception -> 'ERROR: Sensitivity analysis failed - {e}' to stderr + exit 1"

requirements-completed: [SENS-04]

# Metrics
duration: 3min
completed: 2026-03-28
---

# Phase 02 Plan 03: Sensitivity CLI Integration Summary

**sensitivity_cmd wired with full error handling; 3 CLI integration tests cover success, power-of-2 validation, and missing section; examples/demo_config.yml documents sensitivity usage**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-28T02:25:00Z
- **Completed:** 2026-03-28T02:29:07Z
- **Tasks:** 1 (Task 2 is human-verify checkpoint)
- **Files modified:** 3

## Accomplishments

- Updated `sensitivity_cmd` in `terraflow/cli.py` to match `run_cmd` error handling: catches `ValueError` (invalid n_samples, missing sensitivity section) and bare `Exception`, both print to stderr and exit 1
- Added 3 CLI integration tests to `tests/test_cli.py`:
  - `test_sensitivity_cmd_success`: runs full Sobol+Morris analysis, asserts exit 0 and `sensitivity_report.json` exists
  - `test_sensitivity_nonpower_of_two`: n_samples=100 rejects with "power of 2" in stderr and exit 1
  - `test_sensitivity_missing_section`: config without sensitivity: block produces "sensitivity" in stderr and exit 1
- Appended `sensitivity:` section to `examples/demo_config.yml` with n_samples=1024, method=both for end-to-end demo

## Task Commits

1. **Task 1: Wire sensitivity CLI with error handling, add CLI tests, update example config** - `965d93f` (feat)

## Files Created/Modified

- `terraflow/cli.py` - Added try/except to sensitivity_cmd matching run_cmd error handling pattern
- `tests/test_cli.py` - Added test_sensitivity_cmd_success, test_sensitivity_nonpower_of_two, test_sensitivity_missing_section
- `examples/demo_config.yml` - Appended sensitivity: section with w_v/w_t/w_r bounds, n_samples=1024, method=both

## Verification Results

```
tests/test_cli.py::test_sensitivity_cmd_success PASSED
tests/test_cli.py::test_sensitivity_nonpower_of_two PASSED
tests/test_cli.py::test_sensitivity_missing_section PASSED
All 19 test_cli.py + test_sensitivity.py tests PASSED
Full suite: 171 passed, 2 skipped at 87.83% coverage (>= 85% threshold)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. `sensitivity_cmd` calls `run_sensitivity()` which is fully implemented. All paths write actual SALib analysis results.

## Human Verification Checkpoint (Task 2)

Task 2 is a blocking `checkpoint:human-verify`. Human must verify:
1. `terraflow --help` shows run and sensitivity subcommands
2. `terraflow sensitivity -c examples/demo_config.yml` runs (or similar config with real data)
3. Ranked table appears in stdout with S1/ST columns (Sobol') and mu* columns (Morris)
4. `sensitivity_report.json` is written to the configured output_dir
5. Non-power-of-2 n_samples produces clear "power of 2" error with exit 1
6. Full test suite passes: `pytest --cov=terraflow --cov-report=term-missing --cov-fail-under=85`

---
*Phase: 02-sensitivity-analysis*
*Completed: 2026-03-28*
