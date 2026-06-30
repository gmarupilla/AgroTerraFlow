# Migrating from v0.4.x to v0.5.0

v0.5.0 reshapes TerraFlow around its **climate-impact-on-agriculture** flagship.
Two thin wrappers were removed (GeoAI, H3 export) and a much bigger feature
landed (scenario × rule fan-out with CMIP6 NetCDF support). This page lists
every change a v0.4.x user needs to action.

## TL;DR

| You used | Do this on v0.5.0 |
|---|---|
| `terraflow geoai fields/landcover/canopy` | Module removed — call [`geoai-py`](https://github.com/opengeos/geoai) directly |
| `terraflow export --format h3` | Module removed — call [`h3-py`](https://github.com/uber/h3-py) on `features.parquet` |
| `terraflow validate` returning Cohen's κ / Moran's I | Narrowed to spatial-block CV — call `sklearn.metrics.cohen_kappa_score` / `esda.Moran` directly |
| `[geoai]` or `[h3]` install extras | Extras removed — drop them from `pip install "terraflow-agro[…]"` |
| Nothing climate-impact-related | No action needed — the historical pipeline is fully backward-compatible |

## Removed: GeoAI engine (PR #134)

The `terraflow.geoai_engine` module + `terraflow geoai {fields,landcover,canopy}`
sub-app, `GeoAIConfig` Pydantic block, and the `[geoai]` install extra are gone.
The bodies were `NotImplementedError` stubs and downstream users cited `geoai-py`,
not TerraFlow.

**Replacement.** Call `geoai-py` directly:

```python
import geoai
geoai.field_boundaries.delineate(raster_path="my_field.tif", output="fields.gpkg")
```

If field/landcover/canopy inference is core to your workflow, a separate
`terraflow-geoai` package is planned post-JOSS (issue #134).

## Removed: H3 export (PR #135)

The `terraflow.export` module (`to_h3`, `run_export`), the `terraflow export --format h3`
CLI subcommand, the `ExportConfig` Pydantic block, and the `[h3]` extra are gone.

**Replacement.** Five lines on `features.parquet`:

```python
import h3, pandas as pd
df = pd.read_parquet("outputs/runs/abc.../features.parquet")
df["h3"] = [h3.latlng_to_cell(lat, lon, 8) for lat, lon in zip(df.lat, df.lon)]
agg = df.groupby("h3").score.mean().reset_index()
agg.to_parquet("h3_resolution_8.parquet")
```

## Narrowed: `terraflow validate` (PR #136)

The validation block in `report.json` no longer carries `cohen_kappa`,
`morans_i_residuals`, `reference_dataset`, or `n_reference_points`.
`ValidationConfig.reference_csv` is removed. Spatial-block cross-validation
remains the canonical TerraFlow validation surface.

**Replacement.** Both diagnostics are one library call away:

```python
from sklearn.metrics import cohen_kappa_score
kappa = cohen_kappa_score(reference["label"], predicted["label"])

import esda, libpysal
w = libpysal.weights.KNN.from_dataframe(features_gdf, k=8)
mi = esda.Moran(features_gdf.score, w)
print(mi.I, mi.p_norm)
```

Reason: both wrappers failed the Methods-section citation test — downstream
papers cited `sklearn` / `esda`, not TerraFlow. Keeping them earned no
citations and added maintenance burden (issue #136).

## New: climate-impact pipeline (PR series #138a-#138f)

The flagship feature. Add **two** blocks to your YAML config:

```yaml
climate:
  # ... existing fields ...
  timeseries_csv: data/demo_timeseries.csv     # NEW required input
  temporal_aggregations:                       # NEW: per-station rules
    - kind: annual_mean
    - kind: growing_degree_days
      base_temp_c: 10.0
    - kind: frost_days
      threshold_c: 0.0
    - kind: heat_stress_days
      threshold_c: 35.0
    - kind: precip_percentile
      percentile: 95.0
    - kind: spei
      timescale_months: 3
  scenarios:                                   # NEW: time windows
    - { name: historical, period: [1991, 2020] }
    - { name: ssp245,     period: [2041, 2070] }
    - { name: ssp585,     period: [2041, 2070] }
```

The `timeseries_csv` is long-format daily station data with columns
`station_id, lat, lon, date, temperature_c, precipitation_mm`. CMIP6 NetCDF
inputs are supported via the optional `[cmip6]` extra:

```bash
pip install "terraflow-agro[cmip6]"
```

Then use `terraflow.cmip6.cmip6_to_station_timeseries(...)` to convert a
NetCDF to the long-format CSV shape.

**Outputs.** Existing `features.parquet` is unchanged. A new sibling artifact
`climate_features.parquet` lands in the same run directory with one column
per `<rule>__<scenario>` pair (cell-indexed; merge on `cell_id`).

**Demo.** End-to-end example at
[`examples/demo_config_climate_impact.yml`](https://github.com/gmarupilla/AgroTerraFlow/blob/main/examples/demo_config_climate_impact.yml)
and the executed notebook
[`07_climate_impact_crop_suitability`](notebooks/07_climate_impact_crop_suitability.ipynb).

## Other notes

- `make get-demo-data` now also generates `data/demo_timeseries.csv`
  (gitignored; 197k rows / ~7 MB) so the climate-impact demo runs offline.
- Package structure is unchanged in v0.5.0. A planned restructure into
  `terraflow.io.*` + `terraflow.climate.*` sub-packages ships in v0.6.0
  (tracker issue #148).
