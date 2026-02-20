---
title: Configuration Schema
description: Complete YAML configuration reference for TerraFlow — ROI, model parameters, climate strategies, and CRS options.
icon: material/file-cog-outline
tags:
  - Configuration
  - Reference
---

# Configuration Schema

TerraFlow v0.2.0 uses a single YAML configuration file that maps to the `PipelineConfig` model.
It is validated with Pydantic v2 and rejects unknown fields. Geographic coordinates are validated with custom pydantic field validators.

## Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `raster_path` | string | Path to the input raster (GeoTIFF). |
| `climate_csv` | string | Path to the climate CSV (must have `lat`, `lon`, and climate variable columns). |
| `output_dir` | string | Directory to write run outputs. |
| `roi` | object | Region of interest definition (bbox supported). |
| `model_params` | object | Parameters for suitability scoring. |
| `climate` | object | Climate data handling configuration (optional, defaults to spatial interpolation). |
| `max_cells` | integer | Maximum cells sampled from the ROI (default: 500). |

## ROI (bbox)

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `"bbox"` | Must be `"bbox"` (only supported type). |
| `xmin` | float | — | West boundary. |
| `ymin` | float | — | South boundary. |
| `xmax` | float | — | East boundary. |
| `ymax` | float | — | North boundary. |
| `roi_crs` | string | `"EPSG:4326"` | CRS of the bbox coordinates. Use any EPSG code or WKT string accepted by pyproj. Set to the raster's native CRS (e.g. `"EPSG:5070"`) when coordinates are in projected metres. |

### ROI Examples

=== "WGS 84 (Common)"

    Most common case — specifying your region in latitude/longitude degrees.

    ```yaml title="config.yml"
    roi:
      type: bbox
      xmin: -120.5   # West longitude
      ymin: 34.0     # South latitude
      xmax: -118.0   # East longitude
      ymax: 35.5     # North latitude
      # roi_crs defaults to EPSG:4326 — no change needed
    ```

=== "Projected CRS (Specify in WGS84)"

    Your raster is in a projected CRS (e.g., UTM, Albers), but you specify ROI in WGS84 degrees. TerraFlow reprojects automatically.

    ```yaml title="config.yml"
    roi:
      type: bbox
      xmin: -120.5   # WGS84 degrees
      ymin: 34.0
      xmax: -118.0
      ymax: 35.5
      roi_crs: "EPSG:4326"   # Pipeline reprojects to raster CRS
    ```

=== "Projected CRS (Native Units)"

    Your raster is in UTM/Albers and you want to specify ROI in meters directly.

    ```yaml title="config.yml"
    roi:
      type: bbox
      xmin: 500000    # UTM easting (meters)
      ymin: 4200000   # UTM northing (meters)
      xmax: 600000
      ymax: 4300000
      roi_crs: "EPSG:32614"  # UTM Zone 14N — no reprojection
    ```

!!! note "Output Always in WGS84"
    Regardless of input CRS, the pipeline always writes `lat` / `lon` output columns in WGS 84 geographic degrees so downstream tools receive consistent coordinates.

## Model parameters

```yaml
model_params:
  v_min: 0.0
  v_max: 1.0
  t_min: 10.0
  t_max: 35.0
  r_min: 100.0
  r_max: 800.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
```

## Climate configuration (v0.2.0 — New feature)

Climate data is now applied ==per-cell== using configurable interpolation strategies. This replaces the global mean approach from v0.1.

=== "Spatial Interpolation (Recommended)"

    Use `scipy.interpolate.griddata` for linear interpolation with nearest-neighbor fallback. Best for scattered weather station data.

    ```yaml title="config.yml"
    climate:
      strategy: spatial        # Linear interpolation
      fallback_to_mean: true  # Use global mean for outliers
    ```

    !!! tip "Best For"
        - Weather station networks
        - Satellite-derived gridded data
        - Arbitrary point observations
        - Requires ≥3 observation points

=== "Index-Based Matching"

    Match climate records to cells by row order or explicit cell ID. Best for pre-aligned data.

    ```yaml title="config.yml"
    climate:
      strategy: index
      cell_id_column: null    # Optional: column for explicit ID matching
      fallback_to_mean: true  # Pad with mean if data < cells
    ```

    !!! tip "Best For"
        - Pre-processed climate data aligned to your raster
        - Deterministic matching without interpolation
        - Large datasets where speed matters

### Climate CSV Format (Required)

Must include `lat` and `lon` columns with valid coordinates [-90°, 90°] and [-180°, 180°]:

```csv
lat,lon,mean_temp,total_rain
40.005,-100.005,22.5,650
40.015,-99.995,23.1,680
40.025,-99.985,21.8,620
```

### Climate CSV Format

Your `climate_csv` must contain:
- **`lat`**: Latitude in [-90, 90]
- **`lon`**: Longitude in [-180, 180]
- **Climate variables**: One or more columns like `mean_temp`, `total_rain`

**Example:**
```csv
lat,lon,mean_temp,total_rain,wind_speed
34.05,-118.24,22.5,250.0,3.2
34.10,-118.19,23.1,260.0,3.1
34.15,-118.14,21.8,240.0,3.4
```

### Strategy Details

**Spatial Interpolation** (`strategy: spatial`)
- Uses `scipy.interpolate.griddata` to interpolate climate values to each raster cell
- Best for: Weather station networks, satellite-derived gridded data, arbitrary point observations
- Requires: ≥3 observation points for linear interpolation
- Fallback: Uses global mean for cells outside interpolation range (if `fallback_to_mean: true`)

**Index-Based Matching** (`strategy: index`)
- Matches climate CSV rows directly to raster cells by index order
- Best for: Pre-processed climate data already aligned to your specific raster
- Requires: Exact or flexible row count matching
- Fallback: Pads with mean or raises error (if `fallback_to_mean: false`)

All fields except `climate` are required. If `climate` is omitted, defaults to spatial interpolation with fallback enabled.
