"""
Generate a synthetic demo raster for TerraFlow's quickstart example.

The raster mimics the structure of a USDA Cropland Data Layer (CDL) clip:
  - CRS: EPSG:5070 (USA Contiguous Albers Equal Area Conic — CDL native)
  - Pixel size: 1000 m (coarse demo resolution — real CDL is 30 m)
  - Extent: full demo_config.yml ROI (western Kansas, lon -101..-94, lat 38..40)
  - Values: integers 1–255 (CDL crop classification codes), nodata = 0
  - Single band, uint8, LZW-compressed

The synthetic raster is 609×234 px (~60 KB), coarse but big enough across
the full ROI to exercise kriging, sensitivity, and spatial validation.

For real USDA CDL data, see data/README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "usda_cdl.tif"

# Albers (EPSG:5070) extent covering the full demo_config.yml ROI
# (~western Kansas: lon -101..-94, lat 38..40 in WGS84).
# Using 1000 m pixels — coarser than real CDL (30 m) but enough for a
# reproducible demo that exercises spatial interpolation, sensitivity
# analysis, and spatial block cross-validation across the full ROI.
WEST_X = -434706.0  # left edge in Albers metres
NORTH_Y = 1898106.0  # top edge in Albers metres
PIXEL_M = 1000.0    # 1 km — coarse demo resolution (vs 30 m for real CDL)
WIDTH = 609
HEIGHT = 234

# CDL crop codes present in the 2025 western Kansas clip:
# corn=1, sorghum=4, soybeans=5, winter_wheat=24, fallow=61,
# developed_open=121, developed_low=122, grass_pasture=176, shrubland=152
CDL_CODES = np.array([1, 4, 5, 24, 61, 121, 122, 152, 176], dtype=np.uint8)

rng = np.random.default_rng(seed=42)

# Spatial blocks give a more realistic CDL appearance than pure noise.
block_size = 20
blocks = rng.integers(0, len(CDL_CODES), size=(HEIGHT // block_size, WIDTH // block_size), dtype=np.uint8)
data = CDL_CODES[
    np.repeat(np.repeat(blocks, block_size, axis=0), block_size, axis=1)
]
data = data[:HEIGHT, :WIDTH]

# Scatter ~3 % nodata (value 0) to simulate masked/boundary cells
data[rng.random(data.shape) < 0.03] = 0

transform = from_origin(WEST_X, NORTH_Y, PIXEL_M, PIXEL_M)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(
    OUTPUT,
    "w",
    driver="GTiff",
    height=HEIGHT,
    width=WIDTH,
    count=1,
    dtype=np.uint8,
    crs=CRS.from_epsg(5070),
    transform=transform,
    nodata=0,
    compress="lzw",
) as dst:
    dst.write(data, 1)

print(f"Created {OUTPUT}  ({WIDTH}×{HEIGHT} px, {OUTPUT.stat().st_size // 1024} KB)")
sys.exit(0)
