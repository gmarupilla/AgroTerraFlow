# TerraFlow Development Guide

This guide helps you set up a development environment, understand the codebase, and contribute to TerraFlow.

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/gmarupilla/AgroTerraFlow.git
cd TerraFlow

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=terraflow --cov-report=html

# Run specific test file
pytest tests/test_cli.py -v

# Run single test
pytest tests/test_cli.py::test_cli_help_message -v
```

### 3. Code Quality

```bash
# Format code
black terraflow/ tests/

# Lint with ruff
ruff check terraflow/ tests/

# Type checking (with Pylance in VS Code)
```

---

## Project Structure

```
TerraFlow/
├── terraflow/                 # Main package
│   ├── __init__.py           # Package metadata, version
│   ├── cli.py                # Command-line interface
│   ├── config.py             # Configuration validation (Pydantic)
│   ├── geo.py                # Geospatial operations (rasterio)
│   ├── ingest.py             # Data loading (raster, CSV)
│   ├── model.py              # Suitability scoring
│   ├── pipeline.py           # Main workflow orchestration
│   ├── stats.py              # Statistical summaries
│   ├── utils.py              # Utility functions
│   └── viz.py                # Visualization (Plotly)
│
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── test_cli.py           # CLI tests
│   ├── test_config.py        # Config validation tests
│   ├── test_geo.py           # Geo module tests
│   ├── test_ingest.py        # Ingest tests
│   ├── test_model.py         # Model tests
│   ├── test_pipeline.py      # Pipeline integration tests
│   ├── test_stats.py         # Stats tests
│   ├── test_viz.py           # Visualization tests
│   └── smoke_test.py         # Integration smoke test
│
├── docs/                      # Documentation
│   ├── architecture/          # Architecture docs & ADRs
│   ├── api/                   # API documentation
│   ├── cli/                   # CLI documentation
│   └── config/                # Configuration examples
│
├── examples/                  # Example configs
├── data/                      # Sample data
├── pyproject.toml             # Project config (PEP 621)
├── Makefile                   # Build commands
├── Dockerfile                 # Container image
└── README.md                  # Project overview
```

---

## Key Concepts

### 1. Configuration (Pydantic)

TerraFlow uses Pydantic v2 for type-safe configuration:

```python
from terraflow.config import load_config

cfg = load_config("config.yml")
# cfg is PipelineConfig with validated fields:
# - cfg.raster_path: Path
# - cfg.climate_csv: Path
# - cfg.roi: ROI (bbox with xmin, ymin, xmax, ymax)
# - cfg.model_params: ModelParams (v_min/max, t_min/max, r_min/max, weights)
# - cfg.max_cells: int
```

Add validation by defining `validate_*` methods in Pydantic models (see `config.py`).

### 2. Geospatial Operations (Rasterio)

TerraFlow uses rasterio for efficient raster I/O:

```python
from terraflow.geo import clip_raster_to_roi

with rasterio.open("dem.tif") as src:
    clipped_data, transform = clip_raster_to_roi(src, roi)
    # clipped_data: np.ma.MaskedArray (masked values = invalid cells)
    # transform: Affine (for converting row/col to lat/lon)
```

**Important**: Always close rasterio datasets to avoid resource leaks:
```python
src.close()  # or use context manager: with rasterio.open(...) as src:
```

### 3. Workflow Pipeline

The main pipeline (`pipeline.py`) orchestrates:

1. **Load config**: YAML → validated PipelineConfig
2. **Load data**: Raster + climate CSV
3. **Clip raster**: Apply ROI bounds
4. **Aggregate climate**: Compute mean/statistics
5. **Sample cells**: Random selection from valid cells
6. **Score cells**: Apply suitability model
7. **Save results**: Write CSV with cell_id, lat, lon, score, label

### 4. Error Handling

Use specific exceptions:

```python
# ❌ Bad: masks real errors
try:
    data = raster.read(1)
except Exception:
    print("failed")

# ✅ Good: specific exceptions, helpful messages
try:
    data = raster.read(1)
except rasterio.errors.RasterioIOError as e:
    raise ValueError(f"Failed to read raster band 1: {e}") from e
```

Document expected exceptions in docstrings:

```python
def load_raster(path: str | Path) -> DatasetReader:
    """
    ...
    Raises
    ------
    FileNotFoundError:
        If the file does not exist.
    rasterio.errors.RasterioIOError:
        If the file cannot be opened as a raster.
    """
```

---

## Adding Features

### Step 1: Write Tests First (TDD)

```python
# tests/test_new_feature.py
import pytest

def test_new_feature_happy_path():
    """Test the main use case."""
    result = new_feature(input_data)
    assert result == expected_output

def test_new_feature_error_handling():
    """Test error cases."""
    with pytest.raises(ValueError):
        new_feature(invalid_input)
```

Run test to verify it fails:
```bash
pytest tests/test_new_feature.py -v
```

### Step 2: Implement Feature

```python
# terraflow/new_module.py

def new_feature(data: InputType) -> OutputType:
    """
    Descriptive summary.
    
    Parameters
    ----------
    data:
        Input description.
    
    Returns
    -------
    OutputType:
        Output description.
    
    Raises
    ------
    ValueError:
        If conditions invalid.
    """
    # Implementation
    return result
```

### Step 3: Verify Tests Pass

```bash
pytest tests/test_new_feature.py -v
```

### Step 4: Add Documentation

- Add docstring examples
- Update [ROADMAP.md](ROADMAP.md) if feature is user-facing
- Create Architecture Decision Record if architectural change
- Update README.md in root if public API change

### Step 5: Commit and Submit PR

```bash
git add terraflow/ tests/ docs/
git commit -m "feat: add new feature description"
git push origin feature-branch
```

---

## Common Tasks

### Add Validation to Pydantic Model

```python
# config.py
from pydantic import field_validator

class MyModel(BaseModel):
    param: float
    
    @field_validator("param")
    @classmethod
    def validate_param(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"param must be positive, got {v}")
        return v
```

### Add a CLI Argument

```python
# cli.py
parser.add_argument(
    "--output-format",
    choices=["csv", "geojson", "parquet"],
    default="csv",
    help="Output format for results"
)
```

### Test with Temporary Files

```python
# tests/test_example.py
import tempfile
from pathlib import Path

def test_with_temp_file(tmp_path: Path):
    """tmp_path is pytest fixture for temporary directory."""
    output_file = tmp_path / "output.csv"
    result = process_file(output_file)
    assert output_file.exists()
    assert result.shape[0] > 0
```

### Add Optional Dependency

```python
# pyproject.toml
[project.optional-dependencies]
cloud = [
    "s3fs>=2022.1.0",
    "gcsfs>=2022.1.0"
]

# Installation
pip install terraflow[cloud]
```

---

## Testing Best Practices

### 1. Test Organization

```python
# Good: Class-based grouping
class TestClipRasterToROI:
    def test_valid_roi(self): ...
    def test_invalid_bounds(self): ...
    def test_non_intersecting_roi(self): ...

# Good: Descriptive names
def test_cli_config_file_not_found_shows_helpful_error(): ...

# Bad: Vague names
def test_error(): ...
```

### 2. Fixtures

```python
# conftest.py - shared fixtures
@pytest.fixture
def synthetic_raster(tmp_path):
    """Create test raster."""
    # Return path to test raster
    return raster_path

# test_*.py - use fixture
def test_processing(synthetic_raster):
    with rasterio.open(synthetic_raster) as src:
        assert src.count >= 1
```

### 3. Parametrized Tests

```python
@pytest.mark.parametrize("param,expected", [
    (0.0, "low"),
    (0.5, "medium"),
    (1.0, "high"),
])
def test_suitability_labels(param, expected):
    assert suitability_label(param) == expected
```

---

## Code Style

- **Black**: Format with `black terraflow/`
- **Type hints**: Use for all function parameters and returns
- **Docstrings**: NumPy style (parameters, returns, raises, examples)
- **Comments**: Explain *why*, not *what* (code shows what)

```python
# ❌ Bad: Why is unclear
x = y / (y_max - y_min)  # normalize

# ✅ Good: Why is clear, what is obvious from code
# Normalize to [0,1] range; needed for weighted combination in suitability scoring
normalized_value = (value - min_val) / (max_val - min_val)
```

---

## Debugging Tips

### 1. Print Debugging

```python
from terraflow.utils import logger

logger.info(f"Processing {n_cells} cells")
logger.warning(f"ROI bounds outside raster: {roi}")
logger.error(f"Failed to read band {band}: {e}")
```

### 2. Breakpoints with Pytest

```bash
# Drop into debugger on failure
pytest tests/test_file.py -v -s --pdb

# Or add breakpoint in code
import pdb; pdb.set_trace()
```

### 3. Test with Real Data

```bash
# Use demo data
python -c "from terraflow import run_pipeline; run_pipeline('examples/demo_config.yml')"

# Check outputs
head outputs/demo_run/results.csv
```

---

## Performance Profiling

### Profile a Run

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

run_pipeline("config.yml")

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumtime")
stats.print_stats(20)  # Top 20 functions
```

### Memory Usage

```python
# In test or script
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

---

## Release Checklist

Before v1.0 release:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Code formatted: `black terraflow/ tests/`
- [ ] No lint errors: `ruff check terraflow/ tests/`
- [ ] Coverage > 85%: `pytest --cov=terraflow tests/`
- [ ] Update version in `__init__.py` and `pyproject.toml`
- [ ] Update CHANGELOG.md in root
- [ ] Create git tag: `git tag v1.0.0`
- [ ] Push and create release on GitHub

---

## Getting Help

- **GitHub Issues**: Report bugs and ask questions
- **Discussions**: Feature ideas and design discussions
- **Documentation**: See guides for [Architecture](architecture/overview.md), [Configuration](config/schema.md), and [API](api/core.md)
- **Architecture**: See [ADR-001](architecture/adr-001-band-selection.md) and [ADR-002](architecture/adr-002-bbox-roi.md) for design decisions

---

## Contributing Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Write tests first (TDD)
4. Implement feature with clear commits
5. Ensure all tests pass
6. Submit pull request with description
7. Respond to code review feedback

We value:
- ✅ Clear code and comments
- ✅ Comprehensive tests
- ✅ Complete documentation
- ✅ Thoughtful error messages
- ❌ Incomplete features
- ❌ Untested code
- ❌ Cryptic error messages

---

Happy coding! 🌍🌱
