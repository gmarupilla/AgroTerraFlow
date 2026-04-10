---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to plan
stopped_at: "Completed 04-03-PLAN.md: CLI export subcommand, notebook, docs, PR checklist artifacts"
last_updated: "2026-04-04T02:33:50.670Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 12
  completed_plans: 12
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Every TerraFlow run produces a verifiable, reproducible result — same inputs always yield the same outputs, with full uncertainty quantification and provenance — making findings publishable and auditable.
**Current focus:** Phase 04 — h3-export

## Current Position

Phase: 5
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-foundation-hardening P01 | 8 | 2 tasks | 3 files |
| Phase 01 P02 | 8 | 2 tasks | 3 files |
| Phase 02-sensitivity-analysis P01 | 5min | 2 tasks | 5 files |
| Phase 02-sensitivity-analysis P03 | 5min | 2 tasks | 3 files |
| Phase 03 P02 | 25min | 1 tasks | 1 files |
| Phase 03 P03 | 45min | 3 tasks | 7 files |
| Phase 04-h3-export P01 | 49min | 2 tasks | 5 files |
| Phase 04-h3-export P02 | 12min | 1 tasks | 2 files |
| Phase 04-h3-export P03 | 5min | 3 tasks | 8 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 4 (H3 Export) depends on Phase 1 only — can run parallel to Phases 2 and 3 after Phase 1 completes
- [Roadmap]: SALib goes in core dependencies (sensitivity is a key paper claim); h3-py goes in optional `[h3]` extra
- [Roadmap]: Variogram range units (degrees vs metres) — decision deferred to Phase 1 planning; document limitation in report.json at minimum
- [Phase 01-foundation-hardening]: plotly demoted to pip install terraflow[viz] optional extra — keeps core install lean for JOSS reviewers
- [Phase 01-foundation-hardening]: Optional-dep import guard pattern established: try/except with _AVAILABLE flag + ImportError hint at call site
- [Phase 01]: CRSMismatchError subclasses pyproj.exceptions.CRSError so callers can catch either the specific or base CRS error
- [Phase 01]: variogram_params extracted from full-data OrdinaryKriging fit; range_units field set to degrees_geographic to document coordinate-system limitation
- [Phase 02-sensitivity-analysis]: Typer add_completion=False to suppress shell completion prompts; sensitivity_cmd uses late import for safe import before Plan 02; test_cli_valid_config_runs_pipeline wraps main() in raises(SystemExit) for Typer standalone mode
- [Phase 02-sensitivity-analysis]: sensitivity_cmd catches ValueError and Exception with exit 1; human verified complete Sobol/Morris CLI end-to-end
- [Phase 03]: Fold prediction: majority label of buffered training set used as spatial baseline (no free params in TerraFlow model)
- [Phase 03]: Moran's I: row-standardized inverse-distance weights via np.exp(-D); returns None on degeneracy
- [Phase 03]: validate_cmd uses late import (from .validation import run_validation) inside function body, matching sensitivity_cmd pattern
- [Phase 03]: Config path resolution canonical pattern — always use config_dir = config_path.parent, then config_dir / cfg.relative_path (applies to validation.py, pipeline.py)
- [Phase 04-h3-export]: h3 guard at call-site: export.py always importable; ImportError deferred to to_h3() call
- [Phase 04-h3-export]: h3 v4 API (latlng_to_cell) used; v3 geo_to_h3 avoided per D-09
- [Phase 04-h3-export]: resolution_override affects only output filename, not run_dir; run_dir always determined by on-disk config fingerprint
- [Phase 04-h3-export]: export_cmd --format is required (no default) to force explicit user intent; --resolution is optional (None) and passed as resolution_override
- [Phase 04-h3-export]: Late import pattern (from .export import run_export inside function body) consistent with validate_cmd and sensitivity_cmd

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Kriging variogram coordinate system decision (degree-units vs UTM reproject) must be resolved before Phase 1 closes — affects paper Methods and report.json documentation
- [Phase 2]: SALib version API (1.4 vs 1.5 `ResultDict`) must be verified with `pip index versions SALib` before Phase 2 implementation begins
- [Phase 4]: h3-py version API (3.x `geo_to_h3` vs 4.x `latlng_to_cell`) must be verified with `pip index versions h3` before Phase 4 implementation begins

## Session Continuity

Last session: 2026-04-04T02:26:10.176Z
Stopped at: Completed 04-03-PLAN.md: CLI export subcommand, notebook, docs, PR checklist artifacts
Resume file: None
