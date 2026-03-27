# Coding Conventions

**Analysis Date:** 2026-03-18

## Naming Patterns

**Files:**
- Module names: lowercase with underscores (`geo.py`, `climate.py`, `run_identity.py`)
- Private/internal modules: leading underscore not used; intent conveyed via docstrings and location
- Test files: `test_<module>.py` pattern (e.g., `test_utils.py`, `test_climate.py`)

**Functions:**
- Public functions: lowercase with underscores (`clip_raster_to_roi`, `suitability_score`, `load_config`)
- Private/internal functions: leading underscore indicates intent (e.g., `_norm`, `_validate_columns`, `_interpolate_spatial`)
- Single-purpose test helpers: leading underscore (e.g., `_default_params()`, `_make_small_raster()`)
- Accessor methods in classes: PascalCase not used; standard snake_case even for properties (`validate_ranges`, `to_provenance`)

**Variables:**
- Local variables: lowercase with underscores (`raster_path`, `cell_id`, `mean_temp`)
- Constants (globals): UPPERCASE with underscores (`FEATURES_SCHEMA_VERSION`, `MANIFEST_SCHEMA_VERSION`, `MIN_KRIGING_STATIONS`)
- Type hints: fully qualified (`Dict[str, Any]`, `Literal["low", "medium", "high"]`)

**Types/Classes:**
- PascalCase for all classes (`ModelParams`, `ClimateInterpolator`, `RasterSummary`, `RunReport`)
- Pydantic models: inherit from `BaseModel` and include explicit `model_config = ConfigDict(extra="forbid")`
- Dataclass-like models: use Pydantic, not `@dataclass`

## Code Style

**Formatting:**
- Tool: Ruff (via `ruff-format`) + Black
- Line length: 120 characters (set in `pyproject.toml` under `[tool.ruff]`)
- Entry point: pre-commit hooks or `make lint-fix`

**Linting:**
- Tool: Ruff
- Rules selected: E, F, W, I (Error, Pyflakes, Warning, Isort)
- Rule ignored: E501 (line length — handled by formatter, not linter)
- Configuration: `pyproject.toml` under `[tool.ruff.lint]`
- Execution: `make lint` or `ruff check terraflow tests --fix`

**Type Checking:**
- Tool: mypy >= 1.10
- Configuration: `pyproject.toml` under `[tool.mypy]`
- Python version: 3.10+
- Settings enforced:
  - `warn_unused_ignores = true`
  - `warn_redundant_casts = true`
  - `warn_unused_configs = true`
  - `no_implicit_optional = true`
  - `ignore_missing_imports = true` (for optional geospatial libraries)
- Run: `make typecheck`

## Import Organization

**Order:**
1. Standard library (`import os`, `from pathlib import Path`)
2. Third-party packages (`import numpy`, `import pandas`, `from pydantic import BaseModel`)
3. Local/relative imports (`from .utils import logger`, `from .config import ModelParams`)

**Path Aliases:**
- Not used; all imports are absolute with relative prefixes (`.module` within package)

**Conventions:**
- `from __future__ import annotations` at the top of files that use forward references or PEP 563 style hints (seen in `pipeline.py`, `ingest.py`, `climate.py`)
- Type hints in docstrings and function signatures; quoted strings for forward references where needed
- Import entire modules for file I/O (`import os`, `import json`) rather than specific functions

## Error Handling

**Patterns:**
- Raise exceptions with descriptive messages: `raise ValueError(f"Latitude must be in [-90, 90], got {v}")`
- Chain exceptions when re-raising from context: `raise ValueError(...) from e`
- Specific exception types: `ValueError` for validation, `FileNotFoundError` for missing files, `ImportError` for optional dependencies
- Do not catch and silently ignore; always log or re-raise
- In CLI entry (`cli.py`): catch `FileNotFoundError`, `ValueError`, and generic `Exception`, log with `logger.error()`, print to `stderr`, then `sys.exit(1)`

**Example (from `cli.py`):**
```python
try:
    # operation
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    logger.error(f"Pipeline failed: {e}", exc_info=True)
    print(f"ERROR: Pipeline failed - {e}", file=sys.stderr)
    sys.exit(1)
```

## Logging

**Framework:** Python's standard `logging` module

**Setup:**
- Module-level logger: `logger = logging.getLogger("terraflow")` (seen in `utils.py`)
- Initialization: one-time setup with `basicConfig` if no handlers exist (guard: `if not logger.handlers:`)

**Patterns:**
- Use `logger.info()` for informational messages (e.g., "TerraFlow starting...", "Reprojected ROI from...")
- Use `logger.error()` for error messages with context (can include `exc_info=True` for tracebacks)
- Log before expensive operations or state changes
- Interpolate with f-strings: `logger.info(f"Processing {path}")`

**Example (from `geo.py`):**
```python
logger.info(
    "Reprojected ROI from %s to raster CRS %s: "
    "xmin=%.2f ymin=%.2f xmax=%.2f ymax=%.2f",
    roi_crs,
    raster_crs.to_epsg() or "custom",
    xmin,
    ymin,
    xmax,
    ymax,
)
```

## Comments

**When to Comment:**
- Explain *why*, not *what*: code is self-documenting where possible
- Complex algorithms or non-obvious logic: include brief comment
- Workarounds or hacks: mention reason and any ticket references
- Edge cases: explain why special handling is needed

**No `# TODO` comments:** Use GitHub issues or project tracking instead. TerraFlow codebase does not contain TODO/FIXME comments.

**JSDoc/TSDoc (NumPy-style docstrings for Python):**
- All public functions have docstrings
- All classes with public methods have module/class-level docstrings
- Format: NumPy docstring style (seen throughout codebase)

**Docstring structure:**
```python
def function_name(arg1: str, arg2: int) -> bool:
    """
    One-line summary.

    More detailed explanation if needed, spanning multiple sentences.
    Describe behavior, edge cases, or non-obvious implementation details.

    Parameters
    ----------
    arg1:
        Description of arg1.
    arg2:
        Description of arg2.

    Returns
    -------
    bool:
        Description of return value.

    Raises
    ------
    ValueError:
        Condition that triggers ValueError.

    Notes
    -----
    - Implementation detail 1
    - Implementation detail 2

    Examples
    --------
    >>> function_name("test", 42)
    True
    """
```

## Function Design

**Size:** Functions typically 10–60 lines; break complex logic into helpers with leading underscore (private)

**Parameters:**
- Use type hints: `def func(x: float, y: str) -> int:`
- Limit to 3–4 positional arguments; use dataclass/Pydantic model for many parameters
- Avoid `*args`, `**kwargs` except where flexibility is required (e.g., `BaseModel(**data)`)

**Return Values:**
- Single return type, clearly documented
- Use `Optional` for nullable returns: `-> Optional[float]`
- Return immutable structures (tuples, frozen dataclasses) from pure functions
- Return None explicitly; never rely on implicit None return

**Example (from `model.py`):**
```python
def suitability_score(
    v_index: float,
    mean_temp: float,
    total_rain: float,
    params: ModelParams,
) -> float:
    """Compute a simple suitability score in [0, 1]..."""
    v_n = normalize(v_index, params.v_min, params.v_max)
    t_n = normalize(mean_temp, params.t_min, params.t_max)
    r_n = normalize(total_rain, params.r_min, params.r_max)
    score = params.w_v * v_n + params.w_t * t_n + params.w_r * r_n
    return max(0.0, min(1.0, score))
```

## Module Design

**Exports:**
- All public modules define `__all__` listing public API (seen in `__init__.py`)
- Private modules do not export; prefix internal modules with underscore in imports if needed

**Barrel Files:**
- `terraflow/__init__.py` aggregates public API: imports key classes/functions, defines `__all__` and `__version__`

**Internal module organization:**
- `terraflow/core/` — core utilities (run identity, provenance, fingerprinting)
- Other `.py` files at `terraflow/` level — logical domains (geo, climate, model, stats, ingest, pipeline, viz)
- No deep nesting; single or two-level directory structure

**Example barrel file (from `__init__.py`):**
```python
from .config import PipelineConfig, load_config
from .pipeline import run_pipeline
from .stats import (...)

__all__ = [
    "PipelineConfig",
    "load_config",
    "run_pipeline",
    # ...
]

__version__ = "0.2.0"
```

---

*Convention analysis: 2026-03-18*
