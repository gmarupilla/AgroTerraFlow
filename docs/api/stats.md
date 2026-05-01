---
title: Stats API
description: API reference for terraflow.stats — Pydantic summary models and raster/climate stat helpers.
icon: material/chart-bar
tags:
  - API
  - Reference
---

# terraflow.stats

The stats module exposes the Pydantic summary models that back `report.json` plus helper functions for raster and climate statistics.

## Public surface

- `RasterSummary`, `ClimateSummary`, `RunReport` — Pydantic v2 models.
- `summarize_raster`, `summarize_raster_file`, `compare_rasters`, `batch_summarize` — helper functions.

## API Reference

::: terraflow.stats
