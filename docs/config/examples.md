---
title: Configuration Examples
description: Ready-to-use TerraFlow YAML configuration templates for common scenarios — WGS84 rasters, projected CRS, spatial and index climate strategies.
icon: material/file-document-multiple-outline
tags:
  - Configuration
  - Examples
---

# Configuration Examples

## Minimal (linear interpolation)

```yaml
raster_path: "examples/sample_data/soil.tif"
climate_csv: "examples/sample_data/climate.csv"
output_dir: "outputs"
roi:
  type: bbox
  xmin: -120.5
  ymin: 34.0
  xmax: -118.0
  ymax: 35.5
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
climate:
  strategy: spatial
  interpolation_method: linear   # default — fast, no extra deps
  fallback_to_mean: true
max_cells: 250
```

## Kriging with uncertainty

Adds `mean_temp_krig_std` / `total_rain_krig_std` columns and (with `uncertainty_samples > 0`) `score_ci_low` / `score_ci_high` columns.

```yaml
raster_path: "examples/sample_data/soil.tif"
climate_csv: "examples/sample_data/climate.csv"
output_dir: "outputs"
roi:
  type: bbox
  xmin: -120.5
  ymin: 34.0
  xmax: -118.0
  ymax: 35.5
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
  uncertainty_samples: 500   # Monte Carlo draws for score CI
climate:
  strategy: spatial
  interpolation_method: kriging
  variogram_mode: standard
  fallback_to_mean: true
max_cells: 250
```

Set `variogram_mode: extended` when you want TerraFlow to try additional nested variogram candidates before selecting the best kriging model. Extended mode is more expensive than standard kriging because each nested candidate fits a custom variogram before LOOCV; prefer standard mode for large station networks unless nested structures are specifically needed.

## IDW (fast, no uncertainty)

```yaml
raster_path: "examples/sample_data/soil.tif"
climate_csv: "examples/sample_data/climate.csv"
output_dir: "outputs"
roi:
  type: bbox
  xmin: -120.5
  ymin: 34.0
  xmax: -118.0
  ymax: 35.5
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
climate:
  strategy: spatial
  interpolation_method: idw
  fallback_to_mean: true
max_cells: 250
```

See [Climate Configuration](schema.md#climate-configuration) for full field reference.

