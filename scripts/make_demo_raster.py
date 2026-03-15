"""
Generate a synthetic demo raster for TerraFlow's quickstart example.

The raster mimics the structure of a USDA Cropland Data Layer (CDL) clip:
  - CRS: EPSG:5070 (USA Contiguous Albers Equal Area Conic — CDL native)
  - Pixel size: 30 m (CDL native resolution)
  - Approximate extent: western Kansas (same region as demo_config.yml ROI)
  - Values: integers 1–255 (CDL crop classification codes), nodata = 0
  - Single band, uint8, LZW-compressed

The synthetic raster is ~800×800 px (~600 KB), matching the size of a real
CropScape clip over this region.

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

# Approximate Albers (EPSG:5070) origin for western Kansas
# (matches the ~bbox from a real CropScape download of the demo ROI)
WEST_X = 86925.0   # left edge in Albers metres
NORTH_Y = 1774455.0  # top edge in Albers metres
PIXEL_M = 30.0     # 30 m — CDL native resolution
WIDTH = 779
HEIGHT = 779

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
