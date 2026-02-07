# Configuration Schema

TerraFlow v0.2+ uses a single YAML configuration file that maps to the `PipelineConfig` model.
It is validated with Pydantic and rejects unknown fields.

## Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `raster_path` | string | Path to the input raster (GeoTIFF). |
| `climate_csv` | string | Path to the climate CSV (must have `lat`, `lon`, and climate variable columns). |
| `output_dir` | string | Directory to write run outputs. |
| `roi` | object | Region of interest definition (bbox only in v0.1). |
| `model_params` | object | Parameters for suitability scoring. |
| `climate` | object | Climate data handling configuration (optional, defaults to spatial interpolation). |
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

## Climate configuration (v0.2+)

Climate data is now applied per-cell using configurable interpolation strategies.

```yaml
# Option 1: Spatial interpolation (default, recommended for point data)
climate:
  strategy: spatial
  fallback_to_mean: true

# Option 2: Index-based matching (for pre-aligned data)
climate:
  strategy: index
  cell_id_column: null  # optional: column name for explicit cell ID matching
  fallback_to_mean: true
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
