---
title: "ADR-001: Single-Band Raster Processing"
description: Decision record for processing only Band 1 from input rasters — rationale, consequences, and future alternatives.
icon: material/numeric-1-box-outline
tags:
  - Architecture
  - ADR
---

# ADR-001: Single-Band Raster Processing

**Date**: 2026-02-06  
**Status**: Accepted  
**Context**: Handling multi-band GeoTIFF rasters

## Problem

Agricultural rasters often come in multiple formats:
- Single-band vegetation indices (NDVI, EVI)
- Multi-band sensor data (Landsat, Sentinel)
- Composite rasters with specific band organization

TerraFlow needs to handle raster inputs consistently while keeping the implementation simple.

## Decision

TerraFlow currently processes only **Band 1** from any input raster. This is enforced in:
- `terraflow.geo.clip_raster_to_roi()` - validates `raster.count >= 1`
- `terraflow.pipeline.run_pipeline()` - passes band 1 data to model

## Rationale

1. **Simplicity**: Single-band processing avoids complexity of band selection/ordering logic
2. **Common case**: Most agricultural indices are pre-computed single-band products (NDVI, soil moisture)
3. **User control**: Users can pre-process multi-band rasters to extract their desired band before running TerraFlow
4. **Clear error messages**: Band validation happens early with helpful error messages

## Consequences

### Positive
- Straightforward implementation
- Users know exactly what band will be used
- Easy to test and debug

### Negative
- Cannot directly process multi-band rasters without pre-processing
- No automatic band selection for common indices
- Limits direct integration with tools like Landsat/Sentinel data

## Future Alternatives

1. **Band auto-detection**: Select NDVI band if available (metadata-based)
2. **Multi-band support**: Process multiple bands and compute composite suitability
3. **User-configurable selection**: Add `band_number` parameter to config

## References

- Band validation in geo.py (see terraflow/geo.py)
- Usage in pipeline.py (see terraflow/pipeline.py)
- [Config schema](../config/schema.md)
