# Phase 4: H3 Export - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Add an optional H3-indexed output adapter that converts pipeline `features.parquet` into an H3-indexed DataFrame at a configurable resolution. Delivered as:
- A Python function: `terraflow.export.to_h3(features, resolution=8)`
- A CLI subcommand: `terraflow export --format h3 -c config.yml`

`h3-py` stays optional (`[h3]` extra). The main pipeline is unchanged. H3 export is a post-pipeline adapter only — it reads an existing `features.parquet` and writes a new artifact alongside it.

</domain>

<decisions>
## Implementation Decisions

### Resolution Parameter (H3-03)
- **D-01:** H3 resolution lives in a new `export:` section in `config.yml` as the default value (`h3_resolution: 8`). The CLI `--resolution` flag overrides this at runtime.
- **D-02:** The **effective resolution** (CLI value if provided, else config value) is included in the run fingerprint computation. Two runs with different resolutions produce distinct `runs/<fingerprint>/` directories. This satisfies H3-03 cleanly — no special fingerprint injection needed when resolution is read from config.
- **D-03:** `ExportConfig` is a new Pydantic model (following `SensitivityConfig` / `ValidationConfig` patterns) added to `config.py`, with `h3_resolution: int = 8` and a field validator ensuring 0 ≤ resolution ≤ 15 (h3-py's valid range).

### Aggregation (H3-01)
- **D-04:** When multiple pipeline cells fall in the same H3 hex, all numeric columns (`score`, `v_index`, `mean_temp`, `total_rain`) are aggregated by **mean**.
- **D-05:** The `label` column (categorical) is aggregated by **mode** (most frequent label among cells in the hex).

### Output Columns (H3-01)
- **D-06:** The H3 DataFrame exposes all aggregated features: `h3_cell` (index), `score`, `v_index`, `mean_temp`, `total_rain`, `label`. This mirrors `features.parquet`'s schema minus the per-cell provenance columns (`run_id`, `cell_id`, `lat`, `lon`).

### Artifact Location (H3-04)
- **D-07:** `terraflow export` writes `h3_resolution_{N}.parquet` **inside the existing `runs/<fingerprint>/` directory** — co-located with `features.parquet`, `manifest.json`, and `report.json`. The fingerprint determines the run dir, and since resolution is part of the fingerprint, distinct resolutions land in distinct directories.

### Optional Dependency (H3-02)
- **D-08:** `h3-py` is added to `[project.optional-dependencies]` under an `h3` key in `pyproject.toml`. Follow the existing optional-dep import guard pattern from Phase 1: `try/except ImportError` at the top of `terraflow/export.py`, raising `ImportError("h3 required: pip install terraflow[h3]")` at call site if not installed.
- **D-09:** Target **h3-py v4.x** API (`latlng_to_cell`, `cell_to_latlng`). Latest available is 4.4.2. Do NOT use v3.x API (`geo_to_h3`). Pin `h3>=4.0,<5` in the optional dep spec.

### CLI Subcommand (H3-04)
- **D-10:** `terraflow export --format h3 -c config.yml` is the new Typer subcommand. It follows the `validate_cmd` pattern: `@app.command("export")`, late import of `terraflow.export.run_export` inside the function body.
- **D-11:** `--format` is a required CLI option (not positional). Even though only `h3` is supported in Phase 4, the `--format` flag reserves the interface for future formats (e.g., GeoJSON, CSV).
- **D-12:** `--resolution` is an optional CLI override. When provided, it supersedes `export.h3_resolution` from config.

### Public API (H3-01)
- **D-13:** `to_h3(features: pd.DataFrame, resolution: int = 8) -> pd.DataFrame` is the public function. It accepts the features DataFrame directly (not a config path), so callers can use it programmatically without a config file.
- **D-14:** `terraflow.export.to_h3` is exported from `terraflow/__init__.py` alongside `run_pipeline` and `run_validation`.

### Claude's Discretion
- Internal module structure: `terraflow/export.py` (single module) vs `terraflow/export/` (package) — Claude's call based on complexity.
- Whether `run_export(config_path, resolution_override=None)` is a thin wrapper around `to_h3()` or calls it internally — Claude decides the internal factoring.
- Exact h3-py call pattern for lat/lon → cell: `h3.latlng_to_cell(lat, lon, resolution)` per v4 API.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §H3 Export — H3-01 through H3-04 acceptance criteria

### Existing TerraFlow code
- `terraflow/cli.py` — existing `validate_cmd` pattern (late import, `@app.command`, `--config`/`-c` option); `export_cmd` follows this exactly
- `terraflow/config.py` — `PipelineConfig`, `SensitivityConfig`, `ValidationConfig` Pydantic models; add `ExportConfig` with `h3_resolution: int = 8`
- `terraflow/pipeline.py` — `features.parquet` schema (`run_id, cell_id, lat, lon, v_index, mean_temp, total_rain, score, label`); run dir is `output_dir/runs/<fingerprint>/`
- `terraflow/core/run_identity.py` — `compute_run_fingerprint(config_dict, roi_hash, input_fps)` — fingerprint must include effective H3 resolution
- `terraflow/__init__.py` — export `to_h3` here alongside existing exports
- `pyproject.toml` — `[project.optional-dependencies]` section; add `h3 = ["h3>=4.0,<5"]`

### h3-py v4 API
- Use `h3.latlng_to_cell(lat, lon, resolution)` to convert lat/lon to H3 cell ID
- Use `h3.cell_to_latlng(cell)` for reverse if needed
- Do NOT use `h3.geo_to_h3()` — that is the v3 API

### Prior phase conventions
- `.planning/phases/01-foundation-hardening/01-CONTEXT.md` §D-07/D-08 — optional-dep import guard pattern
- `.planning/phases/02-sensitivity-analysis/02-CONTEXT.md` §D-03 — CLI subcommand + late import pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `validate_cmd` in `cli.py` — direct template for `export_cmd` (late import, error handling, Typer option pattern)
- `SensitivityConfig` / `ValidationConfig` in `config.py` — template for `ExportConfig` Pydantic model
- `compute_run_fingerprint()` in `core/run_identity.py` — must be called with effective resolution included in config dict
- `_atomic_write_parquet()` in `pipeline.py` — use for writing `h3_resolution_{N}.parquet` atomically

### Established Patterns
- Optional dep guard: `try: import h3; _H3_AVAILABLE = True \nexcept ImportError: _H3_AVAILABLE = False` at module top; `raise ImportError(...)` at call site
- Config path resolution: `config_dir = config_path.parent; cfg.raster_path = config_dir / cfg.raster_path`
- 85% branch coverage floor enforced; new `export.py` needs tests

### Integration Points
- `to_h3()` reads a `features.parquet`-shaped DataFrame (columns: lat, lon, score, v_index, mean_temp, total_rain, label)
- Output lands in `runs/<fingerprint>/h3_resolution_{N}.parquet` — planner must resolve the run dir from config to find the right `features.parquet`
- `__init__.py` — add `from .export import to_h3` and include `"to_h3"` in `__all__`

</code_context>

<specifics>
## Specific Ideas

- The `--format` flag reserves the export interface for future formats — even though only `h3` is valid in Phase 4, the planner should include a validation error if an unsupported format is passed.
- Notebook example should demonstrate the DeckGL/Kepler.gl use case — the whole point of H3 export is interop with H3-native visualization tools.

</specifics>

<deferred>
## Deferred Ideas

- GeoJSON export format — future, not in Phase 4 scope
- CSV export format — future
- Aggregation function as a user-configurable parameter — deferred; mean is sufficient for JOSS

</deferred>

---

*Phase: 04-h3-export*
*Context gathered: 2026-04-02*
