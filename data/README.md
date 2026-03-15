# Demo Data

## demo_climate.csv

Minimal synthetic climate file included in the repository.
Contains latitude, longitude, mean temperature, and total rainfall observations
for a small region in western Kansas.

## usda_cdl.tif (not included — download below)

The demo raster is a clipped GeoTIFF from the **USDA National Agricultural
Statistics Service (NASS) Cropland Data Layer (CDL)**, a publicly available
annual raster of crop-specific land cover for the contiguous United States.

**Data source (official government release):**
> USDA National Agricultural Statistics Service.
> *Cropland Data Layer.* Published crop-specific data layer.
> Available at: <https://www.nass.usda.gov/Research_and_Science/Cropland/Release/>
> Accessed via CropScape: <https://nassgeodata.gmu.edu/CropScape/>

This dataset is in the public domain (U.S. government work, 17 U.S.C. § 105).

### Download

```bash
make get-demo-data
```

This downloads a ~1.5 MB clip covering the demo ROI
(lon −101 to −94, lat 38 to 40 — western Kansas, EPSG:4326)
from the USDA CropScape WCS service.

Alternatively, download manually from CropScape:
1. Go to <https://nassgeodata.gmu.edu/CropScape/>
2. Select year 2023, draw/enter the bounding box above
3. Export as GeoTIFF → save as `data/usda_cdl.tif`

### Citation

This dataset is cited in the TerraFlow paper as:

> USDA National Agricultural Statistics Service (2023).
> *Cropland Data Layer.* Accessed via CropScape.
> <https://nassgeodata.gmu.edu/CropScape/>
