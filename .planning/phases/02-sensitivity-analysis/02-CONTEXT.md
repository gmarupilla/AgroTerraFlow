# Phase 2: Sensitivity Analysis - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a standalone `terraflow sensitivity -c config.yml` subcommand that computes Sobol' first-order (S1) and total-order (ST) sensitivity indices and Morris elementary effects over the model weight parameters (w_v, w_t, w_r). Results are written to `sensitivity_report.json` in the configured output directory and summarized as a ranked table in the terminal. A `sensitivity` block is included in the output artifact for paper/JOSS reference.

This phase also migrates the CLI from flat argparse to a Typer-based subcommand app, adding `terraflow run` and `terraflow sensitivity` as the first two peer subcommands.

</domain>

<decisions>
## Implementation Decisions

### CLI Architecture
- **D-01:** Migrate `terraflow/cli.py` from flat argparse to **Typer** — `terraflow` becomes the top-level app with subcommands as the expansion surface for future phases.
- **D-02:** The existing `terraflow -c config.yml` command is **renamed** to `terraflow run -c config.yml`. This is a one-time breaking change acceptable at the pre-JOSS stage.
- **D-03:** `terraflow sensitivity -c config.yml` is the new Phase 2 subcommand. Future subcommands (`validate`, `export`, `inspect`) follow the same pattern.

### Sensitivity Config Schema
- **D-04:** Add a `sensitivity:` section to the existing `config.yml` (same file used by `terraflow run`). The section specifies: per-weight bounds (`w_v`, `w_t`, `w_r` each with `low` and `high`), `n_samples` (int, must be power-of-2 for Sobol'), and optionally `method: sobol | morris | both` (default: both).
- **D-05:** Only the three model weights (`w_v`, `w_t`, `w_r`) are sweepable. Normalization bounds (v_min/max, t_min/max, r_min/max) are fixed by input data range and not included in the sweep.
- **D-06:** `n_samples` must be a power-of-2 for Sobol' sampling. Running `terraflow sensitivity` with a non-power-of-2 value produces a clear CLI validation error before any computation starts (per SENS-04 success criterion).

### SALib Dependency
- **D-07:** SALib is a **core dependency** — added to `[project.dependencies]` in `pyproject.toml`, not an optional extra. Sensitivity analysis is a primary JOSS feature; reviewers must be able to run it with a plain `pip install terraflow`.

### Output Artifacts
- **D-08:** `terraflow sensitivity` writes `sensitivity_report.json` to the `output_dir` specified in config. The file is standalone — not tied to any prior pipeline run directory.
- **D-09:** After writing the file, `terraflow sensitivity` prints a ranked parameter table to stdout showing S1 / ST indices (Sobol') or mu* (Morris) per weight parameter.
- **D-10:** The `sensitivity_report.json` content constitutes the `sensitivity` block referenced in SENS-03 (to be embedded or referenced in `report.json` in Phase 5 when the paper is finalized).

### Claude's Discretion
- Internal structure of `sensitivity_report.json` (exact field names, nesting) — follow SALib output conventions.
- Whether `sensitivity` runs Sobol', Morris, or both when `method: both` is set — run sequentially, Sobol' first.
- Typer version pinning strategy — use latest stable compatible with Python 3.10+.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SALib
- SALib documentation and API reference — `pip show salib` or https://salib.readthedocs.io — agents should use Context7 / web fetch for current API

### Existing TerraFlow code
- `terraflow/cli.py` — current flat argparse CLI to be migrated to Typer
- `terraflow/config.py` — `ModelParams`, `PipelineConfig` Pydantic models; `sensitivity:` section will be a new Pydantic model added here
- `terraflow/pipeline.py` — `run_pipeline()` function; Typer `run` subcommand wraps this
- `pyproject.toml` — dependency declarations; SALib and Typer to be added to `[project.dependencies]`

### Requirements
- `.planning/REQUIREMENTS.md` §Sensitivity Analysis — SENS-01 through SENS-04
- `.planning/ROADMAP.md` §Phase 2 — success criteria for this phase

### Prior phase conventions
- `.planning/phases/01-foundation-hardening/01-01-SUMMARY.md` — optional dependency pattern for plotly/[viz] (contrast: SALib is core, not optional)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `terraflow/config.py:PipelineConfig` — Pydantic config loading; new `SensitivityConfig` model should follow the same pattern (field validators, ConfigDict extra="forbid")
- `terraflow/utils.py:logger` — centralized logger; sensitivity module uses the same `terraflow` logger
- `terraflow/pipeline.py:run_pipeline()` — called by the new `terraflow run` subcommand unchanged

### Established Patterns
- Pydantic v2 with `ConfigDict(extra="forbid")` and `field_validator` for all config models
- Atomic file writes (write-to-temp then rename) — sensitivity_report.json should follow this pattern
- 85% branch coverage threshold enforced in CI — new sensitivity module needs tests

### Integration Points
- `pyproject.toml [project.scripts]` — `terraflow = "terraflow.cli:main"` entry point; stays the same, Typer app replaces the argparse parser inside `main()`
- `terraflow/__init__.py` — no changes expected; sensitivity module added as `terraflow/sensitivity.py` or `terraflow/sensitivity/`

</code_context>

<specifics>
## Specific Ideas

- The user envisions `terraflow` as the common top-level command with an expanding set of subcommands: `run`, `sensitivity`, `validate`, `inspect`, `export` (future). Phase 2 establishes the Typer foundation for all future subcommands.
- Terminal output should show a ranked table (not raw JSON) — good for interactive use and for including as a terminal screenshot in the JOSS paper.

</specifics>

<deferred>
## Deferred Ideas

- `terraflow validate` subcommand — Phase 3 scope
- `terraflow export` subcommand — Phase 4 scope
- `terraflow inspect` — future, not yet in roadmap
- Sweeping normalization bounds (v_min/max, t_min/max, r_min/max) — v2 or user-configured subset option

</deferred>

---

*Phase: 02-sensitivity-analysis*
*Context gathered: 2026-03-27*
