---
title: Roadmap
description: Strategic direction for TerraFlow — completed tracks, planned v1.0 features, and future production capabilities.
icon: material/road-variant
tags:
  - Development
  - Reference
---

# TerraFlow Feature Roadmap

Last Updated: 2026-02-06

## Overview

This document outlines the strategic direction for TerraFlow development, organized by priority and implementation complexity. Features are grouped into three main tracks:

<div class="grid" markdown>

:material-check-circle:{ .lg .middle style="color: #00c853" } **Track 1: Stability & Quality** <span class="status-completed">COMPLETED</span>
:   Reliability, testability, and maintainability improvements

:material-check-circle:{ .lg .middle style="color: #00c853" } **Track 2: Capability Expansion** <span class="status-completed">v0.2.0 RELEASED</span>
:   Per-cell climate interpolation and enhanced data support

:material-timer-sand:{ .lg .middle style="color: #00b0ff" } **Track 3: Production Features** <span class="status-planned">v1.0 PLANNED</span>
:   Progress tracking, fingerprinting, and operational deployment

</div>

---

## Track 1: Stability & Quality <span class="status-completed">✅ COMPLETED</span>

Features completed in this phase improve reliability, testability, and maintainability.

!!! success "Fully Implemented"
    All features in this track have been completed and released in v0.1.x series.

### ✅ Resource Management
- [x] Fix unclosed rasterio file handles (resource leak)
- [x] Implement proper context manager patterns
- [x] Add resource cleanup tests

### ✅ Error Handling & Validation
- [x] File existence validation before operations
- [x] ROI bounds validation (min < max)
- [x] Raster band count validation
- [x] Model parameter range validation (v_min < v_max, etc.)
- [x] Climate CSV column validation
- [x] Configuration file validation with helpful error messages
- [x] Fix overly broad exception handling (bare `except`)

### ✅ Testing
- [x] CLI unit tests (arguments, errors, help)
- [x] Error path tests (missing files, invalid configs)
- [x] Geo module edge case tests (invalid bounds, non-intersecting ROI)
- [x] Ingest module tests (file validation, malformed data)
- [x] Test coverage for 14 critical scenarios

### ✅ Documentation
- [x] Comprehensive module docstrings
- [x] Function parameter/return/exception documentation
- [x] Architecture Decision Records (ADRs)
- [x] CLI help text with examples

### ✅ Dependencies
- [x] Remove unused imports (xarray, geopandas)
- [x] Add version constraints for reproducibility
- [x] Sync package version (0.2.0) across pyproject.toml and __init__.py

### ✅ Code Quality
- [x] Fix spatial sampling bias (random.sample vs list slicing)
- [x] Improve logging messages with context
- [x] Add validation hooks in Pydantic models

---

## Track 2: Capability Expansion <span class="status-completed">✅ v0.2.0 RELEASED</span>

Features that add significant value while maintaining focus on agricultural modeling.

!!! success "Enhanced Climate Data Support (v0.2.0)"
    Per-cell climate interpolation is now fully implemented with two configurable strategies:
    
    - ✅ Spatial interpolation using `scipy.interpolate.griddata`
    - ✅ Index-based matching for pre-aligned data
    - ✅ Graceful fallback to global mean for sparse data
    - ✅ Comprehensive validation and 32 test cases
    - ✅ Full documentation and ADR-003

### 📌 Progress Tracking & Observability <span class="status-planned">v1.0 PLANNED</span>

**Goal**: Users can monitor long-running jobs and understand what's happening.

!!! example "Planned Features"
    **Progress bar**: Show sampling progress for large ROIs
    ```
    Sampling cells: [████████░░] 80/100
    ```
    
    **Runtime estimation**: Predict total time based on raster size  
    **Sampling statistics**: Valid cell count, sampling ratio, geographic extent

**Implementation**: `pipeline.py` | **Effort**: 4-6 hours | **Tests**: Progress accuracy, timeout handling

---

### 📌 Run Fingerprinting & Reproducibility <span class="status-planned">v1.0 PLANNED</span>

**Goal**: Track inputs/outputs for reproducibility and auditing.

!!! example "Manifest File"
    Generate `manifest.json` with complete provenance tracking:
    
    ```json
    {
      "version": "0.2.0",
      "timestamp": "2026-02-06T14:30:00Z",
      "config_hash": "sha256:abc123...",
      "raster_hash": "sha256:def456...",
      "sampled_cells": 500,
      "execution_time_seconds": 12.34
    }
    ```

**Implementation**: `utils.py`, `pipeline.py`, new `fingerprint.py` | **Effort**: 6-8 hours

---
1. Keep rasterio window-based reads
2. Process in overlapping windows with stride
3. Write batches to parquet file
4. Return summary stats instead of full DataFrame

**Implementation Files**: `pipeline.py`, new `output.py`
**Estimated Effort**: 12-16 hours
**Tests Required**: Memory usage, output consistency vs current approach
**Dependencies**: `pyarrow` (for parquet)

---

### 📌 Multi-Band Raster Support (Priority: MEDIUM)

**Goal**: Process multi-band data and create composite models.

#### Features
- **Band selection**: Config parameter `band: 1` (default) or `bands: [1, 2, 3]`
- **Composite scoring**: Combine multiple band indices
  - Weighted average: `score = 0.4*ndvi + 0.3*evi + 0.3*moisture`
  - Separate models: Run different model params per band
  
- **Auto-detection**: Recognize common indices from metadata
  - NDVI, EVI, NDBI, etc.
  
**Implementation Files**: `config.py`, `geo.py`, `model.py`
**Estimated Effort**: 10-12 hours
**Tests Required**: Band validation, multi-band aggregation
**Related ADR**: See [adr-001-band-selection.md](architecture/adr-001-band-selection.md)

---

### 📌 Polygon ROI Support (Priority: MEDIUM)

**Goal**: Support arbitrary polygon regions of interest (state boundaries, farms, etc.).

#### Current Limitation
- Only bounding box (4 parameters) supported
- Users with irregular regions must pre-process

#### Proposed Features
- **GeoJSON input**: Specify ROI as GeoJSON polygon
- **Shapefile support**: Load from .shp/.gpkg files
- **Named regions**: Integrate with GADM or similar
- **Boundary buffering**: Expand point locations to study areas

#### Implementation Strategy
1. Read polygon geometry via fiona/geopandas
2. Rasterize polygon to create mask
3. Apply mask to clipped raster
4. Continue normal pipeline

**Implementation Files**: `config.py`, `geo.py`, new `polygon.py`
**Estimated Effort**: 10-14 hours
**Tests Required**: Polygon accuracy, rasterization edge cases
**Dependencies**: `fiona` or `geopandas` (optional)
**Related ADR**: See [adr-002-bbox-roi.md](architecture/adr-002-bbox-roi.md)

---

## Track 3: Production Features (FUTURE)

Features for operational deployment, monitoring, and integration.

### 🎯 Cloud-Native Integration

- **S3/GCS input**: Read rasters directly from cloud storage
- **COG support**: Optimize for Cloud-Optimized GeoTIFF reads
- **Cloud output**: Write results to cloud blob storage
- **Distributed processing**: Support Spark/Dask for parallel regions

**Estimated Effort**: 20+ hours
**Priority**: Q3 2026+

---

### 🎯 Web Service & API

- **REST API**: Flask/FastAPI endpoint for running pipeline
- **Job queuing**: Background task processing (Celery)
- **Web UI**: Interactive map for ROI selection
- **Authentication**: API key management for hosted instance

**Estimated Effort**: 40+ hours
**Priority**: Q4 2026+

---

### 🎯 Temporal Analysis

- **Time series**: Process multiple rasters across time
- **Trend detection**: Identify suitability changes over seasons/years
- **Phenology**: Track seasonal crop development
- **Anomaly detection**: Identify unusual years/regions

**Estimated Effort**: 24-30 hours
**Priority**: Q3 2026+

---

### 🎯 Model Enhancements

- **Machine learning**: Learn weights from training data instead of manual specification
- **Bayesian uncertainty**: Quantify confidence in scores
- **Sensitivity analysis**: Identify which factors matter most
- **Custom indices**: Let users define new vegetation/climate indices

**Estimated Effort**: 30+ hours
**Priority**: Q4 2026+

---

### 🎯 Validation & Benchmarking

- **Cross-validation**: Leave-one-out or k-fold validation on known sites
- **Uncertainty bounds**: Confidence intervals around predictions
- **Comparison mode**: Compare results across model versions
- **Performance profiling**: Benchmark against standard datasets

**Estimated Effort**: 12-18 hours
**Priority**: Q2 2026

---

## Implementation Timeline

```
v0.2.0 (Q1 2026)
├─ Progress tracking ✓
├─ Large raster optimization ✓
├─ Enhanced climate support ✓
└─ Run fingerprinting ✓

v1.0.0 (Q2 2026)
├─ Multi-band support ✓
├─ Polygon ROI ✓
├─ Comprehensive tests ✓
└─ Production documentation ✓

v1.1.0 (Q3 2026)
├─ Cloud integration ✓
├─ Temporal analysis ✓
└─ Validation framework ✓

v2.0.0 (Q4 2026)
├─ Web API ✓
├─ ML models ✓
└─ Advanced analytics ✓
```

---

## Community Contribution Opportunities

Areas well-suited for external contributions:

1. **Integration tests** for different raster types (GeoTIFF, COG, NetCDF)
2. **Documentation** improvements and examples
3. **UI/visualization** enhancements
4. **Cloud provider adapters** (AWS, GCP, Azure)
5. **Model examples** for specific crops/regions
6. **Performance optimization** for specific hardware

---

## Decision Framework

For new features, consider:

1. **Alignment**: Does it serve agricultural modeling use cases?
2. **Simplicity**: Can it be explained in <5 minutes?
3. **Testability**: Can the feature be rigorously tested?
4. **Maintenance**: What's the ongoing support burden?
5. **Dependencies**: Do new libraries add value?

---

## References

- [Architecture Overview](architecture/overview.md)
- [ADR-001: Band Selection](architecture/adr-001-band-selection.md)
- [ADR-002: ROI Type](architecture/adr-002-bbox-roi.md)
- [Configuration Schema](config/schema.md)

