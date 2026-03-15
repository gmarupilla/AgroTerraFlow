# Demo Data

## demo_climate.csv

Minimal synthetic climate file included in the repository.
Contains latitude, longitude, mean temperature, and total rainfall observations
for a small region in western Kansas.

## usda_cdl.tif (not included in git — generate or download below)

The demo raster is derived from the **USDA National Agricultural Statistics
Service (NASS) Cropland Data Layer (CDL)** program — a publicly available
annual raster of crop-specific land cover for the contiguous United States.

**Data source (official government release):**
> USDA National Agricultural Statistics Service.
> *Cropland Data Layer.* Published crop-specific data layer.
> Available at: <https://www.nass.usda.gov/Research_and_Science/Cropland/Release/>
> Interactive portal (CropScape): <https://nassgeodata.gmu.edu/CropScape/>

This dataset is in the public domain (U.S. government work, 17 U.S.C. § 105).

---

### Option 1 — Generate synthetic demo raster (works offline)

```bash
make get-demo-data
```

Creates a CDL-compatible synthetic GeoTIFF (EPSG:5070, uint8, 30 m,
western Kansas extent) using seeded random CDL crop codes.
Sufficient for running all demos and tests.

### Option 2 — Download real USDA CDL data from CropScape

1. Go to <https://nassgeodata.gmu.edu/CropScape/>
2. Draw or enter the bounding box: lon −101 to −94, lat 38 to 40
3. In the download dialog, select the **CDL** tab
4. Choose year (e.g. 2023), projection: **Degrees Lat/Lon WGS84** or
   **USA Contiguous Albers Equal Area Conic USGS** (both supported)
5. Click Submit → download the `.tif` → save as `data/usda_cdl.tif`

Using real CDL data is recommended for any analysis beyond the quickstart demo.

---

### Citation

When using real CDL data in published work, cite as:

> USDA National Agricultural Statistics Service (2023).
> *Cropland Data Layer.* Accessed via CropScape.
> <https://nassgeodata.gmu.edu/CropScape/>

This citation corresponds to `@usda_cdl` in `paper/biblio.bib`.
