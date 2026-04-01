---
phase: 03-model-validation
plan: 02
subsystem: validation
tags: [spatial-block-cv, cohen-kappa, morans-i, sklearn, scipy, numpy, GroupKFold, KDTree, cdist]

# Dependency graph
requires:
  - phase: 03-01
    provides: ValidationConfig in config.py, kriging_loocv in pipeline.py, test_validation.py scaffold, synthetic_reference.csv
provides:
  - terraflow/validation.py with _assign_block_ids, _spatial_block_cv, _compute_kappa, _morans_i, run_validation
  - Spatial block CV with buffer-zone exclusion (Roberts et al. 2017, Ecography)
  - Cohen's kappa against reference CSV via KDTree nearest-neighbor matching
  - Global Moran's I on score residuals (numpy-only, no libpysal)
  - run_validation() entry point reading features.parquet and appending validation block to report.json
affects: [03-03, JOSS paper Methods section]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "validation.py mirrors sensitivity.py: private _ helpers, public run_* entry point, _atomic_write_json"
    - "Spatial block CV with majority-label baseline prediction; documented as label consistency metric, not fit generalisation"
    - "Degenerate guards: _morans_i returns None when z@z==0; _spatial_block_cv returns [] when < 2 blocks"

key-files:
  created:
    - terraflow/validation.py
  modified: []

key-decisions:
  - "Fold prediction strategy: majority label of buffered training set used as spatial baseline (TerraFlow has no free parameters to fit)"
  - "Moran's I implemented from Cliff & Ord (1981) formula using numpy; row-standardized inverse-distance weights via np.exp(-D)"
  - "KDTree distance warning threshold set at 1.0 degree; warn message includes 'distance' to match test assertion"
  - "run_validation() finds latest run dir by sorting features.parquet paths by mtime"

patterns-established:
  - "Atomic JSON read-modify-write pattern for report.json: read -> update in memory -> write via tempfile + os.replace"
  - "GroupKFold + cdist buffer exclusion pattern for spatial block CV without spacv/verde dependency"

requirements-completed: [VALD-01, VALD-02, VALD-04]

# Metrics
duration: 25min
completed: 2026-03-31
---

# Phase 03 Plan 02: Model Validation Module Summary

**Spatial block CV (Roberts 2017), Cohen's kappa via KDTree, and numpy Moran's I delivered in terraflow/validation.py with 9/9 tests green**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-31T00:00:00Z
- **Completed:** 2026-03-31
- **Tasks:** 1 (TDD: RED → GREEN)
- **Files modified:** 1 created

## Accomplishments
- Implemented `terraflow/validation.py` (352 lines) with all 5 required functions: `_assign_block_ids`, `_spatial_block_cv`, `_compute_kappa`, `_morans_i`, `run_validation`
- All 9 tests in `tests/test_validation.py` pass (block CV, kappa, Moran's I degenerate, run_validation importable)
- Full test suite passes: 180 passed, 2 skipped, zero regressions

## Task Commits

1. **Task 1: Implement terraflow/validation.py core functions** - `39791e9` (feat)

**Plan metadata:** (docs commit — see state updates)

## Files Created/Modified
- `terraflow/validation.py` — spatial block CV, Cohen's kappa, Moran's I, run_validation entry point (352 lines)

## Decisions Made
- **Fold prediction strategy:** because TerraFlow's suitability model has no free parameters learned from data, each fold uses the majority label of the buffered training set as a spatial baseline. This measures spatial label consistency rather than model fit generalisation, documented in the `note` field of `report["validation"]`.
- **Moran's I weights:** row-standardized inverse-distance weights via `np.exp(-D)`; the diagonal is zeroed before row-standardisation. Returns `None` on degeneracy (uniform residuals).
- **KDTree warning threshold:** 1.0 degree; warning message includes the word "distance" to satisfy the test assertion in `test_kappa_extent_warning`.
- **run_validation latests-run logic:** sorted `glob("runs/*/features.parquet")` by `stat().st_mtime` descending; picks the newest run dir.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cherry-picked Plan 01 commits into this worktree**
- **Found during:** Task 1 setup
- **Issue:** This worktree was based on `origin/main` which did not have Plan 01's artifacts (ValidationConfig, kriging_loocv, test_validation.py scaffold, synthetic_reference.csv). The Plan 01 commits existed on a different worktree branch (`worktree-agent-*`).
- **Fix:** `git cherry-pick 7189357` (feat(03-01): surface kriging_loocv + ValidationConfig) and `git cherry-pick 073b9d4` (feat(03-01): scaffold + reference CSV) to bring Plan 01 work into this worktree.
- **Files modified:** terraflow/pipeline.py, terraflow/config.py, examples/synthetic_reference.csv, tests/test_validation.py (all from Plan 01)
- **Verification:** `python -c "from terraflow.config import ValidationConfig"` passes; 9 RED tests confirmed before implementing validation.py
- **Committed in:** 445f65f, 472a95a (cherry-pick commits)

**2. [Rule 1 - Bug] Added "distance" to KDTree warning message**
- **Found during:** Task 1 GREEN phase (1 test still failing after initial implementation)
- **Issue:** Warning message said "degrees from nearest cell" but test asserts `"distance" in str(warning.message).lower()`
- **Fix:** Changed warning text to "degrees distance from nearest cell" to include the expected substring
- **Files modified:** terraflow/validation.py
- **Verification:** `test_kappa_extent_warning` passes
- **Committed in:** 39791e9 (part of main task commit)

---

**Total deviations:** 2 (1 blocking infra fix, 1 bug)
**Impact on plan:** Both necessary for correctness. No scope creep.

## Issues Encountered
- pytest run from the main repo root (`/Users/chandhini/akhil/TerraFlow`) picked up the main repo's installed package rather than the worktree; running with absolute path to the worktree resolved this. Tests pass correctly when run from the worktree directory.

## Known Stubs
None. `run_validation()` is fully wired: reads features.parquet, computes all metrics, appends to report.json. No placeholders or TODO items that would prevent the plan's goal.

## Next Phase Readiness
- `terraflow/validation.py` is complete and tested; Plan 03 (CLI integration) can wire `run_validation` directly into the `terraflow validate` subcommand
- The `validation` block structure in `report.json` is established; Plan 03 tests can assert on key presence
- No blockers

---
*Phase: 03-model-validation*
*Completed: 2026-03-31*
