# TerraFlow Documentation

TerraFlow is a reproducible geospatial modeling framework designed for agricultural and environmental analysis.
This site covers the architecture, configuration schema, CLI workflow, and API reference for the v0.1 pipeline.

## What TerraFlow does

- Loads raster and climate inputs from local files.
- Clips data to a region of interest (ROI).
- Computes a simple suitability score and emits tabular outputs.
- Records deterministic run metadata and artifacts for reproducibility.

## Quickstart

1. Create a virtual environment and install the package plus docs dependencies.
2. Preview the documentation locally:

```bash
mkdocs serve
```

3. Build the site with strict validation:

```bash
mkdocs build --strict
```

## Documentation map

- **Architecture** explains boundaries, run identity, and artifact contracts.
- **Config** describes the YAML schema and provides examples.
- **CLI** covers running the pipeline from the command line.
- **API Reference** is generated from the Python sources via `mkdocstrings`.

If you're new to TerraFlow, start with the architecture overview and the configuration schema.
