---
phase: 02
slug: sensitivity-analysis
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.0+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_sensitivity.py tests/test_cli.py -x` |
| **Full suite command** | `pytest --cov=terraflow --cov-report=term-missing --cov-fail-under=85` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_sensitivity.py tests/test_cli.py -x`
- **After every plan wave:** Run `pytest --cov=terraflow --cov-report=term-missing --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | SENS-01 | unit | `pytest tests/test_sensitivity.py::test_sobol_produces_s1_st -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | SENS-01 | unit | `pytest tests/test_sensitivity.py::test_sobol_index_bounds -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | SENS-02 | unit | `pytest tests/test_sensitivity.py::test_morris_produces_mu_star -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | SENS-03 | unit | `pytest tests/test_sensitivity.py::test_report_json_schema -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0 | SENS-03 | unit | `pytest tests/test_sensitivity.py::test_report_written_to_output_dir -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | SENS-04 | integration | `pytest tests/test_cli.py::test_sensitivity_nonpower_of_two -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | SENS-04 | integration | `pytest tests/test_cli.py::test_sensitivity_cmd_success -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | D-02 | integration | `pytest tests/test_cli.py::test_cli_run_subcommand -x` | ✅ (update) | ⬜ pending |
| 02-02-04 | 02 | 1 | D-02 | integration | `pytest tests/test_cli.py::test_old_flat_command_fails -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sensitivity.py` — new file with stub tests for SENS-01 through SENS-03 (Sobol', Morris, report.json schema)
- [ ] `tests/test_cli.py` — update existing CLI tests for `terraflow run` subcommand; add stubs for `terraflow sensitivity` tests
- [ ] `pip install "SALib>=1.5" "typer>=0.12.5"` added to `pyproject.toml [project.dependencies]` before any test can pass

*Wave 0 must complete before any other plan wave begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Terminal ranking table output | D-09 | stdout formatting hard to assert precisely | Run `terraflow sensitivity -c examples/demo_config.yml`; verify ranked table displays with S1/ST columns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
