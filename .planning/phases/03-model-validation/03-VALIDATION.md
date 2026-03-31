---
phase: 3
slug: model-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | VALD-01 | unit | `pytest tests/test_validation.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | VALD-01 | unit | `pytest tests/test_validation.py::test_spatial_block_cv -v` | ✅ | ⬜ pending |
| 3-01-03 | 01 | 1 | VALD-01 | unit | `pytest tests/test_validation.py::test_buffer_exclusion -v` | ✅ | ⬜ pending |
| 3-02-01 | 02 | 1 | VALD-02 | unit | `pytest tests/test_validation.py::test_cohens_kappa -v` | ✅ | ⬜ pending |
| 3-02-02 | 02 | 0 | VALD-02 | file | `test -f examples/synthetic_reference.csv` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 1 | VALD-03 | unit | `pytest tests/test_pipeline.py::test_kriging_loocv_key -v` | ✅ | ⬜ pending |
| 3-04-01 | 04 | 2 | VALD-04 | unit | `pytest tests/test_pipeline.py::test_report_validation_block -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_validation.py` — stubs for VALD-01, VALD-02 (spatial CV, Cohen's kappa)
- [ ] `examples/synthetic_reference.csv` — bundled reference dataset for VALD-02
- [ ] `tests/conftest.py` — shared fixtures (sample raster, reference CSV loader) — update if missing

*Existing pytest infrastructure covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| report.json validation block readable by users | VALD-04 | Integration output requires full pipeline run | Run `terraflow run examples/config.yaml` and inspect `report.json` for `validation` block with kappa, Moran's I, mean accuracy, LOOCV RMSE |
| Spatial CV caveat documented in notebook | VALD-01 | Notebook render requires Jupyter | Open `notebooks/03_model_validation.ipynb` and verify cell explaining deterministic scoring caveat is present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
