---
title: Ingest API
description: API reference for terraflow.ingest — raster and climate CSV loading, file validation, and IO helpers.
icon: material/database-import
tags:
  - API
  - Reference
---

# terraflow.ingest

The ingest module contains IO helpers for loading raster and climate inputs.

## Quick Example

```python
import rasterio
from terraflow.ingest import load_climate_csv
from terraflow.geo import clip_raster_to_roi

# Load climate data with validation
climate_df = load_climate_csv("weather_stations.csv")
print(f"Loaded {len(climate_df)} weather stations")

# Load and clip raster to region of interest
with rasterio.open("land_cover.tif") as src:
    clipped_data = clip_raster_to_roi(
        src,
        bbox=(-101.0, 38.0, -94.0, 40.0),
        roi_crs="EPSG:4326"
    )
```

!!! note "Validation"
    All ingest functions perform automatic validation:
    
    - Climate CSVs must have `lat`, `lon` columns
    - Coordinate ranges are checked (lat: [-90, 90], lon: [-180, 180])
    - Missing values and duplicates trigger warnings

## API Reference

::: terraflow.ingest
