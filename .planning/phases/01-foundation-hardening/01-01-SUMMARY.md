---
phase: 01-foundation-hardening
plan: "01"
subsystem: packaging
tags: [plotly, pyproject.toml, optional-deps, trove-classifiers, viz, joss]

requires: []
provides:
  - plotly moved to optional [viz] extra in pyproject.toml
  - trove classifiers and Documentation URL added to pyproject.toml
  - viz.py guarded with _PLOTLY_AVAILABLE flag and helpful ImportError
  - test_viz.py skips cleanly when plotly not installed
affects: [02-foundation-hardening, 03-foundation-hardening, joss-paper]

tech-stack:
  added: []
  patterns:
    - "Optional dependency pattern: try/except import guard with _AVAILABLE flag"
    - "pytest.importorskip for optional-dep tests"

key-files:
  created: []
  modified:
    - pyproject.toml
    - terraflow/viz.py
    - tests/test_viz.py

key-decisions:
  - "plotly demoted to pip install terraflow[viz] optional extra — keeps core install lean for JOSS reviewers"
  - "ImportError hint pattern (pip install terraflow[viz]) adopted for all future optional imports"

patterns-established:
  - "Optional-dep guard: try/except at module level setting _FOO_AVAILABLE; check at call site with clear InstallError"
  - "Test skip: pytest.importorskip('lib') as first executable line in test file"

requirements-completed: [HARD-04]

duration: 8min
completed: 2026-03-26
---

# Phase 01 Plan 01: Optional Viz Dependency and JOSS Packaging Metadata Summary

**plotly moved to optional `pip install terraflow[viz]` extra with guarded import, and pyproject.toml enriched with trove classifiers and Documentation URL for JOSS submission readiness**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-26T00:00:00Z
- **Completed:** 2026-03-26T00:08:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Removed plotly from core dependencies; it is now exclusively under `[project.optional-dependencies] viz`
- Added 9 PyPI trove classifiers (Dev Status, Audience, License, Python 3.10-3.12, GIS topic, OS Independent) and Documentation URL to pyproject.toml
- Added try/except guard in viz.py setting `_PLOTLY_AVAILABLE` flag; `plot_suitability_scatter` raises ImportError with `pip install terraflow[viz]` hint when plotly is absent
- Added `pytest.importorskip("plotly")` to test_viz.py so the test module skips gracefully without plotly

## Task Commits

Each task was committed atomically:

1. **Task 1: Update pyproject.toml** - `ea3e4c9` (chore)
2. **Task 2: Guard plotly import in viz.py and update test_viz.py** - `17b9be9` (feat)

## Files Created/Modified

- `pyproject.toml` - plotly removed from core deps; viz optional extra, trove classifiers, and Documentation URL added
- `terraflow/viz.py` - try/except plotly import guard with `_PLOTLY_AVAILABLE` flag; ImportError with install hint
- `tests/test_viz.py` - `pytest.importorskip("plotly")` added as first executable line

## Decisions Made

- Used `try/except ImportError` guard at module level (not function level) so import cost is paid once; flag checked at call site
- Documentation URL points to `https://gmarupilla.github.io/AgroTerraFlow/` per project authorship rules

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- pyproject.toml packaging metadata is JOSS-ready for plans 01-02 and 01-03
- Optional-dep guard pattern is established for any future optional import (e.g., h3-py in Phase 4)
- No blockers for subsequent foundation-hardening plans

## Self-Check: PASSED

- `ea3e4c9` found in git log
- `17b9be9` found in git log
- `pyproject.toml` contains `viz = ["plotly>=5.0.0"]` and trove classifiers
- `terraflow/viz.py` contains `_PLOTLY_AVAILABLE`
- `tests/test_viz.py` contains `pytest.importorskip("plotly")`
- `pytest tests/test_viz.py` exits 0 (2 passed)

---
*Phase: 01-foundation-hardening*
*Completed: 2026-03-26*
