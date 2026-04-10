# Phase 4: H3 Export - Research

**Researched:** 2026-04-02
**Domain:** h3-py v4, optional dependency pattern, Pydantic v2 config, Typer CLI, pandas aggregation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** H3 resolution lives in a new `export:` section in `config.yml` as the default value (`h3_resolution: 8`). The CLI `--resolution` flag overrides this at runtime.
- **D-02:** The effective resolution (CLI value if provided, else config value) is included in the run fingerprint computation. Two runs with different resolutions produce distinct `runs/<fingerprint>/` directories.
- **D-03:** `ExportConfig` is a new Pydantic model added to `config.py`, with `h3_resolution: int = 8` and a field validator ensuring 0 ≤ resolution ≤ 15.
- **D-04:** When multiple pipeline cells fall in the same H3 hex, all numeric columns (`score`, `v_index`, `mean_temp`, `total_rain`) are aggregated by **mean**.
- **D-05:** The `label` column is aggregated by **mode** (most frequent label among cells in the hex).
- **D-06:** Output columns: `h3_cell` (index), `score`, `v_index`, `mean_temp`, `total_rain`, `label`. Mirrors `features.parquet` schema minus per-cell provenance (`run_id`, `cell_id`, `lat`, `lon`).
- **D-07:** `terraflow export` writes `h3_resolution_{N}.parquet` inside the existing `runs/<fingerprint>/` directory.
- **D-08:** `h3-py` is added to `[project.optional-dependencies]` under an `h3` key in `pyproject.toml`. `try/except ImportError` at module top; raise `ImportError("h3 required: pip install terraflow[h3]")` at call site.
- **D-09:** Target **h3-py v4.x** API (`latlng_to_cell`, `cell_to_latlng`). Latest is 4.4.2. Do NOT use v3.x API (`geo_to_h3`). Pin `h3>=4.0,<5`.
- **D-10:** `terraflow export --format h3 -c config.yml` follows the `validate_cmd` pattern: `@app.command("export")`, late import of `terraflow.export.run_export` inside function body.
- **D-11:** `--format` is a required CLI option. Only `h3` is valid in Phase 4; pass unsupported formats as a validation error.
- **D-12:** `--resolution` is an optional CLI override; supersedes `export.h3_resolution` from config.
- **D-13:** `to_h3(features: pd.DataFrame, resolution: int = 8) -> pd.DataFrame` is the public function.
- **D-14:** `terraflow.export.to_h3` is exported from `terraflow/__init__.py` alongside `run_pipeline` and `run_validation`.

### Claude's Discretion

- Internal module structure: `terraflow/export.py` (single module) vs `terraflow/export/` (package).
- Whether `run_export(config_path, resolution_override=None)` is a thin wrapper around `to_h3()` or calls it internally.
- Exact h3-py call pattern: `h3.latlng_to_cell(lat, lon, resolution)` per v4 API.

### Deferred Ideas (OUT OF SCOPE)

- GeoJSON export format
- CSV export format
- Aggregation function as user-configurable parameter
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| H3-01 | User can call `terraflow.export.to_h3(features, resolution=8)` and receive a DataFrame indexed by H3 cell ID with scores aggregated within each cell | h3-py v4 `latlng_to_cell`, pandas groupby mean + mode pattern documented below |
| H3-02 | `h3-py` is optional; calling without it raises `ImportError` with `pip install terraflow[h3]` message | `viz.py` import-at-call-site pattern is the exact template |
| H3-03 | H3 resolution parameter is included in run fingerprint so different resolutions produce distinct cached artifacts | `compute_run_fingerprint(config_dict, ...)` uses `canonicalize_config()` which JSON-serializes the entire config dict; adding `export.h3_resolution` to the config section means it is automatically included |
| H3-04 | User can run `terraflow export --format h3 -c config.yml` from the CLI | `validate_cmd` pattern is the direct template |
</phase_requirements>

---

## Summary

Phase 4 adds an optional H3-indexed export adapter as a post-pipeline step. The implementation is small and follows three established TerraFlow patterns: (1) optional-dep import guard from `viz.py`, (2) config model from `SensitivityConfig`/`ValidationConfig`, and (3) CLI subcommand from `validate_cmd`. The only new technical territory is h3-py v4 API usage and pandas mode aggregation for the categorical `label` column.

The fingerprint requirement (H3-03) is handled automatically by D-02: since `export.h3_resolution` lives in the YAML config dict and `compute_run_fingerprint` hashes the entire canonicalized config JSON, any change to `h3_resolution` produces a new fingerprint with no special injection code needed.

The main complexity is `run_export`: it must (a) resolve the run directory from the config the same way `validate` does via `resolve_run_dir`, (b) read `features.parquet`, (c) determine the effective resolution (CLI override vs config), (d) call `to_h3()`, and (e) write `h3_resolution_{N}.parquet` atomically using `_atomic_write_parquet` from `pipeline.py`.

**Primary recommendation:** Single-file `terraflow/export.py`. Use `resolve_run_dir` from `pipeline.py` to locate the run dir; import `_atomic_write_parquet` from `pipeline.py` for artifact writing. `to_h3()` is the pure transformation function; `run_export()` is the orchestrator.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| h3 | 4.4.2 (latest) | Lat/lon → H3 cell index | Official Uber H3 Python binding |
| pandas | >=1.3.0 (already in deps) | groupby aggregation | Already core dependency |
| pyarrow | >=14.0 (already in deps) | Parquet write | Already core dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic v2 | >=2.0 (already in deps) | `ExportConfig` model | Already core dependency |
| typer | >=0.12.5 (already in deps) | `export_cmd` subcommand | Already core dependency |

**Installation (for h3 optional extra):**
```bash
pip install terraflow[h3]
```

**pyproject.toml addition:**
```toml
[project.optional-dependencies]
h3 = ["h3>=4.0,<5"]
viz = ["plotly>=5.0.0"]
```

**Version verification:** `pip index versions h3` confirmed 4.4.2 is the current release (verified 2026-04-02). The jump from 3.x to 4.x is a breaking API change — v3 uses `geo_to_h3`, v4 uses `latlng_to_cell`.

---

## h3-py v4 API

**Confidence: HIGH** — Verified via PyPI page, official h3geo.org docs, and GitHub issue #292 confirmation.

### Key Functions

```python
# Convert lat/lon to H3 cell at a given resolution
h3.latlng_to_cell(lat: float, lng: float, resolution: int) -> str
# Returns: H3 cell ID string, e.g. '89283082e73ffff'

# Reverse: cell ID to center lat/lng
h3.cell_to_latlng(cell: str) -> tuple[float, float]
# Returns: (lat, lng) tuple

# Cell boundary (for visualization)
h3.cell_to_boundary(cell: str) -> tuple[tuple[float, float], ...]
# Returns: tuple of (lat, lng) pairs
```

### Version Pin Strategy
- Pin: `h3>=4.0,<5` — locks to v4.x, excludes future breaking v5.x changes
- Current latest: `4.4.2` (verified via `pip index versions h3`)
- v3.x API (`geo_to_h3`) must NOT be used; it is absent in v4

### Usage Pattern for DataFrame
```python
# Source: h3geo.org indexing docs, PyPI page example
import h3

# Convert a DataFrame column pair to H3 cells
cells = [h3.latlng_to_cell(lat, lon, resolution) for lat, lon in zip(df["lat"], df["lon"])]
```

Using a list comprehension rather than `df.apply(lambda r: h3.latlng_to_cell(...), axis=1)` is preferred — it avoids pandas axis=1 overhead for pure Python-level function calls.

### Valid Resolution Range
- `0` (coarsest, ~4M km² cells) to `15` (finest, ~0.9 m² cells)
- Resolution 8 is the default (avg area ~0.74 km²)
- `ExportConfig` validator must enforce `0 <= resolution <= 15`

---

## Optional Dependency Pattern

**Confidence: HIGH** — Verified from `terraflow/viz.py` (the established Phase 1 pattern).

The exact pattern already in use in this codebase (from `viz.py`):

```python
# At call site (NOT at module top)
try:
    import plotly.express as px
except ImportError as e:
    raise ImportError(
        "plotly is required for visualization. "
        "Install with: pip install terraflow[viz]"
    ) from e
```

`viz.py` does NOT use a module-level `_AVAILABLE` flag — it raises at the call site. The CONTEXT.md describes an `_AVAILABLE` flag approach, but the actual codebase uses the simpler call-site pattern. Both work; the call-site pattern is what's already established.

**Recommendation for `export.py`:** Use the same call-site import guard as `viz.py`:
```python
# At the top of to_h3():
try:
    import h3 as _h3
except ImportError as exc:
    raise ImportError(
        "h3 is required for H3 export. "
        "Install with: pip install terraflow[h3]"
    ) from exc
```

**Test pattern for optional deps** — from `test_viz.py`:
```python
pytest.importorskip("plotly")  # skip entire test file if dep absent
```
For `test_export.py`: use `pytest.importorskip("h3")` to skip H3-specific tests when h3 is not installed. Add one test that asserts `ImportError` is raised when h3 is mocked as unimportable.

---

## Fingerprint Injection

**Confidence: HIGH** — Verified by reading `pipeline.py`, `core/run_identity.py`, and `validation.py`.

### How the fingerprint works

`compute_run_fingerprint(config_dict, roi_hash, input_fingerprints)` in `core/run_identity.py`:
1. Calls `canonicalize_config(config_dict)` — produces sorted JSON bytes of the entire config dict
2. Computes SHA256 of that JSON
3. Combines config hash + roi hash + input file hashes into a final base64url digest

**Key insight:** The `config_dict` is the raw YAML dict (loaded by `load_config_dict`). If `export.h3_resolution: 8` is present in the YAML, it is in the dict and automatically included in the hash. No special injection code is needed.

### How `run_export` must compute the run dir

`run_export` must use the same resolution-aware config dict when calling `resolve_run_dir`. The effective resolution (CLI override or config value) must be set into the config dict **before** calling `resolve_run_dir`:

```python
# Pattern from validation.py:
from .pipeline import resolve_run_dir

def run_export(config_path: Path, resolution_override: int | None = None) -> Path:
    data = load_config_dict(config_path)
    # Inject effective resolution before fingerprint computation
    if resolution_override is not None:
        if "export" not in data:
            data["export"] = {}
        data["export"]["h3_resolution"] = resolution_override
    # Now resolve_run_dir will use the right fingerprint
    run_dir = resolve_run_dir(config_path)  # NOTE: see issue below
    ...
```

**Issue:** `resolve_run_dir(config_path)` re-loads the config dict from disk — it does not accept a pre-mutated dict. So if `--resolution` is provided as a CLI override, `run_export` cannot use `resolve_run_dir` directly without modification.

**Solutions (Claude's discretion):**
1. Duplicate the fingerprint computation inline (copy the pattern from `resolve_run_dir`) with the modified config dict — safest, no changes to `pipeline.py`
2. Add a `resolve_run_dir_from_dict(config_dict, config_dir)` helper to `pipeline.py` — cleaner but touches `pipeline.py`

The simpler path is option 1: copy the resolution-adjusted `config_dict` through the fingerprint computation manually in `run_export`, following the exact same steps as `resolve_run_dir`.

---

## CLI Subcommand Pattern

**Confidence: HIGH** — Verified from `terraflow/cli.py`.

### `validate_cmd` is the direct template

```python
@app.command("validate")
def validate_cmd(
    config: Annotated[
        Path,
        typer.Option(..., "--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run model validation (spatial CV, Cohen's kappa, Moran's I)."""
    logger.info(f"TerraFlow validation starting with config: {config}")
    try:
        from .validation import run_validation
        run_validation(config)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        print(f"ERROR: Validation failed - {e}", file=sys.stderr)
        raise SystemExit(1)
    logger.info("TerraFlow validation completed successfully")
```

### `export_cmd` additions beyond `validate_cmd`

Two new parameters vs `validate_cmd`:

```python
@app.command("export")
def export_cmd(
    config: Annotated[Path, typer.Option(..., "--config", "-c", ...)],
    format: Annotated[str, typer.Option(..., "--format", help="Export format (h3)")],
    resolution: Annotated[Optional[int], typer.Option(None, "--resolution", help="H3 resolution (0-15); overrides config")] = None,
) -> None:
    """Export pipeline results to H3-indexed format."""
    if format != "h3":
        print(f"ERROR: Unsupported format '{format}'. Supported: h3", file=sys.stderr)
        raise SystemExit(1)
    try:
        from .export import run_export
        run_export(config, resolution_override=resolution)
    except ImportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as e:
        ...
```

**Key differences from `validate_cmd`:**
- `--format` is required (no default) — raises SystemExit(1) for unsupported values
- `--resolution` is optional with default `None`
- `ImportError` must be caught explicitly (h3 may not be installed)
- Late import: `from .export import run_export` inside function body

---

## Aggregation Strategy

**Confidence: HIGH** — Standard pandas groupby patterns.

### Numeric columns: mean
```python
numeric_cols = ["score", "v_index", "mean_temp", "total_rain"]
agg_dict = {col: "mean" for col in numeric_cols}
```

### Categorical column: mode
`pandas.Series.mode()` returns a Series (may have multiple values on ties). Take the first:
```python
agg_dict["label"] = lambda s: s.mode().iloc[0] if not s.empty else None
```

### Full aggregation pattern
```python
def to_h3(features: pd.DataFrame, resolution: int = 8) -> pd.DataFrame:
    try:
        import h3 as _h3
    except ImportError as exc:
        raise ImportError(
            "h3 is required for H3 export. "
            "Install with: pip install terraflow[h3]"
        ) from exc

    if resolution < 0 or resolution > 15:
        raise ValueError(f"resolution must be 0–15, got {resolution}")

    required = {"lat", "lon", "score", "v_index", "mean_temp", "total_rain", "label"}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"features DataFrame missing columns: {sorted(missing)}")

    cells = [_h3.latlng_to_cell(lat, lon, resolution)
             for lat, lon in zip(features["lat"], features["lon"])]
    df = features.copy()
    df["h3_cell"] = cells

    numeric_cols = ["score", "v_index", "mean_temp", "total_rain"]
    agg_dict = {col: "mean" for col in numeric_cols}
    agg_dict["label"] = lambda s: s.mode().iloc[0] if not s.empty else None

    result = df.groupby("h3_cell", sort=False).agg(agg_dict).reset_index()
    return result[["h3_cell"] + numeric_cols + ["label"]]
```

### Edge case: empty DataFrame
If `features` is empty, `groupby().agg()` returns an empty DataFrame. This is correct behavior — no special handling needed. Test this explicitly.

### Edge case: single cell per hex
When no cells share a hex, each group has size 1. Mean and mode of a single value are that value. Correct.

### Edge case: mode tie
`Series.mode()` returns all tied values sorted. Taking `.iloc[0]` gives a deterministic (alphabetical) winner. For `label` values `"high"`, `"low"`, `"medium"`, ties resolve alphabetically: `"high"` < `"low"` < `"medium"`. This is acceptable for JOSS — document it as a note in the function docstring.

---

## Config Model

**Confidence: HIGH** — Direct from `config.py` analysis.

### `ExportConfig` follows `ValidationConfig`

`ValidationConfig` is the simplest existing config model and is the direct template:

```python
class ValidationConfig(BaseModel):
    """Configuration for model validation (Phase 3)."""
    n_blocks_side: int = 4
    buffer_deg: float = 0.5
    reference_csv: Optional[str] = None
    model_config = ConfigDict(extra="forbid")
```

`ExportConfig` follows the same pattern:

```python
class ExportConfig(BaseModel):
    """Configuration for H3 export (Phase 4)."""
    h3_resolution: int = 8
    model_config = ConfigDict(extra="forbid")

    @field_validator("h3_resolution")
    @classmethod
    def validate_h3_resolution(cls, v: int) -> int:
        if v < 0 or v > 15:
            raise ValueError(f"h3_resolution must be 0–15, got {v}")
        return v
```

### `PipelineConfig` addition

```python
class PipelineConfig(BaseModel):
    ...
    sensitivity: Optional[SensitivityConfig] = None
    validation: Optional[ValidationConfig] = None
    export: Optional[ExportConfig] = None  # add this
```

### YAML config section
```yaml
export:
  h3_resolution: 8
```

---

## Architecture Patterns

### Recommended Module Structure

Use a single-file `terraflow/export.py` — the feature is not complex enough to warrant a package. This matches how `viz.py`, `sensitivity.py`, and `validation.py` are all single files.

```
terraflow/
├── export.py        # new: to_h3(), run_export()
├── cli.py           # modified: add export_cmd
├── config.py        # modified: add ExportConfig, add export field to PipelineConfig
├── __init__.py      # modified: export to_h3
```

### Module responsibility split

```
to_h3(features: pd.DataFrame, resolution: int = 8) -> pd.DataFrame
  - Pure transformation: no I/O, no config
  - Validates h3 is installed
  - Validates resolution range
  - Validates required columns
  - Applies latlng_to_cell and groupby aggregation
  - Returns h3-indexed DataFrame

run_export(config_path: Path | str, resolution_override: int | None = None) -> Path
  - Orchestrator: reads config, resolves run_dir, reads features.parquet
  - Determines effective resolution (override or config default)
  - Calls to_h3()
  - Writes h3_resolution_{N}.parquet atomically
  - Returns path to written artifact
```

### Artifact write pattern (from `pipeline.py`)

`_atomic_write_parquet` is not exported from `pipeline.py` (it is module-private). Options:
1. Import it with `from .pipeline import _atomic_write_parquet` — works but couples to private API
2. Replicate the 15-line pattern inline in `export.py` — avoids coupling, adds minor duplication

Given the simplicity, option 1 is acceptable (same package, same author). The validation module already imports `resolve_run_dir` from `pipeline.py` so this coupling is established.

The h3 artifact metadata should use a distinct schema key:
```python
schema_meta = {"h3_resolution": str(resolution), "h3_schema_version": "1"}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lat/lon → hex cell | Custom hex grid | `h3.latlng_to_cell` | H3 handles projection, compactness, all resolutions |
| Groupby mode | Custom mode function | `pd.Series.mode().iloc[0]` | Handles ties, empty series, dtype-safe |
| Atomic parquet write | Custom temp+rename | `_atomic_write_parquet` from `pipeline.py` | Already handles pyarrow metadata merging |
| Run dir resolution | Manual fingerprint calculation | `resolve_run_dir` (or inline copy) | Ensures consistency with `pipeline.py` |

---

## Test Strategy

**Confidence: HIGH** — Based on test file analysis and established patterns.

### Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_export.py -v` |
| Full suite command | `pytest --cov=terraflow --cov-report=term-missing` |
| Coverage floor | 85% branch coverage (enforced by `fail_under = 85`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| H3-01 | `to_h3()` returns correct H3-indexed DataFrame | unit | `pytest tests/test_export.py::test_to_h3_basic -v` | Wave 0 |
| H3-01 | Numeric columns aggregated by mean | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mean -v` | Wave 0 |
| H3-01 | Label column aggregated by mode | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mode -v` | Wave 0 |
| H3-01 | Empty DataFrame returns empty result | unit | `pytest tests/test_export.py::test_to_h3_empty_dataframe -v` | Wave 0 |
| H3-01 | Missing required columns raises ValueError | unit | `pytest tests/test_export.py::test_to_h3_missing_columns -v` | Wave 0 |
| H3-02 | `to_h3()` without h3 installed raises ImportError with install hint | unit | `pytest tests/test_export.py::test_to_h3_importerror -v` | Wave 0 |
| H3-02 | ImportError message contains `pip install terraflow[h3]` | unit | included in above | Wave 0 |
| H3-03 | Different resolutions produce different run fingerprints | unit | `pytest tests/test_export.py::test_resolution_changes_fingerprint -v` | Wave 0 |
| H3-04 | `export --format h3 -c config.yml` CLI succeeds | integration | `pytest tests/test_cli.py::TestExportCLI::test_export_h3_success -v` | Wave 0 |
| H3-04 | `export --format csv` raises SystemExit(1) with error message | unit | `pytest tests/test_cli.py::TestExportCLI::test_export_unsupported_format -v` | Wave 0 |
| H3-04 | `export --help` shows usage | unit | `pytest tests/test_cli.py::TestExportCLI::test_export_help -v` | Wave 0 |
| H3-04 | `h3_resolution_{N}.parquet` is written to correct run dir | integration | `pytest tests/test_export.py::test_run_export_artifact_location -v` | Wave 0 |

### Key fixtures available (from `conftest.py`)
- `synthetic_raster` — 5×5 GeoTIFF in EPSG:4326, cells at ~lat 40 lon -100
- `synthetic_climate_csv` / `*_dense` / `*_sparse` — climate station data
- `tmp_path` — all tests use tmp_path for isolation

### `features`-like fixture for `to_h3()` unit tests
`to_h3()` takes a DataFrame directly — no pipeline run needed. Create a small synthetic features DataFrame in the test:
```python
@pytest.fixture
def features_df():
    return pd.DataFrame({
        "lat": [40.0, 40.001, 40.005],
        "lon": [-100.0, -100.001, -100.005],
        "score": [0.7, 0.8, 0.6],
        "v_index": [10.0, 12.0, 8.0],
        "mean_temp": [18.0, 19.0, 17.0],
        "total_rain": [100.0, 110.0, 90.0],
        "label": ["high", "high", "medium"],
    })
```

At resolution 8, nearby lat/lon points (0.001° apart) will likely resolve to the same H3 cell — verify aggregation is triggered.

### Test for ImportError (H3-02)
```python
def test_to_h3_importerror(features_df, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "h3", None)
    from terraflow import export
    importlib.reload(export)  # may need module reload
    with pytest.raises(ImportError, match="pip install terraflow\\[h3\\]"):
        export.to_h3(features_df, resolution=8)
```

Alternatively, use `unittest.mock.patch` to make `h3` unavailable at import time in the function body.

### Sampling rate
- Per task commit: `pytest tests/test_export.py -v`
- Per wave merge: `pytest --cov=terraflow --cov-report=term-missing`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_export.py` — covers H3-01, H3-02, H3-03, H3-04 (artifact location)
- [ ] `tests/test_cli.py` additions — `TestExportCLI` class for H3-04 CLI tests

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-cov |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_export.py -v` |
| Full suite command | `make test-cov` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| H3-01 | `to_h3()` returns correct columns and H3-indexed structure | unit | `pytest tests/test_export.py -k "to_h3" -x` | Wave 0 |
| H3-01 | Mean aggregation for numeric columns | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mean -x` | Wave 0 |
| H3-01 | Mode aggregation for label | unit | `pytest tests/test_export.py::test_to_h3_aggregation_mode -x` | Wave 0 |
| H3-02 | ImportError with install hint when h3 absent | unit | `pytest tests/test_export.py::test_to_h3_importerror -x` | Wave 0 |
| H3-03 | Different resolutions → different fingerprints | unit | `pytest tests/test_export.py::test_resolution_changes_fingerprint -x` | Wave 0 |
| H3-04 | CLI `export --format h3` succeeds end-to-end | integration | `pytest tests/test_cli.py -k "export" -x` | Wave 0 |
| H3-04 | CLI `export --format csv` exits 1 | unit | `pytest tests/test_cli.py -k "unsupported_format" -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_export.py -v`
- **Per wave merge:** `make test-cov`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_export.py` — all H3-01, H3-02, H3-03, unit-level artifact tests
- [ ] `tests/test_cli.py` — `TestExportCLI` class additions for H3-04

---

## Common Pitfalls

### Pitfall 1: h3-py v3 vs v4 API confusion
**What goes wrong:** Code uses `h3.geo_to_h3(lat, lon, resolution)` (v3 API), which does not exist in v4.
**Why it happens:** Most StackOverflow answers and pre-2022 tutorials use v3 API.
**How to avoid:** Always use `h3.latlng_to_cell(lat, lon, resolution)` — this is the only correct form for h3>=4.0.
**Warning signs:** `AttributeError: module 'h3' has no attribute 'geo_to_h3'`

### Pitfall 2: Argument order in `latlng_to_cell`
**What goes wrong:** Passing `(lon, lat, resolution)` instead of `(lat, lon, resolution)`.
**Why it happens:** GeoJSON uses (lon, lat) order; h3-py uses geographic (lat, lon) order.
**How to avoid:** `features.parquet` columns are `lat` and `lon`; use them in that order: `h3.latlng_to_cell(row.lat, row.lon, resolution)`.
**Warning signs:** H3 cells returned for distant regions, no obvious error.

### Pitfall 3: `resolve_run_dir` does not accept a modified config dict
**What goes wrong:** `run_export` modifies `config_dict["export"]["h3_resolution"]` but then calls `resolve_run_dir(config_path)` which re-reads the config from disk — the modification is lost and the fingerprint is wrong.
**Why it happens:** `resolve_run_dir` takes a path, not a dict.
**How to avoid:** Inline the fingerprint computation in `run_export` using the modified dict, following the same steps as `resolve_run_dir` but operating on the pre-mutated dict.
**Warning signs:** CLI `--resolution 10` writes to the same directory as `--resolution 8` config default.

### Pitfall 4: `pandas.Series.mode()` returning multiple values
**What goes wrong:** `df.groupby("h3_cell")["label"].agg(lambda s: s.mode())` returns a Series of Series, crashing with a reshape error.
**Why it happens:** `mode()` returns all tied modes, not a scalar.
**How to avoid:** Use `lambda s: s.mode().iloc[0] if not s.empty else None` to always extract a single value.
**Warning signs:** `ValueError: cannot insert label` or `DataError: No numeric types to aggregate`.

### Pitfall 5: `h3_resolution_8.parquet` filename with underscore vs other separators
**What goes wrong:** Inconsistent filename format makes artifacts hard to glob programmatically.
**Why it happens:** Naming is Claude's discretion; no prior convention in the codebase.
**How to avoid:** Locked by D-07: use `h3_resolution_{N}.parquet` exactly. `N` is the integer resolution, no zero-padding.

### Pitfall 6: Coverage gap from `pytest.importorskip`
**What goes wrong:** All H3 export tests are skipped when h3 is not installed in CI, causing coverage to drop below 85%.
**Why it happens:** `pytest.importorskip("h3")` skips the entire module.
**How to avoid:** Only use `pytest.importorskip("h3")` for tests that truly need h3 installed. The ImportError test (`test_to_h3_importerror`) must mock h3 absence rather than require h3 absence — it should run in all environments.

---

## Risks and Edge Cases

### Risk 1: `_atomic_write_parquet` import from `pipeline.py` (MEDIUM)
`_atomic_write_parquet` is a private function in `pipeline.py`. Importing it works but couples `export.py` to `pipeline.py` internals. The risk is low (same package, no external callers), but if the function signature changes in Phase 5, both files need updating.

**Mitigation:** Accept the coupling. Document the dependency in `export.py` with a comment. Alternatively, inline the 15 lines of atomic write logic.

### Risk 2: Run dir not found (MEDIUM)
If the user runs `terraflow export` before `terraflow run`, `features.parquet` will not exist. The error handling must produce a clear message.
**Mitigation:** Check for `features_path.exists()` and raise `FileNotFoundError` with a message directing the user to run `terraflow run -c config.yml` first (same pattern as `validation.py` line 281).

### Risk 3: h3 not installed in CI/test environment (LOW)
If h3 is not in the dev dependencies, all H3 functional tests will be skipped, masking coverage gaps.
**Mitigation:** Add `h3>=4.0,<5` to the `dev` optional dependency group in `pyproject.toml` so it is installed in the test environment.

### Risk 4: Large features.parquet with many distinct H3 cells (LOW)
At resolution 8, aggregation may produce a DataFrame nearly as large as the input (if cells are spread far apart). This is expected and not a problem for JOSS-scale datasets.

---

## Implementation Order

Recommended plan breakdown into 3 plans:

### Plan 04-01: Config, pyproject.toml, and `export.py` core function
**Files touched:** `pyproject.toml`, `terraflow/config.py`, `terraflow/export.py`, `terraflow/__init__.py`
**What it delivers:** `to_h3()` as a testable unit; `ExportConfig` Pydantic model; h3 optional dep wired
**Tests:** `tests/test_export.py` with unit tests for H3-01 and H3-02

### Plan 04-02: `run_export` orchestrator and artifact writing
**Files touched:** `terraflow/export.py` (addition), `tests/test_export.py` (addition)
**What it delivers:** `run_export(config_path, resolution_override)` that reads features.parquet, calls `to_h3()`, writes `h3_resolution_{N}.parquet`
**Tests:** Integration test for artifact location (H3-03 fingerprint test)

### Plan 04-03: CLI subcommand, demo config, notebook, human verification
**Files touched:** `terraflow/cli.py`, `tests/test_cli.py`, `examples/`, `notebooks/`, `docs/`, `README.md`, `CHANGELOG.md`
**What it delivers:** `export_cmd`, demo YAML, DeckGL/Kepler.gl notebook, human verification (H3-04)
**Tests:** CLI tests in `TestExportCLI` class

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| h3 | H3 export feature | Not installed | — | Feature is optional; tests skip via `pytest.importorskip("h3")` |
| pytest | Test framework | Available (in dev deps) | >=7.0 | — |
| pandas | Aggregation | Available (core dep) | >=1.3.0 | — |
| pyarrow | Parquet write | Available (core dep) | >=14.0 | — |

**Missing dependencies with no fallback:**
- None — h3 absence is expected (it is an optional dep); all other dependencies are already in core or dev.

**Missing dependencies with fallback:**
- `h3`: not installed on this machine; must be installed via `pip install terraflow[h3]` for end-to-end testing. Tests that require h3 must use `pytest.importorskip("h3")`. Add `h3>=4.0,<5` to the `dev` extra in `pyproject.toml` to ensure CI runs H3 tests.

---

## Project Constraints (from CLAUDE.md)

These must be verified by the planner:

| Constraint | Impact on Phase 4 |
|------------|-------------------|
| Line length 120 chars (`ruff`/`black`) | All new code in `export.py`, `cli.py`, `config.py` must respect 120-char limit |
| `make lint` must pass (`ruff check + black`) | Run before any commit; pre-commit hooks enforce this |
| Coverage floor 85% (`fail_under = 85`) | `export.py` needs thorough branch coverage; `pytest.importorskip` can't hide too many tests |
| `make typecheck` (`mypy`) | `export.py` must have proper type annotations; `to_h3` return type is `pd.DataFrame` |
| Pre-commit hooks run ruff + black on staged files | Auto-enforced; no manual action needed |
| Every PR must update `README.md` (sparse) | Phase 4 PR: one-liner mentioning H3 export feature |
| Every PR must add/update `docs/` (detailed) | New `docs/h3-export.md` page documenting the feature |
| Every PR must add Jupyter notebook in `notebooks/` | DeckGL/Kepler.gl demo notebook required |
| Every PR must update `mkdocs.yml` nav | Add H3 export page to nav |
| Every PR must add entry to `CHANGELOG.md` under `[Unreleased]` | Add H3 export entry |
| CRS invariant: always EPSG:4326 | `features.parquet` already in WGS84; h3 uses lat/lon directly — no reprojection needed |
| Artifacts under `output_dir/runs/<fingerprint>/` | `h3_resolution_{N}.parquet` co-located in run dir, not a new directory level |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `h3.geo_to_h3(lat, lon, res)` | `h3.latlng_to_cell(lat, lon, res)` | h3-py v4.0 (2022) | Must use new API; old name raises AttributeError in v4 |
| `h3.h3_to_geo(cell)` | `h3.cell_to_latlng(cell)` | h3-py v4.0 | Same breaking rename |

**Deprecated/outdated:**
- `h3.geo_to_h3`: removed in v4; replaced by `latlng_to_cell`
- `h3.polyfill`: replaced by `h3.polygon_to_cells` in v4 (not relevant to this phase)
- `h3pandas` library: provides H3 pandas accessor, but is an additional dependency; not needed given Phase 4's simple use case

---

## Open Questions

1. **Should `h3` be added to `dev` extras so CI runs H3 tests?**
   - What we know: the `dev` extra is used by `make dev` to install the test environment; h3 is not currently there
   - What's unclear: whether CI / the Makefile runs `pip install .[dev]` or `pip install .[dev,h3]`
   - Recommendation: Add `h3>=4.0,<5` to the `dev` extra in `pyproject.toml` so that `make dev` installs it and H3 tests run by default. The optional dep mechanic is preserved for end users; the dev environment just installs it.

2. **Should `_atomic_write_parquet` be imported from `pipeline.py` or duplicated?**
   - What we know: it is a 15-line private helper; `validation.py` already imports `resolve_run_dir` from `pipeline.py`
   - What's unclear: whether there is a plan to extract shared I/O helpers to a `utils.py`
   - Recommendation: Import from `pipeline.py` for now (same pattern as `resolve_run_dir` in `validation.py`). No Phase 5 work depends on this.

---

## Sources

### Primary (HIGH confidence)
- h3geo.org/docs/api/indexing — `latlng_to_cell`, `cell_to_latlng`, resolution range 0–15
- pypi.org/project/h3 — current version 4.4.2, code example, API overview
- `terraflow/viz.py` (local) — established optional-dep import guard pattern
- `terraflow/cli.py` (local) — `validate_cmd` template for `export_cmd`
- `terraflow/config.py` (local) — `ValidationConfig`/`SensitivityConfig` templates for `ExportConfig`
- `terraflow/core/run_identity.py` (local) — `compute_run_fingerprint` behavior
- `terraflow/pipeline.py` (local) — `_atomic_write_parquet`, `resolve_run_dir`, artifact location pattern
- `pyproject.toml` (local) — existing optional deps, coverage floor, ruff/mypy config

### Secondary (MEDIUM confidence)
- github.com/uber/h3-py/issues/292 — confirms `latlng_to_cell` is v4 API and `geo_to_h3` is v3
- `pip index versions h3` (command run) — confirmed 4.4.2 is current latest

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- h3-py v4 API: HIGH — verified via official docs and GitHub issue confirmation
- Optional dep pattern: HIGH — copied from existing `viz.py`
- Fingerprint injection: HIGH — verified by reading `compute_run_fingerprint` source
- CLI pattern: HIGH — copied from existing `validate_cmd`
- Aggregation strategy: HIGH — standard pandas patterns
- Config model: HIGH — direct template from `ValidationConfig`
- Test strategy: HIGH — mirrors existing `test_viz.py` and `test_validation.py` patterns

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (h3-py v4.x is stable; no imminent breaking changes expected before JOSS submission)

---

## RESEARCH COMPLETE
