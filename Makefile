# Variables
PYTHON = .venv/bin/python
UV = uv
RUFF = .venv/bin/ruff
BLACK = .venv/bin/black
PRE_COMMIT = .venv/bin/pre-commit
MYPY = .venv/bin/mypy
PIP_LICENSES = .venv/bin/pip-licenses

.PHONY: help venv install dev test test-cov smoke-test typecheck license-check run build clean docker-build docker-run lint lint-fix pre-commit docs-serve docs-build paper get-demo-data

help:
	@echo "Available commands:"
	@echo "  make venv          - Create a fresh .venv"
	@echo "  make install       - Install terraflow-agro in editable mode into .venv"
	@echo "  make dev           - Install terraflow-agro + dev dependencies"
	@echo "  make test          - Run unit tests"
	@echo "  make test-cov      - Run tests with coverage"
	@echo "  make smoke-test    - Run end-to-end smoke tests (synthetic data)"
	@echo "  make typecheck     - Run mypy type checks"
	@echo "  make license-check - Report dependency licenses"
	@echo "  make run           - Run example workflow"
	@echo "  make build         - Build wheel + sdist"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker image"
	@echo "  make release       - Bump version, tag, and push"
	@echo "  make pre-commit    - Install git pre-commit hooks"
	@echo "  make docs-serve    - Serve MkDocs site locally"
	@echo "  make docs-build    - Build MkDocs site (strict)"
	@echo "  make paper         - Compile JOSS paper PDF via Docker (openjournals/inara)"
	@echo "  make get-demo-data - Download USDA CDL demo raster from CropScape (public domain)"

# ---------------------------
# Environment setup
# ---------------------------

venv:
	$(UV) venv --clear .venv

install: venv
	$(UV) pip install --python $(PYTHON) -e .

dev: venv
	$(UV) pip install --python $(PYTHON) -e ".[dev]"

# ---------------------------
# Testing & Running
# ---------------------------

test:
	$(PYTHON) -m pytest -v

test-cov:
	$(PYTHON) -m pytest -v --cov --cov-report=term-missing --cov-report=xml

smoke-test:
	$(PYTHON) -m pytest tests/test_e2e_smoke.py -v -m smoke

typecheck:
	$(MYPY) --config-file pyproject.toml

license-check:
	$(PIP_LICENSES) --format=markdown --output-file=license-report.md --with-urls

run-demo:
	$(PYTHON) -m terraflow.cli --config examples/demo_config.yml

# ---------------------------
# Build & Release
# ---------------------------

build:
	$(UV) pip install --python $(PYTHON) --upgrade build
	$(PYTHON) -m build

clean:
	rm -rf build dist *.egg-info
	rm -rf .venv
	find . -name "__pycache__" -exec rm -rf {} +

# Docker
docker-build:
	docker build -t terraflow:latest .

docker-run:
	docker run --rm \
		-v $(PWD):/app \
		terraflow:latest \
		--config examples/demo_config.yml

lint:
	$(RUFF) check terraflow tests --fix
	$(BLACK) terraflow tests
	$(RUFF) check terraflow tests
	$(BLACK) --check terraflow tests

lint-fix:
	$(RUFF) check terraflow tests --fix
	$(BLACK) terraflow tests

pre-commit:
	$(PRE_COMMIT) install

docs-serve:
	$(PYTHON) -m mkdocs serve

docs-build:
	$(UV) pip install --python $(PYTHON) -r docs/requirements.txt
	$(PYTHON) -m mkdocs build --strict


get-demo-data:
	@echo "Generating synthetic demo raster (western Kansas extent, CDL-compatible)..."
	$(PYTHON) scripts/make_demo_raster.py
	@echo "Saved to data/usda_cdl.tif"
	@echo ""
	@echo "For real USDA CDL data see data/README.md (USDA NASS CropScape)."

paper:
	docker run --rm \
		--volume $(PWD)/paper:/data \
		--user $(shell id -u):$(shell id -g) \
		--env JOURNAL=joss \
		openjournals/inara
