# terraflow.climate

The climate module provides spatial interpolation and index-based matching for aligning climate observations to raster cells.

## Overview

**New in v0.2.0**: Replaces global mean climate approach with per-cell interpolation using:
- **Spatial interpolation**: scipy.interpolate.griddata with linear and nearest-neighbor methods
- **Index-based matching**: Row order or explicit cell ID matching
- **Graceful fallbacks**: Global mean values for cells outside interpolation range or with sparse data

## API Documentation

::: terraflow.climate

