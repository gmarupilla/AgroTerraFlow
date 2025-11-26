# ==========================
#  Virtual Environment Setup
# ==========================

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

venv: $(VENV)/bin/activate
	@echo "Virtualenv created at $(VENV)"

# ==========================
#  Installation Commands
# ==========================

install: venv
	$(PIP) install -r requirements.txt

dev: venv
	$(PIP) install -r requirements-dev.txt

# ==========================
#  Quality / Test Commands
# ==========================

lint: venv
	$(VENV)/bin/ruff check terraflow tests

format: venv
	$(VENV)/bin/black terraflow tests

test: venv
	$(VENV)/bin/pytest -v tests

check: lint test

# ==========================
#  Run the Demo Pipeline
# ==========================

run-demo: venv
	$(PYTHON) -m terraflow.cli --config examples/demo_config.yml

# ==========================
#  Utility
# ==========================

shell: venv
	@echo "To activate your environment, run:"
	@echo "source $(VENV)/bin/activate"

.PHONY: build run

build:
	docker build -t terraflow:latest .

run:
	docker run --rm \
		-v $(PWD):/app \
		terraflow:latest \
		--config examples/demo_config.yml
