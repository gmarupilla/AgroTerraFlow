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

**New in v0.2.0**: Replaces global mean climate approach with per-cell interpolation using:

- **Spatial interpolation**: `scipy.interpolate.griddata` with linear and nearest-neighbor methods
- **Index-based matching**: Row order or explicit cell ID matching
- **Graceful fallbacks**: Global mean values for cells outside interpolation range or with sparse data

## Quick Example

```python
import pandas as pd
from terraflow.climate import ClimateInterpolator

# Load climate data
climate_df = pd.read_csv("weather_stations.csv")

# Create spatial interpolator
interpolator = ClimateInterpolator(
    climate_data=climate_df,
    strategy="spatial",
    fallback_to_mean=True
)

# Interpolate values for raster cell locations
cell_coords = [(39.14, -100.82), (38.55, -99.20)]
interpolated = interpolator.interpolate(cell_coords)
```

!!! example "Use Cases"
    - **Spatial**: Weather station networks, satellite gridded data
    - **Index**: Pre-processed per-cell climate datasets

## API Reference

::: terraflow.climate

