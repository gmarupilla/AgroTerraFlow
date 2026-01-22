# **TerraFlow: Reproducible Geospatial Agricultural Modeling**

[![PyPI](https://img.shields.io/pypi/v/terraflow-agro.svg)](https://pypi.org/project/terraflow-agro/)
[![CI](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**TerraFlow** is a reproducible, open-source geospatial workflow framework for agricultural modeling.
It provides:

* 🌾 **Geospatial preprocessing** (rasters, vectors, ROI clipping)
* 🌦 **Climate data integration**
* 📦 **Config-driven model execution**
* 🐍 **Python package + CLI (`terraflow run`)**
* 🐳 **Docker workflow support**
* 📄 **JOSS-compatible research workflow**

Use TerraFlow to build, test, and publish reproducible agricultural analytics pipelines.

---

## 🚀 Features

* Modern Python package (`pyproject.toml`, PEP 621)
* Fully uv-installable (`uv pip install terraflow-agro`)
* Reproducible CLI interface (`terraflow run --config <file>`)
* Pydantic v2 configuration models
* Extensible workflow architecture
* Example data + demo config
* Makefile automation for dev/test/build/release
* GitHub Actions for CI + PyPI publishing on tags

---

# 📦 Installation

## **Option 1: Install from PyPI (Recommended)**

```bash
uv pip install terraflow-agro
```

Verify installation:

```python
import terraflow
print(terraflow.__version__)
```

---

## **Option 2: Install from source**

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

---

# 🧰 Project Structure

```
AgroTerraFlow/
│
├── terraflow/              # Core Python package
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Pydantic v2 config models
│   └── workflow.py         # Core workflow logic
│
├── examples/
│   ├── demo_config.yml     # Example config file
│   └── sample_data/        # Optional small data files
│
├── outputs/                # Generated outputs
├── Dockerfile
├── Makefile
├── README.md
└── pyproject.toml
```

---

# 🏃‍♂️ Quickstart

### Run the demo pipeline

```
make run-demo
```

which is equivalent to:

```
python -m terraflow.cli --config examples/demo_config.yml
```

---

# 🖥 CLI Usage

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

---

# 📚 Documentation

### Local preview

Install the docs dependencies and serve the site:

```bash
uv pip install -r docs/requirements.txt
mkdocs serve
```

### Publishing

Documentation is built and published automatically via GitHub Pages on every push to `main`.

---

# ⚙️ Development

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

---

# 🐳 Docker Usage

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

---

# 🧪 Continuous Integration (GitHub Actions)

The CI pipeline (`.github/workflows/ci.yml`) performs:

* `make venv`
* `make dev`
* `make test`
* `make run-demo` (smoke test)

Triggered on:

* pushes to `main`/`master`
* pull requests targeting those branches

---

# 📤 Publishing a Release to PyPI

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

---

# 🧩 Configuration (Pydantic v2)

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

---

# 📈 Roadmap

* 🔜 Add multiple crop models
* 🔜 Add calibration & uncertainty modules
* 🔜 Add geospatial visualization (`GeoVizFlow` integration)
* 🔜 Improve CLIs & pipeline templates

---

# 📄 License

MIT License — free for academic, commercial, and open-source use.
