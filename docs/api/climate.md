---
title: Climate API
description: API reference for terraflow.climate — ClimateInterpolator, spatial and index strategies, and per-cell value assignment.
icon: material/weather-partly-cloudy
tags:
  - API
  - Reference
---

# terraflow.climate

The climate module provides spatial interpolation and index-based matching for aligning climate observations to raster cells.

## Overview

Per-cell climate interpolation via configurable spatial algorithms:

- **`"linear"`** (default): `scipy.interpolate.griddata` — fast, no extra dependencies
- **`"kriging"`**: Ordinary Kriging via `pykrige` — geostatistically optimal; also produces per-cell uncertainty (`{var}_krig_std` columns)
- **`"idw"`**: Inverse Distance Weighting (power=2) — faster than kriging, no uncertainty output
- **Index-based matching**: Row order or explicit cell ID matching for pre-aligned data
- **Graceful fallbacks**: Global mean values for cells outside interpolation range or with sparse data

## Quick Example

```python
import pandas as pd
from terraflow.climate import ClimateInterpolator

# Load climate data
climate_df = pd.read_csv("weather_stations.csv")

# Create spatial interpolator with kriging (produces uncertainty columns)
interpolator = ClimateInterpolator(
    climate_df=climate_df,
    strategy="spatial",
    interpolation_method="kriging",
    fallback_to_mean=True
)

# Interpolate values for raster cell locations
import numpy as np
cell_lats = np.array([39.14, 38.55])
cell_lons = np.array([-100.82, -99.20])
interpolated = interpolator.interpolate(cell_lats, cell_lons)
```

!!! example "Use Cases"
    - **Spatial**: Weather station networks, satellite gridded data
    - **Index**: Pre-processed per-cell climate datasets

## API Reference

::: terraflow.climate

