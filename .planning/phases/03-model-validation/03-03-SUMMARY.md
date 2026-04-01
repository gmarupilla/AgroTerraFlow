---
phase: 03-model-validation
plan: "03"
subsystem: cli
tags: [typer, validation, cli, notebook, jupyter, cohen-kappa, spatial-cv]

# Dependency graph
requires:
  - phase: 03-02-model-validation
    provides: run_validation function, spatial block CV, Cohen's kappa, Moran's I
provides:
  - validate CLI subcommand (terraflow validate -c config.yml)
  - ValidationConfig wired into demo_config.yml
  - Model validation demo notebook (notebooks/03_model_validation.ipynb)
  - run_validation exported from terraflow public API
affects: [04-h3-export, 05-paper-joss]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Late import pattern for CLI subcommands: `from .validation import run_validation` inside command body"
    - "CLI error handling: ValueError for config errors exits 1 with stderr message, Exception for runtime errors exits 1"
    - "Path resolution: output_dir and reference_csv resolved relative to config file's parent directory (config_dir / cfg.field)"

key-files:
  created:
    - notebooks/03_model_validation.ipynb
  modified:
    - terraflow/cli.py
    - terraflow/__init__.py
    - examples/demo_config.yml
    - tests/test_cli.py
    - terraflow/validation.py
    - terraflow/config.py

key-decisions:
  - "validate_cmd uses late import (from .validation import run_validation) inside function body, matching sensitivity_cmd pattern"
  - "output_dir and reference_csv in validation.py resolved relative to config file parent directory, not cwd — matches pipeline.py convention"
  - "ValidationConfig missing from config.py worktree fixed as cherry-pick gap correction"

patterns-established:
  - "CLI subcommand pattern: @app.command + late import + ValueError/Exception with SystemExit(1)"
  - "Config path resolution: always use config_dir = config_path.parent, then config_dir / cfg.relative_path"

requirements-completed: [VALD-01, VALD-02, VALD-03, VALD-04]

# Metrics
duration: 45min
completed: 2026-03-31
---

# Phase 3 Plan 03: Model Validation CLI Summary

**`terraflow validate -c config.yml` subcommand wired end-to-end with spatial block CV, Cohen's kappa, and Moran's I surfaced in report.json; demo notebook demonstrates the full workflow.**

## Performance

- **Duration:** ~45 min (including human verification and bug fixes)
- **Started:** 2026-03-31T00:00:00Z
- **Completed:** 2026-03-31
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 7

## Accomplishments

- Wired `validate` CLI subcommand in `terraflow/cli.py` following the `sensitivity_cmd` pattern with late import and dual error handling (ValueError/Exception → SystemExit(1))
- Added `run_validation` to `terraflow/__init__.py` public API and `__all__`
- Added `validation:` section to `examples/demo_config.yml` pointing to `examples/synthetic_reference.csv`
- Added `TestValidateCLI` class to `tests/test_cli.py` covering missing-config-section exit-1 and `--help` cases
- Created `notebooks/03_model_validation.ipynb` with 6 cells: run validation, inspect report block, interpret kappa/Moran's I/fold accuracy, show kriging LOOCV, cite Roberts et al. 2017
- Fixed two bugs found during human verification: `ValidationConfig` missing from config.py worktree (cherry-pick gap) and `validation.py` resolving paths from cwd instead of config file's parent

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire validate CLI subcommand + update demo config + add CLI test** - `441c434` (feat)
2. **Task 2: Create model validation demo notebook** - `c5c6da9` (feat)
3. **Task 3: Human verification — bug fix: re-apply kriging_loocv** - `c8c0529` (fix)
4. **Task 3: Human verification — bug fix: path resolution in validation.py** - `0f81182` (fix)

## Files Created/Modified

- `terraflow/cli.py` - Added `validate_cmd` subcommand with late import, ValueError/Exception handling, SystemExit(1) on error
- `terraflow/__init__.py` - Added `run_validation` to public exports and `__all__`
- `examples/demo_config.yml` - Added `validation:` section with `n_blocks_side: 4`, `buffer_deg: 0.5`, `reference_csv: "synthetic_reference.csv"`
- `tests/test_cli.py` - Added `TestValidateCLI` class with missing-config-section and --help tests
- `notebooks/03_model_validation.ipynb` - 6-cell demo notebook covering full validation workflow with Roberts et al. 2017 citation
- `terraflow/validation.py` - Fixed path resolution: output_dir and reference_csv now resolved relative to config file's parent directory
- `terraflow/config.py` - Fixed cherry-pick gap: `ValidationConfig` and `validation` field re-added to worktree

## Decisions Made

- `validate_cmd` uses late import (`from .validation import run_validation`) inside the function body, matching the established `sensitivity_cmd` pattern and ensuring safe import before the validation module is fully exercised.
- Path resolution bug fixed: `validation.py` was resolving `output_dir` and `reference_csv` from `os.getcwd()`. Fixed to use `config_path.parent / cfg.field`, matching `pipeline.py` convention. This is the canonical pattern for all config-relative paths in TerraFlow.
- `ValidationConfig` was missing from the `config.py` worktree (cherry-pick gap from 03-01 branch work). Re-applied to both the worktree and main branch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ValidationConfig missing from config.py worktree**
- **Found during:** Task 3 (human verification — `terraflow validate` import failure)
- **Issue:** `ValidationConfig` and `validation: Optional[ValidationConfig]` field were missing from `terraflow/config.py` on the working branch due to a cherry-pick gap from the 03-01 feature branch
- **Fix:** Re-applied `ValidationConfig` dataclass and `validation` field to `config.py`
- **Files modified:** `terraflow/config.py`
- **Verification:** `terraflow validate -c examples/demo_config.yml` ran successfully
- **Committed in:** `c8c0529`

**2. [Rule 1 - Bug] Fixed output_dir and reference_csv resolved from cwd instead of config file parent**
- **Found during:** Task 3 (human verification — `FileNotFoundError` on `synthetic_reference.csv`)
- **Issue:** `validation.py` used `Path(cfg.output_dir)` and `Path(cfg.validation.reference_csv)` which resolved from the current working directory rather than the config file's directory. Running `terraflow validate -c examples/demo_config.yml` from repo root caused `synthetic_reference.csv` to be looked up in the repo root instead of `examples/`
- **Fix:** Changed to `config_dir = config_path.parent` and used `config_dir / cfg.output_dir` and `config_dir / cfg.validation.reference_csv`, matching the pattern used in `pipeline.py`
- **Files modified:** `terraflow/validation.py`
- **Verification:** `terraflow validate -c examples/demo_config.yml` ran successfully, Cohen's kappa 0.034 written to report.json
- **Committed in:** `0f81182`

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both bugs were required for correctness and would have broken the CLI for any user running from a directory other than `examples/`. No scope creep.

## Issues Encountered

Human verification discovered two bugs that were absent from automated tests (tests used `tmp_path` which made paths match). The bugs were latent cherry-pick and path-resolution issues. Fixed inline during the verification gate.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 (Model Validation) is now complete: VALD-01 through VALD-04 all satisfied
- `terraflow validate -c config.yml` is user-facing and documented in the demo notebook
- `report.json` now contains `kriging_loocv`, `validation` (kappa, Moran's I, fold accuracy), and `sensitivity` blocks depending on which commands are run
- Phase 4 (H3 Export) and Phase 5 (Paper) can proceed; Phase 4 depends on Phase 1 only

---
*Phase: 03-model-validation*
*Completed: 2026-03-31*
