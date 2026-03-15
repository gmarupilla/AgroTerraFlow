# Demo Data

`demo_climate.csv` is a minimal tabular climate file included in the repository for
demonstration purposes.

`usda_cdl.tif` is a sample crop from the USDA National Agricultural Statistics
Service Cropland Data Layer (CDL). It is **not stored in git** due to its size.

## Obtaining the demo raster

**Option 1 — Zenodo archive (recommended):**

```bash
curl -L https://doi.org/10.5281/zenodo.18490119 -o usda_cdl.tif
```

**Option 2 — Download via CropScape:**

Visit [https://nassgeodata.gmu.edu/CropScape/](https://nassgeodata.gmu.edu/CropScape/)
and export a GeoTIFF clipped to the demo ROI (lon -101 to -94, lat 38 to 40).

Once placed in this directory, run the demo:

```bash
terraflow --config examples/demo_config.yml
```
