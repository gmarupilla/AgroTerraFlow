# TerraFlow
[![CI](https://github.com/gmarupilla/terraflow/actions/workflows/ci.yml/badge.svg)](https://github.com/gmarupilla/terraflow/actions/workflows/ci.yml)


TerraFlow is an open-source, reproducible workflow for geospatial agricultural modeling and simulation.

It demonstrates how to:

- Load raster and climate data
- Run a simple suitability model
- Produce reproducible outputs (CSV, maps)
- Configure runs via YAML

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
make dev
```

## Run with Docker

You can also run TerraFlow inside a container.

Build the image:

```bash
make build
make run
```
