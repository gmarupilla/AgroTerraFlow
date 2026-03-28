---
phase: 02-sensitivity-analysis
verified: 2026-03-28T02:41:01Z
status: gaps_found
score: 3/10 must-haves verified
gaps:
  - truth: "run_sensitivity() with method=sobol produces S1 and ST indices for w_v, w_t, w_r"
    status: failed
    reason: "terraflow/sensitivity.py is still the 7-line Plan 01 stub — raises NotImplementedError. The full 291-line implementation exists only in git worktree branch worktree-agent-a369c668 and has never been merged into feat/stage2-mc-uncertainty."
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub — 7 lines, raises NotImplementedError. Plan 02 commit 338a030 not present on working branch."
    missing:
      - "Merge worktree-agent-a369c668 commits 5d1919d, 338a030, 965d93f into feat/stage2-mc-uncertainty"

  - truth: "run_sensitivity() with method=morris produces mu_star, mu, sigma for w_v, w_t, w_r"
    status: failed
    reason: "Same root cause — sensitivity.py is a stub. Morris implementation exists only in unmerged worktree branch."
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub — no _run_morris(), no SALib.sample.morris import, no SALib.analyze.morris import."
    missing:
      - "Same merge action as SENS-01 gap above"

  - truth: "run_sensitivity() with method=both produces both Sobol and Morris results"
    status: failed
    reason: "stub — no implementation exists in working tree"
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub"
    missing:
      - "Same merge action"

  - truth: "sensitivity_report.json is written atomically to output_dir with sobol and/or morris blocks"
    status: failed
    reason: "No write logic exists in working tree sensitivity.py"
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub — no _atomic_write_json(), no report construction, no output_dir write"
    missing:
      - "Same merge action"

  - truth: "Sobol S1 and ST values are in [0, 1] range with positive confidence intervals"
    status: failed
    reason: "No SALib analysis occurs — stub raises NotImplementedError before any computation"
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub"
    missing:
      - "Same merge action"

  - truth: "A ranked parameter table is printed to stdout showing S1/ST or mu_star"
    status: failed
    reason: "No _print_sobol_table() or _print_morris_table() exists in working tree"
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub"
    missing:
      - "Same merge action"

  - truth: "terraflow sensitivity -c config.yml runs Sobol and Morris analysis and exits 0"
    status: failed
    reason: "sensitivity_cmd in cli.py calls run_sensitivity which raises NotImplementedError. Also, Plan 03 error handling (try/except ValueError) was not merged — sensitivity_cmd has no error handling in working tree."
    artifacts:
      - path: "terraflow/cli.py"
        issue: "sensitivity_cmd calls bare run_sensitivity(config) with no error handling. Plan 03 commit 965d93f not present on working branch."
    missing:
      - "Merge worktree commits to get working sensitivity engine + CLI error handling"

  - truth: "terraflow sensitivity -c config.yml with non-power-of-2 n_samples exits with code 1 and shows helpful error"
    status: failed
    reason: "sensitivity_cmd has no try/except. A non-power-of-2 n_samples ValueError would propagate uncaught through Typer, producing exit code 1 but no formatted error message to stderr."
    artifacts:
      - path: "terraflow/cli.py"
        issue: "Missing except ValueError handler in sensitivity_cmd"
    missing:
      - "Add try/except ValueError and Exception blocks to sensitivity_cmd (Plan 03 Task 1 fix)"

  - truth: "sensitivity_report.json is created in the configured output_dir after CLI run"
    status: failed
    reason: "Depends on sensitivity.py implementation being present — stub never writes a file"
    artifacts:
      - path: "terraflow/sensitivity.py"
        issue: "Stub"
    missing:
      - "Same merge action"

  - truth: "examples/demo_config.yml contains a sensitivity: section for documentation and testing"
    status: failed
    reason: "demo_config.yml has no sensitivity: section. Plan 03 commit 965d93f (which appended it) not merged into working branch."
    artifacts:
      - path: "examples/demo_config.yml"
        issue: "File exists but contains no sensitivity: key. grep finds 0 matches."
    missing:
      - "Append sensitivity: block to examples/demo_config.yml"
---

# Phase 02: Sensitivity Analysis Verification Report

**Phase Goal:** Implement reproducible sensitivity analysis for model weight parameters using Sobol' and Morris methods via SALib, invocable from the CLI.
**Verified:** 2026-03-28T02:41:01Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Root Cause: Implementation Commits Not Merged into Working Branch

The Plan 02 and Plan 03 implementation commits were created in a git worktree (`worktree-agent-a369c668`) but were **never merged** into the `feat/stage2-mc-uncertainty` branch. The working tree contains only Plan 01 artifacts. This single root cause blocks 9 of 10 must-haves.

The commit history on `feat/stage2-mc-uncertainty`:
- `06aa878` feat(02-01): add SALib/typer deps and SensitivityConfig models — PRESENT
- `c587302` feat(02-01): migrate CLI to Typer subcommands and update tests — PRESENT
- `5d1919d` test(02-02): add failing tests for sensitivity analysis engine — ABSENT (worktree only)
- `338a030` feat(02-02): implement Sobol and Morris sensitivity analysis engine — ABSENT (worktree only)
- `965d93f` feat(02-03): wire sensitivity CLI with error handling and add integration tests — ABSENT (worktree only)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SALib>=1.5 and typer>=0.12.5 declared in pyproject.toml core dependencies | VERIFIED | `grep SALib pyproject.toml` returns `"SALib>=1.5"`; typer found similarly |
| 2 | PipelineConfig accepts optional sensitivity: section | VERIFIED | `config.py` line 257: `sensitivity: Optional[SensitivityConfig] = None` |
| 3 | terraflow run -c config.yml is a recognized subcommand | VERIFIED | `cli.py` has `@app.command("run")` with -c option |
| 4 | run_sensitivity() with method=sobol produces S1 and ST indices | FAILED | `sensitivity.py` is 7-line stub raising `NotImplementedError` |
| 5 | run_sensitivity() with method=morris produces mu_star, mu, sigma | FAILED | Same stub — no Morris implementation |
| 6 | run_sensitivity() with method=both produces both results | FAILED | Same stub |
| 7 | sensitivity_report.json written atomically to output_dir | FAILED | No write logic in stub |
| 8 | Sobol S1/ST values in [0,1] range with positive confidence intervals | FAILED | No computation occurs |
| 9 | Ranked parameter table printed to stdout | FAILED | No print functions in stub |
| 10 | terraflow sensitivity -c config.yml runs and exits 0 | FAILED | Calls stub which raises NotImplementedError; also no error handling in sensitivity_cmd |
| 11 | Non-power-of-2 n_samples exits code 1 with helpful error | FAILED | sensitivity_cmd has no try/except |
| 12 | sensitivity_report.json created in output_dir after CLI run | FAILED | Stub never writes |
| 13 | examples/demo_config.yml contains sensitivity: section | FAILED | File exists, 0 sensitivity: lines |

**Score: 3/13 truths verified** (collapsing to 3/10 must-haves from plans)

---

## Required Artifacts

### Plan 01 Artifacts (SENS-04 foundation)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | SALib>=1.5 in dependencies | VERIFIED | Line confirmed: `"SALib>=1.5"` and `"typer>=0.12.5"` |
| `terraflow/config.py` | WeightBounds, SensitivityConfig models | VERIFIED | Both classes present, validators correct |
| `terraflow/cli.py` | Typer app with run/sensitivity subcommands | PARTIAL | run subcommand wired correctly; sensitivity_cmd exists but missing error handling from Plan 03 |
| `tests/test_cli.py` | Updated CLI tests for `terraflow run` | VERIFIED | 9 tests use `"terraflow", "run", "-c"`; `test_cli_old_flat_command_fails` present |

### Plan 02 Artifacts (SENS-01, SENS-02, SENS-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `terraflow/sensitivity.py` | Sobol and Morris engine, min 150 lines | STUB | 7 lines, raises NotImplementedError. Full 291-line implementation in `worktree-agent-a369c668:338a030` only. |
| `tests/test_sensitivity.py` | 7 test functions | MISSING | File does not exist on `feat/stage2-mc-uncertainty`. Present only in worktree. |

### Plan 03 Artifacts (SENS-04 CLI completion)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `terraflow/cli.py` | sensitivity_cmd with error handling + `run_sensitivity` call | PARTIAL | `run_sensitivity` import present; `try/except ValueError` missing (Plan 03 commit not merged) |
| `tests/test_cli.py` | `test_sensitivity_cmd_success`, `test_sensitivity_nonpower_of_two`, `test_sensitivity_missing_section` | MISSING | None of the 3 sensitivity integration tests exist. File is 268 lines (Plan 01 version). |
| `examples/demo_config.yml` | sensitivity: section | MISSING | File exists with no sensitivity key |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `terraflow/cli.py` | `terraflow/pipeline.py` | `from .pipeline import run_pipeline` | WIRED | Line 10 of cli.py |
| `terraflow/config.py` | `terraflow/cli.py` | `SensitivityConfig` imported | PARTIAL | SensitivityConfig exists in config.py; not imported in cli.py (late import via sensitivity.py) |
| `terraflow/sensitivity.py` | `SALib.sample.sobol` | `from SALib.sample.sobol import sample` | NOT WIRED | Stub has no SALib imports |
| `terraflow/sensitivity.py` | `SALib.analyze.sobol` | `from SALib.analyze.sobol import analyze` | NOT WIRED | Stub has no SALib imports |
| `terraflow/sensitivity.py` | `SALib.sample.morris` | `from SALib.sample.morris import sample` | NOT WIRED | Stub has no SALib imports |
| `terraflow/sensitivity.py` | `SALib.analyze.morris` | `morris_analyze(problem, X, Y, ...)` | NOT WIRED | Stub has no SALib imports |
| `terraflow/sensitivity.py` | `terraflow/config.py` | `from .config import` | NOT WIRED | Stub only imports `from pathlib import Path` |
| `terraflow/cli.py` | `terraflow/sensitivity.py` | `from .sensitivity import run_sensitivity` inside sensitivity_cmd | WIRED (import only) | Import present but calls a stub that raises NotImplementedError |

---

## Data-Flow Trace (Level 4)

Not applicable — `sensitivity.py` is a stub. No data flows. `run_sensitivity()` raises `NotImplementedError` before any SALib calls are made.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| sensitivity.py is importable | `python -c "from terraflow.sensitivity import run_sensitivity; print(type(run_sensitivity))"` | `<class 'function'>` | PASS (stub is importable) |
| run_sensitivity raises on invocation | `python -c "from terraflow.sensitivity import run_sensitivity; run_sensitivity('/tmp/x')"` | `NotImplementedError` | FAIL — stub behavior confirms engine absent |
| config.py models import correctly | `python -c "from terraflow.config import WeightBounds, SensitivityConfig; print('ok')"` | `ok` | PASS |
| test_sensitivity.py exists | `ls tests/test_sensitivity.py` | File not found | FAIL |
| CLI help shows both subcommands | `terraflow --help \| grep sensitivity` | Shows `sensitivity` in help | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SENS-01 | Plan 02 | Sobol' first-order and total-order indices over ModelParams via SALib | BLOCKED | sensitivity.py is stub; SALib imports absent; no computation |
| SENS-02 | Plan 02 | Morris elementary effects screening over ModelParams | BLOCKED | sensitivity.py is stub; no Morris implementation |
| SENS-03 | Plan 02 | sensitivity_report.json with Sobol indices, confidence intervals, parameter rankings | BLOCKED | No write logic exists; stub never produces a file |
| SENS-04 | Plans 01+03 | `terraflow sensitivity -c config.yml` CLI subcommand | PARTIAL | Subcommand registered and sensitivity_cmd defined; but calls a stub (NotImplementedError) and lacks error handling from Plan 03 |

REQUIREMENTS.md itself correctly reflects SENS-01/02/03 as Pending and SENS-04 as Complete, but SENS-04 Complete is misleading — the subcommand is registered but non-functional (raises NotImplementedError on invocation).

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `terraflow/sensitivity.py` | 5-7 | `raise NotImplementedError(...)` in `run_sensitivity()` | BLOCKER | Every invocation of `terraflow sensitivity -c ...` raises NotImplementedError |
| `terraflow/sensitivity.py` | 1 | Docstring: "implementation in Plan 02" | BLOCKER | Plan 02 was supposedly completed; stub was never replaced |
| `terraflow/cli.py` | 57-58 | `sensitivity_cmd` calls `run_sensitivity(config)` with no error handling | BLOCKER | ValueError from Pydantic validation propagates uncaught; no formatted error message |

---

## Human Verification Required

The Plan 03 task included a human checkpoint (Task 2) which the 02-03-SUMMARY.md records as "APPROVED by human (2026-03-27)". However, that approval was given in the worktree environment where the full implementation was present. The approval does not apply to the current working tree state, where the implementation is absent.

### 1. End-to-End CLI Run After Merge

**Test:** After merging the worktree commits, run `terraflow sensitivity -c examples/demo_config.yml`
**Expected:** Ranked Sobol'/Morris tables print to stdout, `sensitivity_report.json` is created in the configured output_dir, exit code 0
**Why human:** Requires visual inspection of rich table output and file contents; SALib computation is not deterministic for correctness verification without running it

---

## Gaps Summary

**Root cause: 3 implementation commits exist only in a git worktree and were never merged.**

The worktree `worktree-agent-a369c668` (tip: `965d93f`) contains the complete Phase 02 implementation including:
- `tests/test_sensitivity.py` (7 tests, all passing per SUMMARY)
- `terraflow/sensitivity.py` (291-line full implementation with Sobol/Morris/report/tables)
- Updated `terraflow/cli.py` (sensitivity_cmd error handling)
- Updated `tests/test_cli.py` (3 sensitivity integration tests)
- Updated `examples/demo_config.yml` (sensitivity: section)

The `feat/stage2-mc-uncertainty` branch is missing commits `5d1919d`, `338a030`, `965d93f`.

**To close all gaps:** Merge or cherry-pick those 3 commits from `worktree-agent-a369c668` into `feat/stage2-mc-uncertainty`. No new code needs to be written — the implementation is complete and was human-approved; it just needs to land on the working branch.

**Requirement status post-merge (expected):**
- SENS-01: satisfied — Sobol S1/ST computed via SALib 1.5 with seed=42
- SENS-02: satisfied — Morris mu_star/mu/sigma via SALib morris_analyze(problem, X, Y)
- SENS-03: satisfied — sensitivity_report.json with schema_version, sobol, morris blocks
- SENS-04: satisfied — terraflow sensitivity -c config.yml fully functional with error handling

---

_Verified: 2026-03-28T02:41:01Z_
_Verifier: Claude (gsd-verifier)_
