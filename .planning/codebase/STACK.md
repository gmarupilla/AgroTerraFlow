# Technology Stack

**Analysis Date:** 2026-03-18

## Languages

**Primary:**
- Python 3.10+ - Entire codebase, CLI, and data processing pipeline

**Secondary:**
- Shell (Bash/zsh) - Build scripts, Makefile, CI/CD workflows
- YAML - Configuration files and GitHub Actions workflows
- Markdown - Documentation (MkDocs)

## Runtime

**Environment:**
- CPython 3.10, 3.11, 3.12 (tested in CI matrix)
- Tested on Linux (Ubuntu 22.04 in CI), macOS, Windows (Docker)

**Package Manager:**
- `uv` (Astral's fast Python package installer)
  - Lockfile: Not used (pyproject.toml-only approach)
- Alternative: `pip` (compatible)

## Frameworks

**Core:**
- setuptools 64+ - Package build and distribution
- build - Python wheel/sdist creation for publishing

**Data Processing:**
- pandas 1.3.0+ - Tabular data handling (climate CSV, feature tables)
- numpy 1.21.0+ - Numerical array operations, masked arrays
- pyarrow 14.0+ - Apache Arrow backend for parquet serialization
- rasterio 1.2.0+ - Geospatial raster I/O (GeoTIFF, COG)
- pykrige 1.7+ - Geostatistical kriging interpolation with variogram fitting
- scipy 1.9.0+ - Scientific computing (griddata for linear interpolation)
- shapely 2.0.0+ - Geometry operations (WKB/WKT, spatial relationships)
- pyproj 3.0+ - Coordinate reference system (CRS) transformations

**Visualization:**
- plotly 5.0.0+ - Interactive web-based charts (optional dev dependency)
- matplotlib 3.7+ - Static plotting (dev dependency)
- seaborn 0.13+ - Statistical visualization (dev dependency)

**Configuration & Validation:**
- pydantic 2.0+ - Data validation via schema models (PipelineConfig, ModelParams, etc.)
- pyyaml 5.4.0+ - YAML file parsing for pipeline config

**Testing:**
- pytest 7.0+ - Test runner and fixtures
- pytest-cov 3.0+ - Code coverage tracking

**Code Quality:**
- mypy 1.10+ - Static type checking
- ruff - Fast Python linter (import sorting, code quality)
- black 24.4.2+ - Code formatter (opinionated)
- pre-commit 3.7+ - Git hooks for automated checks before commits

**Documentation:**
- mkdocs 1.5+ - Static site generator
- mkdocs-material 9+ - Material theme for MkDocs
- mkdocstrings[python] 0.24+ - Auto-generate API docs from docstrings
- mkdocs-gen-files 0.5+ - Generate docs files programmatically
- mkdocs-literate-nav 0.6+ - Custom navigation for docs
- mkdocs-section-index 0.3+ - Section-level index pages
- mkdocs-mermaid2-plugin 1.1.1+ - Mermaid diagram support
- pymdown-extensions 10+ - Additional Markdown extensions
- mkdocs-jupyter 0.24+ - Jupyter notebook support in docs

**Notebook/Interactive:**
- marimo 0.19+ - Reactive notebook environment (dev dependency)

**Utilities:**
- pip-licenses 4.3+ - License report generation
- types-PyYAML 6.0+ - Type stubs for PyYAML

## Key Dependencies

**Critical (Core Functionality):**
- `rasterio` - Enables reading GeoTIFF raster data (DEM, NDVI, etc.)
- `pandas` + `pyarrow` - Enables tabular climate data processing and parquet output
- `pydantic` - Config validation and type safety throughout pipeline
- `numpy` - Core numerical operations for raster manipulation
- `shapely` - Geometry operations for ROI clipping and spatial tests

**Scientific (Feature Computation):**
- `scipy.interpolate.griddata` - Default linear interpolation for climate
- `pykrige` - Kriging interpolation with uncertainty quantification (optional method)
- `pyproj` - CRS transformations (necessary for geographic accuracy)

**Quality Assurance:**
- `pytest` + `pytest-cov` - Test coverage enforcement (85% minimum)
- `mypy` - Type checking for Python 3.10+ code
- `ruff` - Fast linting with import sorting
- `black` - Formatting consistency

## Configuration

**Environment:**
- Configuration via YAML files (user-supplied, see `examples/demo_config.yml`)
- No `.env` files required — all config is explicit YAML or CLI args
- No secrets management framework (project assumption: no API keys or credentials)

**Build:**
- `pyproject.toml` - Single source of truth for dependencies, build metadata, tool config
- Tool configurations in `pyproject.toml`: mypy, ruff, pytest, coverage
- Pre-commit hooks in `.pre-commit-config.yaml` (ruff, black, yaml validation)

**Tool Configurations:**
- Ruff: Line length 120, linting rules E/F/W/I (ignores E501 line length in content)
- Black: Line length 120 (via Ruff), operated through pre-commit
- MyPy: Python 3.10, strict null checks, ignore missing imports for untyped packages
- Pytest: Markers defined (e.g., `smoke` for end-to-end tests)
- Coverage: 85% fail-under threshold, branch coverage enabled

## Platform Requirements

**Development:**
- Python 3.10+ interpreter
- Make (for Makefile commands)
- `curl` (for uv installer in Docker/CI)
- GDAL/GDAL development libraries (required by rasterio for georeferencing)
  - Ubuntu: `gdal-bin libgdal-dev`
  - macOS: typically available via homebrew/conda

**Production/Deployment:**
- Docker image based on `python:3.11-slim` with GDAL libs
- Deployment target: Any platform with Python 3.10+ and GDAL support
- CI: GitHub Actions (Ubuntu latest) with matrix testing on 3.10/3.11/3.12

---

*Stack analysis: 2026-03-18*
