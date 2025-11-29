# Variables
PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: help venv install dev test run build clean docker-build docker-run release

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

# ---------------------------
# Environment setup
# ---------------------------

venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e .

dev: venv
	$(PIP) install -e ".[dev]"

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
	$(PIP) install --upgrade build
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
