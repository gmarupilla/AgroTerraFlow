# TerraFlow Feature Roadmap

Last Updated: 2026-02-06

## Overview

This document outlines the strategic direction for TerraFlow development, organized by priority and implementation complexity. Features are grouped into three main tracks:

1. **Stability & Quality** (In Progress)
2. **Capability Expansion** (Planned for v1.0)
3. **Production Features** (Future)

---

## Track 1: Stability & Quality ✅ (COMPLETED)

Features completed in this phase improve reliability, testability, and maintainability.

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
- [x] Sync package version (0.1.5) across pyproject.toml and __init__.py

### ✅ Code Quality
- [x] Fix spatial sampling bias (random.sample vs list slicing)
- [x] Improve logging messages with context
- [x] Add validation hooks in Pydantic models

---

## Track 2: Capability Expansion (PLANNED FOR v1.0)

Features that add significant value while maintaining focus on agricultural modeling.

### 📌 Progress Tracking & Observability (Priority: HIGH)

**Goal**: Users can monitor long-running jobs and understand what's happening.

#### Features
- **Progress bar**: Show sampling progress for large ROIs
  - Display: `Sampling cells: [████████░░] 80/100`
  - Use: `tqdm` library (optional dependency)
  
- **Runtime estimation**: Predict total time based on raster size
  - Calculate in load phase before starting sampling
  - Log: "Estimated time: 2.5 minutes for 10,000 cells"
  
- **Sampling statistics logging**:
  - Valid cell count in ROI
  - Sampling ratio (sampled / valid)
  - Geographic extent statistics
  
**Implementation Files**: `pipeline.py`
**Estimated Effort**: 4-6 hours
**Tests Required**: Progress accuracy, timeout handling

---

### 📌 Enhanced Climate Data Support (Priority: HIGH)

**Goal**: Support per-cell climate variation instead of single global average.

#### Current Behavior
- Loads climate CSV, takes mean of each column
- Applies same values to all sampled cells
- Ineffective for geographically diverse regions

#### Proposed Behavior
- Accept climate CSV with same row count as cells
- Match cells to climate records by index or ID
- Or: Create spatial index (lat/lon) and interpolate climate for each cell
- Fall back to global average if indices unavailable

#### Features
- **Index-based matching**: Cell ID → climate row
- **Spatial interpolation**: Use cell lat/lon to interpolate climate
- **Validation**: Check climate data covers all sampled cells
- **Documentation**: Config examples for different climate formats

**Implementation Files**: `ingest.py`, `pipeline.py`
**Estimated Effort**: 8-10 hours
**Tests Required**: Interpolation accuracy, edge cases (sparse data)
**Dependencies**: `scipy` (optional, for interpolation)

---

### 📌 Run Fingerprinting & Reproducibility (Priority: HIGH)

**Goal**: Track inputs/outputs for reproducibility and auditing.

#### Features
- **Manifest file** (`manifest.json`):
  ```json
  {
    "version": "0.1.5",
    "timestamp": "2026-02-06T14:30:00Z",
    "config_hash": "sha256:abc123...",
    "raster_hash": "sha256:def456...",
    "climate_hash": "sha256:ghi789...",
    "output_hash": "sha256:jkl012...",
    "sampled_cells": 500,
    "valid_cells_in_roi": 1000,
    "execution_time_seconds": 12.34
  }
  ```

- **Checksum computation**: SHA256 for all input/output files
- **Provenance tracking**: Record exact config used, versions, parameters
- **Reproducibility verification**: Re-run with same config produces identical hash

#### Implementation Files**: `utils.py`, `pipeline.py`, new `fingerprint.py`
**Estimated Effort**: 6-8 hours
**Tests Required**: Hash consistency, manifest validation

---

### 📌 Large Raster Optimization (Priority: MEDIUM)

**Goal**: Handle multi-gigabyte rasters without OOM (out of memory).

#### Current Limitations
- Loads entire clipped raster into memory: `raster.read(1, masked=True)`
- Valid cell collection is O(n) memory
- DataFrame creation loads all results

#### Proposed Features
- **Streaming reads**: Process raster in chunks/windows
- **Iterative sampling**: Don't pre-compute all valid cells
- **Parquet output**: Write results incrementally to disk (vs CSV)
- **Lazy evaluation**: Yield results rather than accumulate

#### Implementation Strategy
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
