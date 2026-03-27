# TESTING.md — TerraFlow Test Structure and Practices

## Framework

- **pytest** — primary test framework
- **pytest-cov** — coverage reporting
- **Coverage target**: 85% branch coverage (`fail_under = 85` in `pyproject.toml`)
- **Coverage source**: `terraflow/` package only (tests excluded)

## Test Location

All tests live in `tests/`. No inline tests in source modules.

```
tests/
├── conftest.py             # Shared fixtures
├── data/                   # Small static test data files
├── smoke_test.py           # Real-data tests (conditional skip)
├── test_artifacts.py       # Artifact contract (parquet + JSON schemas)
├── test_cli.py             # Typer CLI commands
├── test_climate.py         # ClimateInterpolator (unit + integration)
├── test_config.py          # Pydantic config validation
├── test_determinism.py     # Run determinism regression
├── test_e2e_smoke.py       # End-to-end with synthetic data
├── test_geo.py             # Geospatial operations
├── test_ingest.py          # Raster/CSV ingestion
├── test_model.py           # Suitability scoring
├── test_pipeline.py        # Pipeline orchestration
├── test_run_identity.py    # Run fingerprint / DataCatalog
├── test_stats.py           # Raster statistics
├── test_uncertainty.py     # Monte Carlo uncertainty propagation
├── test_utils.py           # Utility helpers
└── test_viz.py             # Visualization
```

## Pytest Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
    "smoke: end-to-end smoke tests using synthetic data (run with: pytest -m smoke)",
]

[tool.coverage.run]
branch = true
source = ["terraflow"]
omit = ["tests/*"]

[tool.coverage.report]
show_missing = true
skip_covered = true
fail_under = 85
```

## Shared Fixtures (`tests/conftest.py`)

Fixtures are defined in `tests/conftest.py` and available to all test files.

**Key fixtures:**

```python
@pytest.fixture
def synthetic_raster(tmp_path: Path) -> Path:
    """5×5 GeoTIFF raster (EPSG:4326), values 0–24."""
    # Creates .tif at tmp_path/data/synthetic_raster.tif
    ...

@pytest.fixture
def synthetic_climate_csv_dense(tmp_path: Path) -> Path:
    """8-station climate CSV — enough for kriging (≥ MIN_KRIGING_STATIONS=5)."""
    # Creates .csv at tmp_path/data/synthetic_climate_dense.csv
    ...
```

- Fixtures use `tmp_path` (pytest built-in) for isolation
- Synthetic rasters use `rasterio` with `from_origin` transforms
- Climate CSVs use `pandas.DataFrame.to_csv`

## Test Structure Patterns

### Class-based grouping
Tests are grouped into `TestFeatureName` classes for related behaviors:

```python
class TestClimateInterpolatorInit:
    """Test ClimateInterpolator initialization and validation."""

    def test_init_spatial_strategy_valid(self):
        ...

    def test_init_index_strategy_valid(self):
        ...
```

### Function naming
```
test_<behaviour>_<condition>
test_two_runs_same_inputs_identical_scores
test_init_spatial_strategy_valid
test_fingerprint_stable_across_reruns
```

### Docstrings on test functions
Each test has a one-line docstring describing expected behavior — used as living documentation.

## Test Types

### Unit tests
- Test individual functions/classes in isolation
- Modules covered: `test_config.py`, `test_model.py`, `test_stats.py`, `test_utils.py`, `test_run_identity.py`
- Use synthetic data generated in-test or from fixtures

### Integration tests
- Test component interactions through pipeline stages
- `test_climate.py` — ClimateInterpolator + `load_climate_csv` integration
- `test_pipeline.py` — full pipeline with synthetic data
- `test_artifacts.py` — artifact schema contracts across a full run

### End-to-end tests
- `test_e2e_smoke.py` — marked `@pytest.mark.smoke`, uses synthetic raster + CSV
- `smoke_test.py` — real USDA CDL data; conditionally skipped if data absent:

```python
_SKIP_REAL_DATA = pytest.mark.skipif(
    not _RASTER_PATH.exists(),
    reason="USDA CDL raster not present — run 'make get-demo-data' first"
)
```

### Determinism tests
- `test_determinism.py` — `TestSamplingDeterminism` class
- Verifies identical inputs produce identical cell coordinates, scores, and fingerprints
- Runs pipeline twice with same config, asserts numpy equality

### Uncertainty tests
- `test_uncertainty.py` (398 lines) — Monte Carlo uncertainty propagation (Stage 2)
- Tests `suitability_score_array` vectorized correctness
- Verifies MC columns appear in `features.parquet` when `uncertainty_samples > 0`
- Asserts `score_ci_low <= score <= score_ci_high` for every cell
- Tests `uncertainty` block presence in `report.json`
- Tests no MC columns when `uncertainty_samples=0` (default)

### CLI tests
- `test_cli.py` (257 lines) — tests Typer CLI commands via subprocess or Click test runner
- Covers `run`, `validate`, and `info` commands

## Conditional Skipping Pattern

For tests requiring large external data files:

```python
_RASTER_PATH = Path(__file__).resolve().parents[1] / "data" / "usda_cdl.tif"
_SKIP_REAL_DATA = pytest.mark.skipif(
    not _RASTER_PATH.exists(),
    reason="USDA CDL raster not present — run 'make get-demo-data' first; see data/README.md",
)

@_SKIP_REAL_DATA
def test_summarize_raster_file_real_data():
    ...
```

## Coverage

- Branch coverage required (`branch = true`)
- 85% minimum enforced in CI (`fail_under = 85`)
- `show_missing = true` — shows uncovered line numbers in report
- `skip_covered = true` — hides 100%-covered files from report

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=terraflow --cov-report=term-missing

# Only smoke tests
pytest -m smoke

# Specific module
pytest tests/test_climate.py

# Skip slow tests (real data)
pytest --ignore=tests/smoke_test.py
```

## Key Makefile Targets

```makefile
make test          # pytest with coverage
make test-fast     # pytest without coverage
make lint          # Ruff + mypy
```

## Anti-Patterns to Avoid

- Do NOT import from test modules in other test modules — use fixtures in `conftest.py`
- Do NOT hardcode absolute paths — use `tmp_path`, `Path(__file__).parents`, or fixtures
- Do NOT commit large binary test data — use `make get-demo-data` for real data
- Do NOT use `monkeypatch` to skip real I/O unless unavoidable — prefer synthetic data
