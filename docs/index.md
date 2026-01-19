# TerraFlow Documentation

TerraFlow is a reproducible geospatial modeling framework for agricultural and environmental analysis.
Start with the [TerraFlow Overview](architecture/overview.md) to understand the core pipeline and contracts.

## v0.1 scope

TerraFlow v0.1 is local-first and assumes:

- ROI boundaries defined in YAML (bbox in v0.1 examples).
- Local GeoTIFF raster inputs (for example, `data/usda_cdl.tif`).
- Local climate CSV inputs (for example, `data/demo_climate.csv`).

## Quickstart

```bash
mkdocs serve
```

```bash
mkdocs build --strict
```

## Documentation map

- **Architecture** covers TerraFlow overview, boundaries, run identity, and artifact contracts.
- **Config** describes the YAML schema and provides examples.
- **CLI** explains how to run TerraFlow.
- **API Reference** documents the core modules.
