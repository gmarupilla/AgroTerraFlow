---
phase: 02-sensitivity-analysis
plan: 01
subsystem: cli
tags: [typer, SALib, pydantic, sensitivity-analysis, config]

# Dependency graph
requires: []
provides:
  - SALib>=1.5 and typer>=0.12.5 declared in pyproject.toml core dependencies
  - WeightBounds and SensitivityConfig Pydantic models with validators
  - PipelineConfig accepts optional sensitivity: section without extra-field rejection
  - Typer-based CLI with explicit run and sensitivity subcommands
  - terraflow/sensitivity.py stub for safe import before Plan 02 implementation
affects: [02-02, 02-03]

# Tech tracking
tech-stack:
  added: [SALib>=1.5, typer>=0.12.5]
  patterns:
    - Typer subcommand registration with explicit name= string to avoid Typer 0.14+ inference pitfall
    - Late import pattern for sensitivity module (import inside function body) to allow cli.py to load before sensitivity.py is fully implemented
    - PipelineConfig uses Optional field for sensitivity to allow YAML co-habitation without extra="forbid" rejection

key-files:
  created: [terraflow/sensitivity.py]
  modified: [pyproject.toml, terraflow/config.py, terraflow/cli.py, tests/test_cli.py]

key-decisions:
  - "Typer add_completion=False to suppress shell completion prompts on first install"
  - "sensitivity_cmd uses late import (inside function body) so cli.py is importable even when sensitivity.py is a stub"
  - "test_cli_valid_config_runs_pipeline updated to catch SystemExit(0) — Typer standalone mode calls sys.exit(0) on success"

patterns-established:
  - "Typer subcommand: always pass explicit name= string to @app.command() to avoid name inference bugs"
  - "CLI error handling: FileNotFoundError and ValueError exit(1), unexpected Exception exit(1) with Pipeline failed prefix"

requirements-completed: [SENS-04]

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 02 Plan 01: Sensitivity Analysis — Dependencies and CLI Foundation Summary

**SALib>=1.5 and typer>=0.12.5 added to core deps; CLI migrated from argparse to Typer with `run` and `sensitivity` subcommands; SensitivityConfig Pydantic model with power-of-2 validator wired into PipelineConfig**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-28T02:02:00Z
- **Completed:** 2026-03-28T02:07:22Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added SALib>=1.5 and typer>=0.12.5 to pyproject.toml core dependencies (sensitivity is a key paper claim — D-07)
- Created WeightBounds (high>low validator) and SensitivityConfig (power-of-2 n_samples, SENS-04) Pydantic models; PipelineConfig accepts optional `sensitivity:` YAML section
- Replaced argparse CLI with Typer app exposing `run` and `sensitivity` subcommands; old flat `terraflow -c` correctly rejected with exit code 2
- Added terraflow/sensitivity.py stub so `sensitivity_cmd` can be imported safely before Plan 02 implementation
- Updated all 9 CLI tests to use `terraflow run -c` invocations; added `test_cli_old_flat_command_fails`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dependencies and SensitivityConfig models** - `06aa878` (feat)
2. **Task 2: Migrate CLI to Typer and update tests** - `c587302` (feat)

## Files Created/Modified
- `pyproject.toml` - Added SALib>=1.5, typer>=0.12.5 to [project.dependencies]
- `terraflow/config.py` - Added WeightBounds model, SensitivityConfig model, Optional sensitivity field on PipelineConfig
- `terraflow/cli.py` - Complete rewrite from argparse to Typer with run/sensitivity subcommands
- `tests/test_cli.py` - Updated all tests to use subcommand invocations; added test_cli_old_flat_command_fails
- `terraflow/sensitivity.py` - Created stub module with run_sensitivity placeholder (raises NotImplementedError)

## Decisions Made
- `add_completion=False` on Typer app to suppress shell completion setup prompts during install
- `sensitivity_cmd` uses late import (`from .sensitivity import run_sensitivity` inside function body) so cli.py remains importable before sensitivity.py is fully implemented in Plan 02
- `test_cli_valid_config_runs_pipeline` was updated to wrap `main()` in `pytest.raises(SystemExit)` and assert `code == 0` — Typer's standalone mode calls `sys.exit(0)` after a successful command, unlike argparse which returns normally

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_cli_valid_config_runs_pipeline failing due to Typer's sys.exit(0)**
- **Found during:** Task 2 (CLI migration and test updates)
- **Issue:** The test called `main()` without catching `SystemExit`. Typer in standalone mode calls `sys.exit(0)` after a successful command execution, causing pytest to see an unexpected `SystemExit(0)` and fail the test.
- **Fix:** Wrapped `main()` in `pytest.raises(SystemExit)` and asserted `exc_info.value.code == 0` to confirm successful exit.
- **Files modified:** tests/test_cli.py
- **Verification:** `pytest tests/test_cli.py -x -v` all 9 tests pass
- **Committed in:** `c587302` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug)
**Impact on plan:** Necessary for test correctness. Typer's behavior differs from argparse — this is the standard pattern for testing Typer CLIs.

## Issues Encountered
None beyond the Typer sys.exit(0) behavior documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 can now `from .sensitivity import run_sensitivity` and implement the SALib-based sensitivity engine
- `from terraflow.config import SensitivityConfig` is available for loading sensitivity config blocks
- CLI foundation complete: `terraflow sensitivity -c config.yml` will route to `run_sensitivity()` once Plan 02 implements it
- SALib is installed and importable: `import SALib.sample.sobol`, `import SALib.analyze.sobol`

---
*Phase: 02-sensitivity-analysis*
*Completed: 2026-03-28*
