# Phase 2: Sensitivity Analysis - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 02-sensitivity-analysis
**Areas discussed:** CLI subcommand design, Sensitivity config schema, SALib dependency scope, Output artifacts

---

## CLI Subcommand Design

| Option | Description | Selected |
|--------|-------------|----------|
| argparse subparsers | Add subparsers to existing argparse; minimal change | |
| Separate entrypoint | `terraflow-sensitivity` as separate pyproject entry point | |
| Migrate CLI to Typer | Replace argparse with Typer; modern subcommand support | ✓ |

**User's choice:** Migrate to Typer

| Option | Description | Selected |
|--------|-------------|----------|
| `terraflow run` — clean rename | `terraflow run` / `sensitivity` as peer subcommands | ✓ |
| Keep backward compat | `invoke_without_command` so old invocation still works | |

**Notes:** User clarified that `terraflow` should be the common top-level app with subcommands: `run`, `sensitivity`, and future ones (`validate`, `inspect`, `export`). Clean rename accepted — pre-JOSS breakage is acceptable.

---

## Sensitivity Config Schema

| Option | Description | Selected |
|--------|-------------|----------|
| New `sensitivity:` section in existing config | Extend same config.yml with sensitivity block | ✓ |
| Separate sensitivity config file | `--sensitivity-config sens.yml` separate file | |
| Derive bounds from ModelParams automatically | ±X% auto-derived bounds | |

**User's choice:** `sensitivity:` section in existing config.yml

| Option | Description | Selected |
|--------|-------------|----------|
| Weights only: w_v, w_t, w_r | Scientific focus; most policy-relevant parameters | ✓ |
| All 9 fields | Full sweep including normalization bounds | |
| User-specified subset | Variable-length parameter list in config | |

**User's choice:** Weights only (w_v, w_t, w_r)

---

## SALib Dependency Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Core dependency | Always installed; reviewers need no extra steps | ✓ |
| Optional `[sensitivity]` extra | Follows plotly/[viz] pattern; opt-in | |

**User's choice:** Core dependency
**Notes:** Distinction from plotly: SALib is computation for a primary JOSS feature, not visualization.

---

## Output Artifacts

| Option | Description | Selected |
|--------|-------------|----------|
| Write sensitivity_report.json to output_dir | Standalone JSON file | ✓ |
| Append to existing pipeline run's report.json | Couples to prior run | |
| Print to stdout + write file | Both terminal output and file | |

**User's choice:** Write sensitivity_report.json

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — print ranking table | Terminal summary after writing file | ✓ |
| No — silent (file only) | Write file, no terminal output | |

**User's choice:** Print ranking table to stdout

---

## Claude's Discretion

- Internal field names in sensitivity_report.json
- Sequential execution order when `method: both`
- Typer version selection

## Deferred Ideas

- `terraflow validate`, `terraflow inspect`, `terraflow export` — future subcommands
- Sweeping normalization bounds — v2 feature
