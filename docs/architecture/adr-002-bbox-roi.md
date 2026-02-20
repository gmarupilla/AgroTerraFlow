---
title: "ADR-002: Bounding Box Only ROI Support"
description: Decision record for restricting ROI to bounding boxes — performance rationale, consequences, and polygon roadmap.
icon: material/numeric-2-box-outline
tags:
  - Architecture
  - ADR
---

# ADR-002: Bounding Box Only ROI Support

**Date**: 2026-02-06  
**Status**: Accepted  
**Context**: Specifying regions of interest for analysis

## Problem

Users need to constrain analysis to specific geographic regions. Different ROI types have different complexity levels:
- **Bounding box (bbox)**: Simple, fast, aligns with raster tiles
- **Polygon**: Flexible, requires rasterization, more computation
- **Points/buffers**: Useful for site-specific analysis, but adds complexity

TerraFlow needs to balance flexibility with implementation simplicity.

## Decision

TerraFlow currently supports only **bounding box (bbox)** ROI type. This is enforced in:
- `terraflow.config.ROI` - Literal["bbox"] type constraint
- `terraflow.geo.clip_raster_to_roi()` - uses `rasterio.windows.from_bounds()`

## Rationale

1. **Performance**: Bbox clipping is a native rasterio operation (O(1) window reads)
2. **Alignment**: Rasters are already grid-based; bounding boxes are natural
3. **Simplicity**: No dependency on geopandas or shapely for polygon operations
4. **Correctness**: Avoids rasterization artifacts and precision issues
5. **Cloud-native**: Works well with cloud-optimized GeoTIFF (COG) read patterns

## Consequences

### Positive
- Fast region selection
- Simple configuration (4 parameters: xmin, ymin, xmax, ymax)
- No additional dependencies needed
- Works well with cloud-hosted rasters (S3, GCS)

### Negative
- Cannot select irregular regions directly
- Users must pre-process for polygon-based ROIs
- Cannot select based on administrative boundaries without preprocessing

## Future Alternatives

1. **Polygon ROI**: Add geopandas dependency, rasterize polygon to mask
2. **Shapefile support**: Read administrative boundaries from file
3. **Named regions**: Integrate with spatial indices (e.g., GADM, USGS)

## Implementation Notes

When users need polygon-based ROI:
1. Convert polygon to bounding box (covers full polygon)
2. Post-filter results using point-in-polygon checks in results CSV
3. Or use external tools (GDAL, QGIS) to mask raster, then process

## References

- ROI specification in config.py (see terraflow/config.py)
- Clipping implementation in geo.py (see terraflow/geo.py)
- [Config schema documentation](../config/schema.md)
- [Architecture overview](overview.md)
