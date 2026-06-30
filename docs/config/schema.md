---
title: Configuration Schema
description: Complete YAML configuration reference for TerraFlow — ROI, model parameters, climate strategies, and CRS options.
icon: material/file-cog-outline
tags:
  - Configuration
  - Reference
---

# Configuration Schema

TerraFlow uses a single YAML configuration file that maps to the `PipelineConfig` model.
It is validated with Pydantic v2 and rejects unknown fields. Geographic coordinates are validated with custom pydantic field validators.

## Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `raster_path` | string | Path to the input raster (GeoTIFF). |
| `raster_band` | integer | 1-based rasterio band index for multi-band inputs (default: `1`). Out-of-range values raise `ValueError` at start-up; the selected band is captured in `manifest.json`. |
| `climate_csv` | string | Path to the climate CSV (must have `lat`, `lon`, and climate variable columns). |
| `output_dir` | string | Directory to write run outputs. |
| `roi` | object | Region of interest definition (bbox supported). |
| `model_params` | object | Parameters for suitability scoring. |
| `climate` | object | Climate data handling configuration (optional, defaults to spatial interpolation). |
| `sensitivity` | object | Optional Sobol' / Morris sensitivity analysis block (consumed by `terraflow sensitivity`). |
| `validation` | object | Optional spatial-block CV block (consumed by `terraflow validate`). |
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

| Field | Type | Default | Description |
|---|---|---|---|
| `v_min` / `v_max` | float | — | Vegetation index suitability range |
| `t_min` / `t_max` | float | — | Temperature (°C) suitability range |
| `r_min` / `r_max` | float | — | Rainfall (mm) suitability range |
| `w_v` / `w_t` / `w_r` | float | — | Weights (must sum to 1.0) |
| `uncertainty_samples` | int | `0` | Monte Carlo draws per cell for score confidence intervals. Requires `interpolation_method: kriging`. `0` disables. |

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
  uncertainty_samples: 0  # set >0 with kriging to get score_ci_low/score_ci_high
```

## Climate configuration

Climate data is applied ==per-cell== using configurable interpolation strategies and algorithms.

### `climate` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `strategy` | string | `"spatial"` | `"spatial"` or `"index"` — how cells are matched to climate observations |
| `interpolation_method` | string | `"linear"` | `"linear"`, `"kriging"`, or `"idw"` — spatial algorithm (ignored when `strategy: index`) |
| `variogram_mode` | string | `"standard"` | `"standard"` tries spherical/exponential/Gaussian; `"extended"` also evaluates nested kriging candidates (kriging only) |
| `fallback_to_mean` | bool | `true` | Use global mean for cells outside interpolation range |
| `cell_id_column` | string | `null` | Column for explicit cell ID matching (index strategy only) |

### Interpolation methods

=== "linear (default)"

    Fast triangular interpolation via `scipy.interpolate.griddata`. No extra dependencies.

    ```yaml title="config.yml"
    climate:
      strategy: spatial
      interpolation_method: linear
      fallback_to_mean: true
    ```

=== "kriging"

    Ordinary Kriging via `pykrige`. Geostatistically optimal; selects variogram model automatically via LOOCV.
    Adds `{var}_krig_std` columns to output. Combine with `uncertainty_samples` for score confidence intervals.

    ```yaml title="config.yml"
    climate:
      strategy: spatial
      interpolation_method: kriging
      variogram_mode: standard
      fallback_to_mean: true
    model_params:
      # ... other params ...
      uncertainty_samples: 500  # produces score_ci_low / score_ci_high
    ```

    Set `variogram_mode: extended` to evaluate additional nested candidates and record their LOOCV scores in `report.json`. Extended mode fits custom nested variograms before LOOCV, so it is slower than standard mode on large station networks.

    !!! note "Requires pykrige"
        Install with `pip install terraflow-agro[kriging]` or `pip install pykrige`.

=== "idw"

    Inverse Distance Weighting (power=2). Faster than kriging, no uncertainty output.

    ```yaml title="config.yml"
    climate:
      strategy: spatial
      interpolation_method: idw
      fallback_to_mean: true
    ```

=== "index"

    Match climate CSV rows to cells by row order or explicit cell ID. No interpolation.

    ```yaml title="config.yml"
    climate:
      strategy: index
      cell_id_column: null    # optional: column for explicit ID matching
      fallback_to_mean: true
    ```

### Climate CSV format

Must include `lat` and `lon` columns with valid coordinates:

```csv
lat,lon,mean_temp,total_rain
40.005,-100.005,22.5,650
40.015,-99.995,23.1,680
40.025,-99.985,21.8,620
```

- **`lat`**: Latitude in [-90, 90]
- **`lon`**: Longitude in [-180, 180]
- **Climate variables**: One or more numeric columns (`mean_temp`, `total_rain`, etc.)

If `climate` is omitted entirely, defaults to `strategy: spatial`, `interpolation_method: linear`, `variogram_mode: standard`, `fallback_to_mean: true`.
