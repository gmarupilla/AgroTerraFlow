# Variables
PYTHON = .venv/bin/python
UV = uv
RUFF = .venv/bin/ruff
BLACK = .venv/bin/black
PRE_COMMIT = .venv/bin/pre-commit
MYPY = .venv/bin/mypy
PIP_LICENSES = .venv/bin/pip-licenses

.PHONY: help venv install dev test test-cov smoke-test typecheck license-check run build clean docker-build docker-run docker-smoke lint lint-fix pre-commit docs-serve docs-build paper get-demo-data get-drought-data drought-eval

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
	@echo "  make docker-smoke  - Build image and run demo pipeline with --network none to verify offline reproducibility"
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
	$(UV) pip install --python $(PYTHON) -e ".[dev,cmip6]"

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

get-drought-data:
	@echo "Downloading RMA Cause of Loss (public) 2000-2023 into data/drought/rma ..."
	$(PYTHON) -m terraflow.cli drought fetch --rma-dir data/drought/rma --sob-dir data/drought/sob --year-min 2000 --year-max 2023

drought-eval:
	$(PYTHON) -m terraflow.cli drought build -c examples/drought_v0_corn_6state.yml
	$(PYTHON) -m terraflow.cli drought evaluate -c examples/drought_v0_corn_6state.yml

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

# Offline smoke test — runs the demo pipeline entirely without network and
# asserts that all three JOSS-required artifacts (features.parquet,
# manifest.json, report.json) appear under the mounted output dir.
# Uses --network none to guarantee the run cannot reach external services;
# every input (synthetic raster, climate CSV, wheel) is baked into the
# image at build time.  See issue #67.
docker-smoke:
	docker build -t terraflow:latest .
	@set -e; \
	out=$$(mktemp -d 2>/dev/null || mktemp -d -t terraflow-smoke); \
	cleanup() { docker run --rm -v "$$out":/cleanup alpine:3 sh -c 'rm -rf /cleanup/*' 2>/dev/null || true; rmdir "$$out" 2>/dev/null || true; }; \
	trap cleanup EXIT; \
	echo "Running demo pipeline in docker with --network none..."; \
	docker run --rm --network none \
		-v "$$out":/app/outputs \
		terraflow:latest \
		run --config examples/demo_config.yml; \
	fp_dir=$$(ls -d "$$out"/demo_run/runs/*/ 2>/dev/null | head -n1); \
	if [ -z "$$fp_dir" ]; then \
		echo "docker-smoke FAILED: no run directory under $$out/demo_run/runs/"; \
		exit 1; \
	fi; \
	for artifact in features.parquet manifest.json report.json; do \
		if [ ! -f "$$fp_dir/$$artifact" ]; then \
			echo "docker-smoke FAILED: missing $$fp_dir/$$artifact"; \
			exit 1; \
		fi; \
	done; \
	echo "docker-smoke OK: offline run produced all 3 artifacts in $$fp_dir"

# Hermetic climate-impact end-to-end (#138f): exercises the new
# timeseries_csv + temporal_aggregations + scenarios path with
# --network none.  Validates that climate_features.parquet lands in the
# run directory and contains scenario × rule columns.
docker-smoke-climate-impact:
	docker build -t terraflow:latest .
	@set -e; \
	out=$$(mktemp -d 2>/dev/null || mktemp -d -t terraflow-ci-smoke); \
	cleanup() { docker run --rm -v "$$out":/cleanup alpine:3 sh -c 'rm -rf /cleanup/*' 2>/dev/null || true; rmdir "$$out" 2>/dev/null || true; }; \
	trap cleanup EXIT; \
	echo "Running climate-impact pipeline in docker with --network none..."; \
	docker run --rm --network none \
		-v "$$out":/app/outputs \
		terraflow:latest \
		run --config examples/demo_config_climate_impact.yml; \
	fp_dir=$$(ls -d "$$out"/climate_impact_demo/runs/*/ 2>/dev/null | head -n1); \
	if [ -z "$$fp_dir" ]; then \
		echo "docker-smoke-climate-impact FAILED: no run directory under $$out/climate_impact_demo/runs/"; \
		exit 1; \
	fi; \
	for artifact in features.parquet climate_features.parquet manifest.json report.json; do \
		if [ ! -f "$$fp_dir/$$artifact" ]; then \
			echo "docker-smoke-climate-impact FAILED: missing $$fp_dir/$$artifact"; \
			exit 1; \
		fi; \
	done; \
	echo "docker-smoke-climate-impact OK: offline run produced features + climate_features in $$fp_dir"

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
	@echo "Generating synthetic station time-series (1991-2020 + 2041-2070, 9 stations)..."
	$(PYTHON) scripts/make_demo_timeseries.py
	@echo ""
	@echo "For real USDA CDL data see data/README.md (USDA NASS CropScape)."

paper:
	docker run --rm \
		--volume $(PWD)/paper:/data \
		--user $(shell id -u):$(shell id -g) \
		--env JOURNAL=joss \
		openjournals/inara
