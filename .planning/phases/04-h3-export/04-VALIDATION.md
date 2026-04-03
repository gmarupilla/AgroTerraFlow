---
phase: 4
slug: h3-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7+ with pytest-cov |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_export.py -v` |
| **Full suite command** | `make test-cov` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_export.py -v`
- **After every plan wave:** Run `make test-cov`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | H3-02 | unit | `pytest tests/test_export.py::test_to_h3_importerror -x` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | H3-01 | unit | `pytest tests/test_export.py -k "to_h3" -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | H3-01 | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mean -x` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 1 | H3-01 | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mode -x` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | H3-03 | unit | `pytest tests/test_export.py::test_resolution_changes_fingerprint -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | H3-03 | unit | `pytest tests/test_export.py::test_run_export_writes_artifact -x` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 3 | H3-04 | integration | `pytest tests/test_cli.py -k "export" -x` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 3 | H3-04 | unit | `pytest tests/test_cli.py -k "unsupported_format" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_export.py` — stub file with test functions for H3-01, H3-02, H3-03
- [ ] `tests/test_cli.py` — `TestExportCLI` class additions for H3-04

*Existing infrastructure (pytest, conftest.py fixtures) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Notebook demonstrates DeckGL/Kepler.gl H3 use case | H3-01 | Visual output validation | Run `notebooks/04_h3_export.ipynb` end-to-end; verify H3 cells render in the visualization section |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
