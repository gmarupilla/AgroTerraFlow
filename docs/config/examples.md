# Configuration Examples

Below is a complete example configuration aligned with v0.2.0 with spatial climate interpolation.

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
  strategy: spatial        # Spatial interpolation (default)
  fallback_to_mean: true
max_cells: 250
```

### Tips

- Keep file paths local (relative or absolute paths supported).
- Climate CSV must have `lat` and `lon` columns for spatial interpolation.
- Adjust `max_cells` if you need to limit output size.
- Use consistent units across raster and climate inputs.
- See [Climate Configuration](schema.md#climate-configuration-v020--new-feature) for strategy options.
