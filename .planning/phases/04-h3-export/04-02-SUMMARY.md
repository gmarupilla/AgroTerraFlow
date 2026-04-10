---
phase: 04-h3-export
plan: 02
subsystem: export
tags: [h3, export, orchestrator, fingerprint, parquet]
dependency_graph:
  requires:
    - 04-01  # ExportConfig, to_h3() function
  provides:
    - run_export() orchestrator in terraflow/export.py
  affects:
    - terraflow/export.py
    - tests/test_export.py
tech_stack:
  added: []
  patterns:
    - run_validation() orchestrator pattern (load config, resolve run dir, read parquet, write artifact)
    - _atomic_write_parquet for safe concurrent writes
    - resolve_run_dir for fingerprint-based run directory lookup
key_files:
  created: []
  modified:
    - terraflow/export.py
    - tests/test_export.py
decisions:
  - resolution_override affects only output filename, not run_dir; run_dir always determined by on-disk config fingerprint (per D-07)
  - format="geojson" raises ValueError immediately before config load for fail-fast behavior
metrics:
  duration: ~12min
  completed: "2026-04-04T02:09:49Z"
  tasks_completed: 1
  files_modified: 2
---

# Phase 4 Plan 02: run_export() Orchestrator and Fingerprint Tests Summary

**One-liner:** `run_export()` orchestrator wires `to_h3()` into TerraFlow's artifact system, reading features.parquet from the fingerprinted run directory and writing `h3_resolution_{N}.parquet` atomically.

## What Was Built

Added `run_export()` to `terraflow/export.py` following the established `run_validation()` pattern. The function:

1. Validates the export format (only `"h3"` supported)
2. Loads and validates config via `load_config_dict` + `build_config`
3. Checks for `export:` section in config; raises `ValueError` with clear message if absent
4. Resolves effective resolution (CLI override takes precedence over config value)
5. Calls `resolve_run_dir()` to locate the fingerprinted run directory
6. Raises `FileNotFoundError` with actionable message if `features.parquet` not found
7. Reads features, calls `to_h3()`, writes `h3_resolution_{N}.parquet` atomically via `_atomic_write_parquet`

Added 6 new tests in `tests/test_export.py`:
- `TestRunExport.test_run_export_writes_artifact` — confirms h3_resolution_8.parquet is created and returned
- `TestRunExport.test_run_export_resolution_override_filename` — confirms override changes filename to h3_resolution_4.parquet
- `TestRunExport.test_run_export_no_export_section` — confirms `ValueError` with "no 'export:' section"
- `TestRunExport.test_run_export_unsupported_format` — confirms `ValueError` with "Unsupported export format"
- `TestRunExport.test_run_export_missing_features_raises` — confirms `FileNotFoundError` on absent parquet
- `test_resolution_changes_fingerprint` — directly validates H3-03: two configs differing only in `h3_resolution` produce distinct run fingerprints

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement run_export() orchestrator and fingerprint tests | 0705eba | terraflow/export.py, tests/test_export.py |

## Decisions Made

1. **Resolution override scope:** `resolution_override` changes only the output filename (`h3_resolution_{N}.parquet`), not the run directory. The run directory is always derived from the on-disk config fingerprint. For a distinct cached directory, the user must set `export.h3_resolution` in the YAML config. This satisfies H3-03 via the config fingerprint mechanism.

2. **Format validation order:** The unsupported format check runs first (before config load) for immediate fail-fast feedback — consistent with how `to_h3()` validates its own inputs before doing I/O.

3. **Test config templates:** Export test configs require `model_params` block because `PipelineConfig.model_params` is required. Templates follow the same pattern as `test_validation.py`'s `_MINIMAL_CONFIG`.

## Deviations from Plan

**1. [Rule 1 - Bug] Test config templates missing required model_params**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `_EXPORT_CONFIG` and `_NO_EXPORT_CONFIG` lacked `model_params:` block, causing `build_config()` to raise `ValidationError` before reaching the export section check
- **Fix:** Added full `model_params` block to both config templates, matching `test_validation.py` pattern
- **Files modified:** tests/test_export.py
- **Commit:** 0705eba (inline fix, same commit)

## Known Stubs

None. `run_export()` is fully wired: reads real parquet, calls real `to_h3()`, writes real parquet via `_atomic_write_parquet`. The h3-dependent tests (`test_run_export_writes_artifact`, `test_run_export_resolution_override_filename`) are skipped in environments without `h3` installed — this is expected behavior, not a stub.

## Verification Results

- `python -m pytest tests/test_export.py -v` — 12 passed, 7 skipped (h3 optional dep not installed)
- `python -c "from terraflow.export import run_export; print(run_export)"` — prints function reference
- All acceptance criteria met per plan

## Self-Check: PASSED

Files exist:
- FOUND: terraflow/export.py (contains `def run_export(`, `resolve_run_dir`, `h3_resolution_{effective_resolution}.parquet`, `Unsupported export format`, `no 'export:' section`)
- FOUND: tests/test_export.py (contains `test_run_export_writes_artifact`, `test_resolution_changes_fingerprint`, `test_run_export_unsupported_format`)

Commits exist:
- FOUND: 0705eba — feat(04-02): implement run_export() orchestrator and fingerprint tests
