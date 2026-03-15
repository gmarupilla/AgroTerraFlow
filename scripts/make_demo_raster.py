"""
Generate a synthetic demo raster for TerraFlow's quickstart example.

The raster mimics the structure of a USDA Cropland Data Layer (CDL) clip:
  - Geographic extent: lon -101 to -94, lat 38 to 40 (western Kansas)
  - CRS: EPSG:4326 (WGS 84)
  - Pixel size: ~30 m at this latitude (~0.00027 degrees)
  - Values: integers 1–255 (CDL crop classification codes), nodata = 0
  - Single band, uint8

For real USDA CDL data, see data/README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "usda_cdl.tif"

# Demo ROI: western Kansas — matches examples/demo_config.yml
XMIN, YMIN, XMAX, YMAX = -101.0, 38.0, -94.0, 40.0

# ~300 m pixel (10× CDL native resolution) — sufficient for demo purposes
PIXEL_DEG = 0.00269494585236

WIDTH = int(round((XMAX - XMIN) / PIXEL_DEG))
HEIGHT = int(round((YMAX - YMIN) / PIXEL_DEG))

# Common CDL crop codes for Kansas: corn=1, soybeans=5, winter_wheat=24,
# sorghum=4, fallow=61, grass/pasture=176, developed=121, water=83
CDL_CODES = np.array([1, 4, 5, 24, 61, 121, 176], dtype=np.uint8)

rng = np.random.default_rng(seed=42)

# Spatial blocks give a more realistic CDL appearance than pure noise.
block_h, block_w = HEIGHT // 40, WIDTH // 40
blocks = rng.integers(0, len(CDL_CODES), size=(block_h, block_w), dtype=np.uint8)
data = CDL_CODES[
    np.repeat(np.repeat(blocks, HEIGHT // block_h, axis=0), WIDTH // block_w, axis=1)
]
# Trim/pad to exact dimensions
data = data[:HEIGHT, :WIDTH]

# Scatter ~3 % nodata (value 0) to simulate masked cells
nodata_mask = rng.random(data.shape) < 0.03
data[nodata_mask] = 0

transform = from_bounds(XMIN, YMIN, XMAX, YMAX, WIDTH, HEIGHT)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(
    OUTPUT,
    "w",
    driver="GTiff",
    height=HEIGHT,
    width=WIDTH,
    count=1,
    dtype=np.uint8,
    crs=CRS.from_epsg(4326),
    transform=transform,
    nodata=0,
    compress="lzw",
) as dst:
    dst.write(data, 1)

print(f"Created {OUTPUT}  ({WIDTH}×{HEIGHT} px, {OUTPUT.stat().st_size // 1024} KB)")
sys.exit(0)
