---
title: Climate Impact API
description: API reference for terraflow.climate_impact — scenario × hazard orchestrator producing climate_features.parquet.
icon: material/chart-timeline-variant
tags:
  - API
  - Reference
---

# terraflow.climate_impact

Climate-impact pipeline orchestrator introduced in v0.5.0 (#138e). Glues
`terraflow.temporal.compute_per_station_aggregations` to
`terraflow.climate.ClimateInterpolator` and writes the sibling
`climate_features.parquet` artifact alongside the historical
`features.parquet`.

The orchestrator is auto-invoked by `terraflow.pipeline.run_pipeline`
when the loaded config declares both `climate.temporal_aggregations`
and `climate.scenarios` (since v0.5.0; #138f). It is also exposed as a
public function for callers that want to drive the climate-impact path
without going through the full pipeline.

## Overview

- `load_timeseries_csv(path)` — parse and validate the long-format
  station daily CSV. Required columns: `station_id, lat, lon, date,
  temperature_c, precipitation_mm`.
- `run_climate_impact_features(cfg, run_dir, cells_df)` — orchestrate
  the full path: compute per-station aggregations, kriging-interpolate
  each `<rule>__<scenario>` column to cell centroids, write the
  artifact. Returns the absolute path to `climate_features.parquet`.

## Artifact contract

| Column | Type | Meaning |
|---|---|---|
| `cell_id` | int | Stable within a run; matches `features.parquet.cell_id` |
| `<rule_label>__<scenario_name>` | float | One column per `TemporalAggregation × Scenario` pair |

Merge with `features.parquet` on `cell_id` for a complete cell-level
panel.

## Quick example

```python
import pandas as pd
from terraflow.pipeline import run_pipeline

df = run_pipeline("examples/demo_config_climate_impact.yml")
run_dir = df.attrs["run_dir"]

features = pd.read_parquet(f"{run_dir}/features.parquet")
climate  = pd.read_parquet(f"{run_dir}/climate_features.parquet")
panel    = features.merge(climate, on="cell_id")

# panel now has historical suitability + every <rule>__<scenario> column.
```

## API Reference

::: terraflow.climate_impact
