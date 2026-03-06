# tests/data — Synthetic Test Fixtures

**Provenance:** All files in this directory are **synthetically generated** —
they do not contain real satellite imagery, real climate observations, or any
personally identifiable information.

**License:** MIT (same as the TerraFlow project).  These files may be freely
used for testing, continuous integration, and reproducibility validation.

## Contents

| File / pattern | Description |
|---|---|
| *(generated at runtime by pytest fixtures in `conftest.py`)* | Tiny 5×5 GeoTIFF rasters and 3-row climate CSVs are written to `tmp_path` by the `synthetic_raster` and `synthetic_climate_csv` fixtures.  No binary blobs are committed. |

## Design intent

* Fixtures are created programmatically in `conftest.py` using `rasterio`
  and `pandas`, keeping the repository free of large binary files.
* The synthetic raster is a 5×5 grid centred on −100 °lon / 40 °lat
  (EPSG:4326) with pixel values 0–24 and no nodata mask.
* The synthetic climate CSV has three rows with `lat`, `lon`, `mean_temp`,
  and `total_rain` columns that fall within the raster extent.
* These fixtures are deterministic given the same pytest `tmp_path`, making
  golden-value tests stable across platforms.
