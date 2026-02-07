# TerraFlow Feature Roadmap & Enhancement Guide

**Last Updated:** February 6, 2026  
**Project Status:** Production-Ready with Enhancement Opportunities

---

## Vision

TerraFlow should evolve into a **comprehensive, scalable geospatial modeling framework** that enables researchers and practitioners to:
- Build reproducible agricultural suitability analyses
- Process rasters efficiently at scale
- Integrate multi-source climate and environmental data
- Generate publication-quality visualizations and reports
- Track and audit model runs for reproducibility

---

## Priority Matrix

### 🔴 Critical (Would be breaking bugs if they existed)
All addressed in current implementation ✅

### 🟠 High Priority (1-2 weeks effort)
1. **[SAMPLING] Fix spatial bias in cell selection**
   - **Issue:** `valid_indices[:max_cells]` selects cells from top-left corner only
   - **Solution:** Use `random.sample(valid_indices, k=max_cells)` for unbiased sampling
   - **Impact:** Statistically representative results
   - **Complexity:** Low (3-line change)
   - **Test:** Unit test for sampling distribution

2. **[CLIMATE] Support per-cell climate variation**
   - **Issue:** Climate data aggregated globally; all cells get same value
   - **Solution:** Support spatial joins - match climate data to cells by location
   - **Impact:** More realistic suitability scores
   - **Complexity:** Medium (requires spatial join logic)
   - **Test:** Integration test with gridded climate data

3. **[FEATURES] Add ROI/output mask to results**
   - **Issue:** Users can't easily identify which cells were in ROI
   - **Solution:** Add "in_roi" boolean column to results
   - **Impact:** Better data interpretation
   - **Complexity:** Low (1 boolean column)
   - **Test:** Assert all results have in_roi=True

### 🟡 Medium Priority (2-4 weeks effort)
4. **[GEOMETRY] Extend ROI support to polygons**
   - **Issue:** Only supports bounding boxes; users want arbitrary geometries
   - **Solution:** Accept GeoJSON/Shapefile polygons, use rasterio mask
   - **Impact:** More flexible analyses
   - **Complexity:** Medium (geometry handling)
   - **Test:** Test with various polygon geometries

5. **[OPERATIONS] Add progress indicators for long operations**
   - **Issue:** No feedback on long-running jobs
   - **Solution:** Use `tqdm` for progress bars in loops
   - **Impact:** Better UX for large datasets
   - **Complexity:** Low (add progressbar)
   - **Test:** Visual confirmation

6. **[REPORTING] Implement run fingerprinting (promised in docs)**
   - **Issue:** Documented but not implemented
   - **Solution:** Generate manifest.json with inputs, outputs, metadata
   - **Impact:** Full reproducibility and audit trail
   - **Complexity:** Medium (JSON generation, checksumming)
   - **Test:** Verify manifest contents

7. **[REPORTING] Generate run report (promised in docs)**
   - **Issue:** Documented but not implemented
   - **Solution:** Create report.json with QA metrics, timing, coverage
   - **Impact:** Operational visibility
   - **Complexity:** Medium (metrics collection)
   - **Test:** Assert report contains expected fields

### 🟢 Low Priority (Nice to have)
8. **[PERFORMANCE] Lazy loading for large rasters**
   - **Why:** Current approach loads all data into memory
   - **Solution:** Implement windowed reading
   - **Impact:** Handle rasters >10GB
   - **Complexity:** High (streaming architecture)

9. **[FEATURES] Support multi-band analysis**
   - **Why:** Users often have multi-spectral data
   - **Solution:** Config option to combine bands (NDVI, etc.)
   - **Impact:** More use cases
   - **Complexity:** Medium

10. **[FEATURES] Cloud-native support**
    - **Why:** Enable Azure/AWS/GCS integration
    - **Solution:** Virtual file system support (rasterio + fsspec)
    - **Impact:** Scalability
    - **Complexity:** High

---

## Detailed Feature Specifications

### Feature 1: Unbiased Cell Sampling 🔴 HIGH

**Current Code:**
```python
sampled_indices = valid_indices[:max_cells]  # Top-left bias!
```

**Proposed Code:**
```python
import random

sampled_indices = random.sample(valid_indices, k=min(max_cells, len(valid_indices)))
```

**Benefits:**
- ✅ Statistically representative
- ✅ No spatial bias
- ✅ 1-line change
- ✅ Backward compatible

**Testing:**
```python
def test_unbiased_sampling():
    """Verify sampling covers entire ROI."""
    valid_indices = [(r, c) for r in range(100) for c in range(100)]
    sampled = random.sample(valid_indices, k=50)
    
    # Check distribution across quadrants
    q1 = sum(1 for r, c in sampled if r < 50 and c < 50)
    q2 = sum(1 for r, c in sampled if r < 50 and c >= 50)
    q3 = sum(1 for r, c in sampled if r >= 50 and c < 50)
    q4 = sum(1 for r, c in sampled if r >= 50 and c >= 50)
    
    # Each quadrant should have ~12-13 cells (±20%)
    assert 8 < q1 < 18 and 8 < q2 < 18 and 8 < q3 < 18 and 8 < q4 < 18
```

---

### Feature 2: Per-Cell Climate Data 🔴 HIGH

**Current Limitation:**
- Climate CSV aggregated to single mean values
- All cells get identical temperature/rainfall

**Proposed Solution:**
- Accept gridded climate data (GeoTIFF or similar)
- Or accept climate CSV with lat/lon columns
- Spatially join climate to raster cells

**New Config Format:**
```yaml
climate_data:
  type: "gridded"  # or "point" for CSV
  path: "climate/temperature.tif"
  aggregate: "mean"  # mean, max, min
```

**Implementation Approach:**
```python
def load_climate_for_cells(
    climate_path: str,
    cell_coords: List[tuple],
    raster_transform: Affine
) -> Dict[tuple, Dict[str, float]]:
    """Load climate values for specific cells."""
    with rasterio.open(climate_path) as climate_raster:
        climate_by_cell = {}
        for row, col in cell_coords:
            x, y = xy(raster_transform, row, col, offset="center")
            # Query climate raster at this location
            value = climate_raster.sample([(x, y)])
            climate_by_cell[(row, col)] = float(value)
    return climate_by_cell
```

**Benefits:**
- ✅ Realistic climate variation
- ✅ Better suitability scores
- ✅ Supports multiple climate sources

---

### Feature 3: Polygon ROI Support 🟡 MEDIUM

**Current Limitation:**
- Only bounding box (xmin, ymin, xmax, ymax)
- Users often have irregular AOI boundaries

**Proposed Solution:**
```yaml
roi:
  type: "polygon"  # or "bbox" (default)
  source: "aoi.geojson"  # GeoJSON file
  properties:
    field_name: "value"  # Filter geometries
```

**Implementation:**
```python
def clip_raster_to_polygon(
    raster: DatasetReader,
    geom_path: str | Path,
) -> Tuple[np.ma.MaskedArray, Dict[str, Any]]:
    """Clip raster using polygon geometry."""
    import geopandas as gpd
    
    gdf = gpd.read_file(geom_path)
    geom = gdf.geometry.unary_union
    
    # Rasterio mask function
    from rasterio.mask import mask
    
    clipped, transform = mask(raster, [geom], crop=True)
    return np.ma.masked_array(clipped[0]), transform
```

**Benefits:**
- ✅ Arbitrary AOI shapes
- ✅ Multi-polygon support
- ✅ Attribute filtering

---

### Feature 4: Run Fingerprinting 🟡 MEDIUM

**Current State:** Documented but not implemented

**Proposed manifest.json:**
```json
{
  "version": "1.0",
  "timestamp": "2026-02-06T10:30:00Z",
  "inputs": {
    "raster": {
      "path": "data/dem.tif",
      "sha256": "abc123...",
      "crs": "EPSG:4326",
      "shape": [1000, 1000]
    },
    "climate_csv": {
      "path": "data/climate.csv",
      "sha256": "def456...",
      "rows": 100
    },
    "config": {
      "sha256": "ghi789...",
      "model_params": {...}
    }
  },
  "outputs": {
    "results_csv": {
      "path": "outputs/results.csv",
      "rows": 500,
      "sha256": "jkl012..."
    }
  },
  "environment": {
    "terraflow_version": "0.1.5",
    "python": "3.13.0",
    "gdal": "3.8.0"
  }
}
```

**Implementation:**
```python
def generate_manifest(
    config_path: Path,
    raster_path: Path,
    climate_path: Path,
    output_paths: Dict[str, Path]
) -> Dict:
    """Generate reproducibility manifest."""
    import hashlib
    import json
    from datetime import datetime
    
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                h.update(chunk)
        return h.hexdigest()
    
    manifest = {
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "inputs": {
            "config": {"sha256": sha256_file(config_path)},
            "raster": {"sha256": sha256_file(raster_path)},
            "climate": {"sha256": sha256_file(climate_path)}
        },
        "outputs": {
            name: {"sha256": sha256_file(path)}
            for name, path in output_paths.items()
        }
    }
    
    return manifest
```

**Benefits:**
- ✅ Full reproducibility
- ✅ Audit trail
- ✅ Input validation (detect changed files)

---

### Feature 5: Progress Indicators 🟡 MEDIUM

**Current State:** Silent operations, no feedback

**Proposed Solution:**
```python
from tqdm import tqdm

# In pipeline.py
for cell_id, (row, col) in enumerate(tqdm(sampled_indices, desc="Processing cells")):
    v_index = float(clipped_data[row, col])
    # ...
```

**Benefits:**
- ✅ User feedback for long operations
- ✅ ETA estimation
- ✅ Minimal code change

---

## Implementation Roadmap

### Phase 1: Foundation (1 month)
- Week 1: Unbiased sampling + per-cell climate
- Week 2: Run fingerprinting
- Week 3: Progress indicators
- Week 4: Testing, docs, release 0.2.0

### Phase 2: Advanced Geospatial (1-2 months)
- Polygon ROI support
- Multi-band rasters
- Cloud storage integration

### Phase 3: Scale & Performance (2-3 months)
- Lazy loading
- Parallel processing
- Performance benchmarking

---

## Contribution Guidelines

### Adding a New Feature

1. **Create an issue** describing the feature
2. **Comment on the issue** that you're working on it
3. **Branch from main:**
   ```bash
   git checkout -b feature/description
   ```
4. **Implement with tests:**
   ```bash
   # Write tests first (TDD)
   # Implement feature
   # Run: make test && make lint
   ```
5. **Add documentation:**
   - Update docstrings
   - Add example in README if user-facing
6. **Submit PR** with clear description

### Code Quality Standards

- ✅ All tests pass (`make test`)
- ✅ Lint passes (`make lint`)
- ✅ New public functions have docstrings
- ✅ Error paths tested
- ✅ Type hints present

### Testing Checklist

- ✅ Unit tests for individual functions
- ✅ Integration tests for workflows
- ✅ Error handling tests
- ✅ Edge case tests
- ✅ Real data tests if applicable

---

## Success Metrics

After implementing these features, TerraFlow should:

| Metric | Target | Current |
|--------|--------|---------|
| Test Coverage | >90% | ~85% |
| Documentation | Complete | ~95% |
| User-Reported Bugs | <1/month | 0 |
| Installation Size | <100MB | ~120MB |
| Sample Runtime | <10s (10K cells) | ~5s |
| Publication Use | 5+ papers | 1 |

---

## Community Engagement

### Where to Contribute
- **Bug fixes:** Start with issues tagged `bug`
- **Features:** Comment on roadmap items
- **Docs:** Typos and clarifications welcome
- **Examples:** Submit working notebooks
- **Performance:** Profile and optimize hot paths

### Getting Help
- GitHub Discussions for questions
- Issues for bugs and feature requests
- Docstrings for API reference
- Examples folder for walkthroughs

---

## References

- [GDAL/Rasterio Documentation](https://rasterio.readthedocs.io/)
- [GeoPandas for Vector Data](https://geopandas.org/)
- [Xarray for Multidimensional Data](https://docs.xarray.dev/)
- [Dask for Parallel Computing](https://www.dask.org/)
- [Cloud-Optimized GeoTIFF](https://www.cogeo.org/)

---

**Updated:** February 6, 2026  
**Status:** Current Feature Set Implemented & Tested ✅  
**Next Milestone:** v0.2.0 with unbiased sampling + per-cell climate
