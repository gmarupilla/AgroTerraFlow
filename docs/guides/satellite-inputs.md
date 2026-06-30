# Satellite inputs — Sentinel-2, Landsat, HLS → TerraFlow

TerraFlow's vegetation-index input (`raster_path`) is *any* single-band GeoTIFF.
This guide shows how to get from a real satellite acquisition to a config-ready
raster, using free public sources.

The three lowest-friction paths are:

| Source | Resolution | Revisit | Best for |
|---|---|---|---|
| **Sentinel-2 L2A** | 10 m | 5 days | Field-scale vegetation, cropland monitoring |
| **Landsat 8/9 L2** | 30 m | 16 days | Long historical record (1984+), thermal bands |
| **HLS v2.0** (Harmonized Landsat-Sentinel) | 30 m | 2-4 days | Combined cadence; cross-calibrated by NASA |

All three deliver Cloud-Optimized GeoTIFFs (COGs) by default. TerraFlow reads
them with `rasterio` so they drop in unchanged.

## 1. Pick a vegetation index

The classic choice for crop suitability is NDVI:

```
NDVI = (NIR - RED) / (NIR + RED)
```

Bands by sensor:

| Sensor | RED | NIR |
|---|---|---|
| Sentinel-2 | B04 (665 nm) | B08 (842 nm) |
| Landsat 8/9 | SR_B4 | SR_B5 |
| HLS S30 | B04 | B8A |
| HLS L30 | B04 | B05 |

For drought-leaning analyses use NDWI or NDMI; the band mapping is sensor-
specific but the workflow below is identical.

## 2. Download with STAC (cleanest)

The Microsoft Planetary Computer hosts all three datasets as public STAC
collections. Install the optional dependencies once:

```bash
pip install pystac-client planetary-computer rioxarray
```

Then for a Sentinel-2 NDVI mosaic over your ROI:

```python
import planetary_computer as pc
import pystac_client, rioxarray as rxr, numpy as np

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=pc.sign_inplace,
)
items = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[-101, 38, -94, 40],          # western Kansas demo ROI
    datetime="2025-06-01/2025-08-31",  # peak-season window
    query={"eo:cloud_cover": {"lt": 20}},
).item_collection()

# Median composite to suppress residual cloud / shadow.
nir = rxr.open_rasterio(items[0].assets["B08"].href, masked=True).squeeze()
red = rxr.open_rasterio(items[0].assets["B04"].href, masked=True).squeeze()
ndvi = ((nir - red) / (nir + red)).astype("float32")
ndvi.rio.to_raster("ndvi_s2_2025.tif", compress="deflate")
```

The output is a single-band float32 GeoTIFF. TerraFlow handles the reprojection
to EPSG:4326 internally — but for very large rasters it's faster to reproject
upstream:

```python
ndvi.rio.reproject("EPSG:4326").rio.to_raster("ndvi_wgs84.tif")
```

## 3. Wire into a TerraFlow config

```yaml
raster_path: "ndvi_wgs84.tif"
climate_csv:  "stations.csv"      # see climate setup below
output_dir:   "outputs/s2_run"

roi:
  type: bbox
  xmin: -101.0
  ymin:  38.0
  xmax:  -94.0
  ymax:  40.0

model_params:
  v_min: -0.2       # NDVI range — adjust for your sensor / season
  v_max:  0.9
  t_min:  0.0
  t_max: 40.0
  r_min:  0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
```

The key knob is `model_params.v_min/v_max` — these clip the NDVI scale. If you
forget to set them for the sensor's actual range, scores collapse to a narrow
band.

## 4. Climate inputs alongside satellite

For the historical single-period path, the `climate_csv` is a flat per-station
average (`lat, lon, mean_temp, total_rain`). For the climate-impact path
(`temporal_aggregations` + `scenarios`), the `timeseries_csv` is long-format
daily station data — see [Migration v0.4 → v0.5](../migration-v0.4-to-v0.5.md).

CMIP6-derived bias-corrected daily output drops into the same long-format CSV
shape; the `[cmip6]` extra adds NetCDF ingestion (`terraflow.cmip6`).

## Reproducibility checklist

- [ ] Save the STAC item ID alongside the raster (commit it in the config
      directory or in a `README.md` next to the TIF).
- [ ] Use a fixed compositing window (`datetime="2025-06-01/2025-08-31"`),
      not "last 90 days" — otherwise the run fingerprint is misleading.
- [ ] Reproject to EPSG:4326 before running TerraFlow to keep the run
      fingerprint stable across hosts (different rasterio + GDAL builds
      produce subtly different reprojected pixels).
- [ ] Pin `rasterio` / `rioxarray` / `pystac-client` versions in the
      environment that produced the input — they're not TerraFlow
      dependencies but they shape the data the run fingerprint covers.

## See also

- `docs/notebooks/07_climate_impact_crop_suitability.ipynb` — end-to-end demo.
- `docs/quickstart.md` — config + first run in 10 minutes.
- `docs/architecture/run-identity.md` — what the run fingerprint covers
  and what it doesn't.
