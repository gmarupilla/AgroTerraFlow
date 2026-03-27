---
phase: 1
slug: foundation-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `make test` |
| **Full suite command** | `make test-cov` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `make test`
- **After every plan wave:** Run `make test-cov`
- **Before `/gsd:verify-work`:** Full suite must be green with ≥85% branch coverage
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01-01 | 1 | HARD-04 | packaging | `grep -c 'plotly' pyproject.toml \| grep -q '1'` | ✅ | ⬜ pending |
| 1-01-02 | 01-01 | 1 | HARD-04 | unit | `pytest tests/test_viz.py -x -q` | ✅ | ⬜ pending |
| 1-02-01 | 01-02 | 1 | HARD-01 | unit | `python -c "from terraflow.exceptions import CRSMismatchError"` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01-02 | 1 | HARD-03 | unit | `grep 'kriging_diagnostics' terraflow/pipeline.py && pytest tests/ -x -q` | ✅ | ⬜ pending |
| 1-03-01 | 01-03 | 2 | HARD-01, HARD-02, HARD-03 | integration | `pytest tests/test_pipeline.py -x -q -k "crs_mismatch or kriging_diagnostics"` | ❌ W0 | ⬜ pending |
| 1-03-02 | 01-03 | 2 | HARD-02 | coverage | `pytest tests/ --cov=terraflow --cov-branch -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- `tests/` directory with conftest.py and synthetic fixtures already present
- `make test-cov` already generates `coverage.xml`
- No new test framework setup required

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pip install terraflow` installs without plotly | HARD-04 | Requires clean venv | `python -m venv /tmp/test-venv && /tmp/test-venv/bin/pip install -e . && /tmp/test-venv/bin/python -c "import plotly"` — must raise ImportError |
| PyPI classifiers visible on test.pypi.org | HARD-04 | Requires upload | Verify `pyproject.toml` contains classifier strings; build/upload deferred to Phase 5 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
