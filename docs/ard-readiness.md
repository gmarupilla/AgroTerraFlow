---
title: ARD Readiness Checklist
description: Analysis-Ready Data (ARD) readiness assessment — auditable provenance, deterministic identity, stable artifact contracts, and reproducibility.
icon: material/shield-check
tags:
  - ARD
  - Reference
  - Reproducibility
---

# ARD Readiness Checklist

Assessment of TerraFlow's Analysis-Ready Data (ARD) properties.  ARD in
geospatial science means outputs are traceable, reproducible, and stable enough
to be used directly in downstream analysis without additional preparation.

---

## Auditable provenance

- [x] Every run writes `manifest.json` containing:
    - Full config snapshot (as parsed Python dict)
    - SHA-256 fingerprints and byte-sizes of all input files
    - `DataCatalog` metadata (CRS, bounds, nodata, shape) for each layer
    - Code version and optional git SHA
    - UTC creation timestamp
- [x] `manifest.json` is the single source of truth for a run's provenance
- [x] `report.json` records per-layer coverage metrics, nodata summaries,
      and per-step wall-clock timings

---

## Deterministic run identity

- [x] `run_fingerprint` is computed from config + ROI geometry + input
      file contents (SHA-256)
- [x] `mtime` is excluded from the fingerprint — identity is content-based
- [x] Same config + same ROI + same input files → identical `run_fingerprint`
      regardless of machine, clone time, or file copy
- [x] Fingerprint verified by regression test
      (`tests/test_artifacts.py::TestDeterminism::test_fingerprint_stable_across_different_mtimes`)
- [ ] Random cell sampling is not seeded by the fingerprint — **known gap**
      (documented in [Run Identity](architecture/run-identity.md#limitations))

---

## Stable artifact contracts

- [x] `features.parquet` schema v1 (frozen, stored in Parquet file metadata)
- [x] Schema contract enforced by automated tests (`tests/test_artifacts.py`)
- [x] `run_id` column links every row back to `manifest.json`
- [x] `lat`/`lon` guaranteed to be WGS84 geographic degrees (CRS enforcement)
- [x] Column order is stable across runs and platforms

---

## Clear failure modes

- [x] ROI entirely outside raster extent → `ValueError` with clear message
- [x] Input file missing → `FileNotFoundError` with file path
- [x] Malformed YAML config → `ValueError` with parse location
- [x] CRS reprojection failure → propagated `pyproj.exceptions.CRSError`
- [x] No valid (non-nodata) cells in ROI → `ValueError` with cell count
- [x] All errors produce non-zero exit code and `ERROR: …` on `stderr`

---

## Reproducibility claims — what is and is not guaranteed

### Guaranteed

| Claim | Evidence |
|---|---|
| Same inputs → same `run_fingerprint` | Content-based SHA-256; mtime excluded; regression test |
| Same `run_fingerprint` → same `features.parquet` schema | Schema version frozen in file metadata |
| Same `run_fingerprint` → same `report.json` coverage metrics | Deterministic raster clip + numpy stats |
| Identical re-run is a no-op | Cached run detection; `features.parquet` mtime unchanged |
| `lat`/`lon` columns always WGS84 | Forced reprojection in pipeline; tested |

### Not guaranteed (known limitations)

| Claim | Reason |
|---|---|
| Same inputs → identical sampled cell set | `random.sample` uses unseeded PRNG; cells may differ |
| Same inputs → byte-identical `features.parquet` | Parquet metadata may include platform-dependent info |
| Fingerprint stable across major library upgrades | Shapely geometry normalisation may change between major versions |

---

## Nodata policy

- The pipeline clips the raster to the ROI window and reads band 1 with
  `masked=True` (respects the raster's nodata value if set).
- Masked (nodata) cells are excluded from sampling and scoring.
- `report.json` records `n_roi_nodata_cells` and `roi_nodata_fraction` for
  every run so coverage gaps are always visible.
- No imputation or gap-filling of nodata cells is performed by the pipeline.

---

## CRS policy

- ROI bounding box coordinates may be expressed in any CRS via `roi_crs`
  (default: `EPSG:4326`).
- The ROI is reprojected to the raster's native CRS before clipping.
- Cell centroids are always reprojected to WGS84 (EPSG:4326) for output.
- CRS enforcement is tested for both geographic (EPSG:4326) and projected
  (EPSG:32614) rasters.

---

## Decision support interpretation

!!! info "How to interpret suitability scores"
    TerraFlow outputs a composite suitability score in `[0.0, 1.0]` and a
    categorical label (`low` / `medium` / `high`).  These are **model outputs,
    not ground truth**.  They reflect the normalisation ranges and weights
    specified in the config.  Users should:

    1. Verify that `v_min`/`v_max`, `t_min`/`t_max`, `r_min`/`r_max` are
       appropriate for their crop type and region.
    2. Verify that `w_v`, `w_t`, `w_r` reflect agronomic priorities.
    3. Treat `label` as a first-pass triage tool, not a definitive agronomic
       recommendation.
    4. Cross-reference `report.json` coverage metrics: low `roi_coverage_fraction`
       may indicate ROI/raster alignment issues that reduce result reliability.
