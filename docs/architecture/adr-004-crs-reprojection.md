# ADR-004: CRS Reprojection for ROI and Output Coordinates

**Status**: Accepted
**Date**: 2026-02-19
**Deciders**: TerraFlow Contributors
**Tickets**: TERRA-010 (ROI clipping silent wrong-results), TERRA-011 (lat/lon in projected metres)

## Context

### Problem 1 — ROI clipping silently returned wrong data (TERRA-010)

The USDA Cropland Data Layer (CDL) — the primary supported raster — is stored in
**EPSG:5070 (NAD83 / Conus Albers)** with coordinate values in metres.  Demo
configs express the ROI in **WGS 84 degrees** (e.g. `xmin: -101, ymin: 38`).

The old `clip_raster_to_roi` passed the WGS 84 degree values directly to
`rasterio.windows.from_bounds` which expected Albers metres.  The resulting
window was orders of magnitude smaller than a single pixel, so rasterio returned
the full raster silently.  No error was raised; the pipeline appeared to work
while actually ignoring the ROI.

Additionally, when the ROI was genuinely outside the raster extent, the function
returned the full raster rather than raising an error, masking misconfiguration.

### Problem 2 — lat/lon output in projected metres (TERRA-011)

Because cell-centre coordinates were taken directly from `rasterio.transform.xy`
in the raster's native CRS, the `lat` and `lon` columns in `results.csv`
contained Albers-metre values (~1 000 000 m) rather than geographic degrees.
Downstream tools (mapping, climate interpolation) that expected WGS 84 degrees
produced garbage results silently.

## Decision

### 1. Mandatory CRS reprojection in `clip_raster_to_roi`

`terraflow.geo.clip_raster_to_roi` now accepts an `roi_crs` parameter
(default `"EPSG:4326"`).  When the ROI CRS differs from the raster CRS, all
four ROI corners are transformed with **pyproj** (`always_xy=True`) and the
axis-aligned bounding box of the reprojected corners is used for clipping.  This
handles non-linear (curved-grid) projections correctly.

Strict error semantics replace the silent-fallback behaviour:

- Invalid ROI bounds (`xmin ≥ xmax` or `ymin ≥ ymax`) → `ValueError` **before** reprojection.
- Degenerate window after reprojection (NaN width/height due to numerically invalid coordinates) → clean `ValueError`.
- Empty clipped data (ROI genuinely does not intersect the raster) → `ValueError` with a diagnostic message that includes the raster's actual extent.

### 2. WGS 84 output coordinates in `run_pipeline`

After clipping, cell-centre coordinates are computed in the raster's native CRS
via `rasterio.transform.xy`.  If the native CRS is not WGS 84 (EPSG:4326) they
are then reprojected to WGS 84 with a single vectorised `Transformer.transform`
call.  The `lat` / `lon` columns in the output DataFrame always contain
geographic degrees regardless of the input raster's CRS.

### 3. `roi_crs` configuration field

A new optional `roi_crs: str` field (default `"EPSG:4326"`) was added to the
`ROI` Pydantic model.  It is forwarded from the config YAML → `PipelineConfig`
→ `clip_raster_to_roi`.  Users can supply WGS 84 bbox coordinates and let the
pipeline handle reprojection, or supply native-CRS coordinates by setting
`roi_crs` to match the raster.

### 4. `roi_crs` in `stats.py` surface API

`summarize_raster`, `summarize_raster_file`, `compare_rasters`, and
`batch_summarize` gained an optional `roi_crs` parameter.  When omitted it
defaults to the raster's own CRS so that callers passing native-CRS coordinates
are unaffected (backward compatible).

## Consequences

### Positive

- ✅ ROI clipping is now geometrically correct for any combination of raster CRS and ROI CRS.
- ✅ `lat` / `lon` output columns are always WGS 84 geographic degrees — safe to pass directly to mapping libraries and the climate interpolator.
- ✅ Misconfigured or non-overlapping ROIs raise a clear `ValueError` instead of silently returning the full raster.
- ✅ Climate spatial interpolation operates in the same WGS 84 coordinate space as the weather-station lat/lon values, eliminating the unit mismatch that caused all cells to fall back to the global mean.
- ✅ No breaking change for callers who supply WGS 84 bbox values (default behaviour unchanged).

### Negative

- ⚠️ **New dependency**: `pyproj>=3.0` added to `[project.dependencies]`.  pyproj bundles PROJ data (~30 MB) so the installed footprint increases.
- ⚠️ Callers of `clip_raster_to_roi` or `stats.py` functions that previously passed native-CRS coordinates **without** setting `roi_crs` will now have those coordinates reprojected from WGS 84 (the new default), which may raise `ValueError` for previously-passing tests.  The fix is to set `roi_crs` to match the raster's CRS.
- ⚠️ Reprojecting all four corners adds a small latency (~1 ms); negligible in practice.

### Neutral

- The `roi_crs: "EPSG:4326"` default was chosen because all user-facing documentation has always described ROI coordinates as "longitude / latitude degrees", making WGS 84 the clearly expected default.

## Alternatives Considered

### A — Require all ROI coordinates to be in the raster's native CRS

Rejected.  Users cannot be expected to know that CDL is EPSG:5070 and to supply
metre-valued coordinates.  WGS 84 degrees are the universal lingua franca for
geographic bboxes.

### B — Auto-detect whether coordinates look like degrees vs metres

Rejected.  Heuristics based on magnitude are fragile (e.g. UTM Zone 14N
eastings overlap valid degree ranges for other projections).  Explicit `roi_crs`
is unambiguous and auditable.

### C — Reproject the raster to WGS 84 at ingestion time

Rejected.  Reprojecting the full raster would be slow, lossy (resampling
artefacts), and would discard the native-CRS metadata needed for accurate
area/distance calculations.  Reprojecting the small ROI bbox is fast and lossless.

## Related Decisions

- **ADR-001**: Single-band raster processing — CRS reprojection reads band 1 only, consistent.
- **ADR-002**: BBox ROI only — reprojection applies to the bbox corners; no geometry complexity.
- **ADR-003**: Climate interpolation — spatial interpolation now operates in the corrected WGS 84 coordinates.

## Future Enhancements

1. Extend `roi.type` to support GeoJSON polygon ROIs with CRS-aware reprojection.
2. Validate that the reprojected ROI covers a non-trivial fraction of the raster to catch partially-overlapping misconfigurations.
3. Expose raster native CRS in the run fingerprint / manifest for full provenance.
