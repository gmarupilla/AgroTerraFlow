# Configuration Schema

TerraFlow v0.1 uses a single YAML configuration file that maps to the `PipelineConfig` model.
It is validated with Pydantic and rejects unknown fields.

## Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `raster_path` | string | Path to the input raster (GeoTIFF). |
| `climate_csv` | string | Path to the climate CSV. |
| `output_dir` | string | Directory to write run outputs. |
| `roi` | object | Region of interest definition (bbox only in v0.1). |
| `model_params` | object | Parameters for suitability scoring. |
| `max_cells` | integer | Maximum cells sampled from the ROI (default: 500). |

## ROI (bbox)

```yaml
roi:
  type: bbox
  xmin: -120.5
  ymin: 34.0
  xmax: -118.0
  ymax: 35.5
```

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

All fields are required unless otherwise noted.
