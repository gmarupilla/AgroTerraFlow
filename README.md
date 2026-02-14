# TerraFlow: Reproducible Geospatial Agricultural Modeling

[![CI](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/ci.yml)
[![Deploy Docs](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/docs.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/docs.yml)
[![Publish to PyPI](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/publish-pypi.yml)
[![Build JOSS Manuscript](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/manuscript.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/manuscript.yml)
[![PyPI](https://img.shields.io/pypi/v/terraflow-agro.svg)](https://pypi.org/project/terraflow-agro/)
[![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Quality gate](https://sonarcloud.io/api/project_badges/quality_gate?project=gmarupilla_AgroTerraFlow)](https://sonarcloud.io/summary/new_code?id=gmarupilla_AgroTerraFlow)
[![Codecov](https://codecov.io/gh/gmarupilla/AgroTerraFlow/branch/main/graph/badge.svg)](https://codecov.io/gh/gmarupilla/AgroTerraFlow)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**TerraFlow v0.2.0** is a reproducible, open-source geospatial workflow framework for agricultural modeling.
It provides:

* Geospatial preprocessing (rasters, vectors, ROI clipping)
* Spatially-aware climate data (per-cell spatial interpolation with fallback strategies) - NEW in v0.2.0
* Config-driven model execution with Pydantic v2 validation
* Python package with CLI interface (`terraflow run`)
* Docker workflow support
* JOSS-compatible research workflow and manuscript
* Comprehensive test suite (33+ tests) with 100% pass rate
* Interactive Jupyter notebook for testing and visualization
* Architecture Decision Records (ADRs) for design documentation

Use TerraFlow to build, test, and publish reproducible agricultural analytics pipelines.

## Features

**Core Capabilities:**
* Modern Python package (pyproject.toml, PEP 621 compliant)
* Fully uv-installable (`uv pip install terraflow-agro`)
* Reproducible CLI interface (`terraflow run --config <file>`)
* Pydantic v2 configuration models with geographic coordinate validation - enhanced in v0.2.0
* Spatial interpolation using scipy.interpolate.griddata - new in v0.2.0
* Extensible workflow architecture with clean separation of concerns

**Development & Testing:**
* Comprehensive test suite with pytest (33+ tests across 10 test files)
* Linting with ruff and black
* Makefile automation for dev/test/build/release workflows
* Interactive Jupyter notebook for comprehensive testing
* Example data and demo configurations

**CI/CD & Documentation:**
* GitHub Actions for CI testing and linting
* Automated PyPI publishing on version tags
* MkDocs-based documentation with GitHub Pages deployment
* JOSS manuscript build automation
* Docker support for containerized workflows

**Architecture & Design:**
* Architecture Decision Records (ADRs) documenting key design choices
* Clean module separation (cli, config, climate, geo, ingest, model, pipeline, stats, viz)
* Comprehensive error handling and resource management
* Production-ready code quality

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
uv pip install terraflow-agro
```

Verify installation:

```python
import terraflow
print(terraflow.__version__)
```

### Option 2: Install from source

Clone the repo:

```bash
git clone https://github.com/gmarupilla/AgroTerraFlow.git
cd AgroTerraFlow
```

### Create `.venv` and install dependencies

```bash
make dev
```

This runs:

* `uv venv .venv`
* `uv pip install --python .venv/bin/python -e ".[dev]"`
  (Using only `pyproject.toml` — no requirements.txt)

## Quickstart

### Run the demo pipeline

```
make run-demo
```

which is equivalent to:

```
python -m terraflow.cli --config examples/demo_config.yml
```

## CLI Usage

After installation, TerraFlow exposes a CLI:

```
terraflow run --config config.yml
```

Or explicitly:

```
python -m terraflow.cli --config config.yml
```

Example:

```bash
terraflow run --config examples/demo_config.yml
```

Your results will appear in:

```
outputs/
```

## Run Fingerprint

Each pipeline execution is identified by a deterministic `run_fingerprint` derived from:

- Canonicalized YAML configuration
- ROI geometry hash
- Input file fingerprints (sha256, size, mtime)

Identical inputs always produce the same fingerprint across machines. This enables
immutable run directories like:

```
runs/<fingerprint>/...
```

## Climate Data Integration (v0.2.0)

TerraFlow now supports **per-cell climate data** with two interpolation strategies:

### Spatial Interpolation (Recommended)
For climate data with geographic coordinates (weather stations, satellite grids):

```yaml
climate:
  strategy: spatial          # Interpolate using scipy.griddata
  fallback_to_mean: true     # Use global mean for extrapolated cells
```

**Benefits:**
- Works with arbitrary observation locations
- Smooth spatial gradients across your ROI
- Graceful handling of sparse data

### Index-Based Matching
For pre-aligned climate data (one row per cell):

```yaml
climate:
  strategy: index            # Direct row-to-cell matching
  fallback_to_mean: true     # Use mean for mismatched counts
```

**Climate CSV Format:**
Your climate CSV must have `lat`, `lon`, and climate variables:

```csv
lat,lon,mean_temp,total_rain
34.05,-118.24,22.5,250.0
34.10,-118.19,23.1,260.0
```

See [Climate Configuration](docs/config/schema.md#climate-configuration-v02) and [ADR-003](docs/architecture/adr-003-climate-interpolation.md) for details.

## Documentation

### Local preview

Install the docs dependencies and serve the site:

```bash
uv pip install -r docs/requirements.txt
mkdocs serve
```

### Publishing

Documentation is built and published automatically via GitHub Pages on every push to `main`.

## Development

### Create virtual environment + install dev deps

```bash
make dev
```

### Run tests

```bash
make test
```

### Run the demo workflow

```bash
make run-demo
```

### Linting

```bash
make lint
```

This runs ruff and black for code formatting and style checks.

## Testing

TerraFlow includes a comprehensive test suite with 33+ tests covering all core functionality.

### Run all tests

```bash
make test
```

### Test Coverage

The test suite covers:
- CLI argument parsing and error handling
- Climate data loading and interpolation (spatial and index-based)
- Configuration validation with Pydantic v2
- Geospatial operations (ROI clipping, masking, band selection)
- Data ingestion and preprocessing
- Model execution
- Pipeline integration
- Statistical analysis
- Visualization generation

### Interactive Testing

Use the comprehensive Jupyter notebook for interactive testing and exploration:

```bash
jupyter notebook notebooks/terraflow_v0.2.0_comprehensive_test.ipynb
```

## Docker Usage

### Build image

```bash
make docker-build
```

### Run container

```bash
make docker-run
```

Equivalent to:

```bash
docker run --rm \
    -v $(pwd):/app \
    terraflow:latest \
    --config examples/demo_config.yml
```

## Continuous Integration (GitHub Actions)

### CI Pipeline (ci.yml)

The main CI pipeline runs on every push and pull request to main/master:

* Sets up Python 3.10 and uv package manager
* Creates virtual environment and installs dependencies
* Runs full test suite with pytest
* Runs linting checks with ruff and black

### Documentation Deployment (docs.yml)

Automatically builds and deploys documentation to GitHub Pages on every push to main:

* Builds MkDocs site with strict mode
* Deploys to GitHub Pages

### PyPI Publishing (publish-pypi.yml)

Triggered on version tags (v*.*.*):

* Builds Python wheel and source distribution
* Publishes to PyPI automatically
* No manual intervention required

### JOSS Manuscript (manuscript.yml)

Builds the JOSS paper PDF on version tags or manual trigger:

* Generates publication-ready manuscript
* Uploads as GitHub artifact

## Publishing a Release to PyPI

Publishing is fully automated via GitHub Actions and `publish-pypi.yml`.

### 1. Update version

```bash
make release version=0.1.X
```

This:

* updates `pyproject.toml`
* updates `terraflow/__init__.py`
* commits version bump
* tags release
* pushes tag → triggers PyPI publish

### 2. GitHub Action builds & uploads:

* wheel (`.whl`)
* source distribution (`.tar.gz`)

No manual PyPI login required.

## Configuration (Pydantic v2)

TerraFlow uses Pydantic v2 for typed config:

```python
from pydantic import BaseModel

class WorkflowConfig(BaseModel):
    input_raster: str
    roi_path: str
    climate_source: str
    output_dir: str = "outputs"

    model_config = {
        "extra": "forbid",
        "validate_default": True
    }
```

A typical YAML config:

```yaml
input_raster: "examples/sample_data/soil.tif"
roi_path: "examples/sample_data/roi.geojson"
climate_source: "era5"
output_dir: "outputs"
```

## Architecture

TerraFlow follows clean architecture principles with clear separation of concerns:

### Core Modules

- **cli.py**: Command-line interface with argument parsing and error handling
- **config.py**: Pydantic v2 models for configuration validation
- **climate.py**: Climate data interpolation with spatial and index-based strategies
- **geo.py**: Geospatial operations (raster I/O, ROI clipping, coordinate validation)
- **ingest.py**: Data ingestion and preprocessing
- **model.py**: Core modeling logic
- **pipeline.py**: Workflow orchestration and execution
- **stats.py**: Statistical analysis and aggregation
- **viz.py**: Visualization generation with Plotly
- **utils.py**: Utility functions and helpers

### Architecture Decision Records

Key design decisions are documented in ADRs:

- **ADR-001**: Band selection strategy for multi-band rasters
- **ADR-002**: Bounding box vs polygon ROI support
- **ADR-003**: Climate interpolation strategies (spatial vs index-based)

See `docs/architecture/` for detailed ADRs.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for detailed feature planning.

**Planned enhancements:**
* Multiple crop models support
* Calibration and uncertainty quantification modules
* Enhanced geospatial visualization
* Improved CLI templates and pipeline configurability
* Performance optimization for large-scale rasters
* Additional interpolation methods

## Contributing

Contributions are welcome! See [docs/contributing.md](docs/contributing.md) for guidelines.

## Citation

If you use TerraFlow in your research, please cite our JOSS paper (manuscript in preparation).

## License

MIT License — free for academic, commercial, and open-source use.
