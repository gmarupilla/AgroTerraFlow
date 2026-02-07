# Variables
PYTHON = .venv/bin/python
UV = uv
RUFF = .venv/bin/ruff
BLACK = .venv/bin/black

.PHONY: help venv install dev test run build clean docker-build docker-run lint lint-fix docs-serve docs-build

help:
	@echo "Available commands:"
	@echo "  make venv          - Create a fresh .venv"
	@echo "  make install       - Install terraflow-agro in editable mode into .venv"
	@echo "  make dev           - Install terraflow-agro + dev dependencies"
	@echo "  make test          - Run unit tests"
	@echo "  make run           - Run example workflow"
	@echo "  make build         - Build wheel + sdist"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker image"
	@echo "  make release       - Bump version, tag, and push"
	@echo "  make docs-serve    - Serve MkDocs site locally"
	@echo "  make docs-build    - Build MkDocs site (strict)"

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
	$(RUFF) check terraflow tests
	$(BLACK) --check terraflow tests

lint-fix:
	$(RUFF) check terraflow tests --fix
	$(BLACK) terraflow tests

docs-serve:
	$(PYTHON) -m mkdocs serve

docs-build:
	$(UV) pip install --python $(PYTHON) -r docs/requirements.txt
	$(PYTHON) -m mkdocs build --strict
