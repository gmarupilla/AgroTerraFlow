VENV := $(PWD)/.venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)
	# source $(VENV)/bin/activate
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt

lint:
	$(VENV)/bin/ruff check terraflow tests

format:
	$(VENV)/bin/black terraflow tests

test:
	source $(VENV)/bin/activate; \
	$(VENV)/bin/pytest -v

check: lint test


run-demo: install
	$(PYTHON) -m terraflow.cli --config examples/demo_config.yml

shell: venv
	@echo "To activate your environment, run:"
	@echo "source $(VENV)/bin/activate"

build:
	docker build -t terraflow:latest .

run:
	docker run --rm \
		-v $(PWD):/app \
		terraflow:latest \
		--config examples/demo_config.yml

.PHONY: venv install lint format test check run-demo shell build run
