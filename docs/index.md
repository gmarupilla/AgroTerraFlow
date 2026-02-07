# TerraFlow Documentation

TerraFlow is a reproducible geospatial modeling framework for agricultural and environmental analysis.
Start with the [TerraFlow Overview](architecture/overview.md) to understand the core pipeline and contracts.

## v0.2.0 Features

**TerraFlow v0.2.0** is local-first with spatial climate interpolation:

- ROI boundaries defined in YAML (bbox).
- Local GeoTIFF raster inputs (for example, `data/usda_cdl.tif`).
- Local climate CSV inputs with lat/lon coordinates for spatial interpolation (for example, `data/demo_climate.csv`).
- **Per-cell climate values** using configurable strategies (spatial interpolation or index-based matching).

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
