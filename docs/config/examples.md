# Configuration Examples

Below is a complete example configuration aligned with v0.1 expectations.

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
max_cells: 250
```

### Tips

- Keep file paths local for v0.1 (no remote URIs).
- Adjust `max_cells` if you need to limit output size.
- Use consistent units across raster and climate inputs.
