---
title: Geo API
description: API reference for terraflow.geo — ROI clipping, CRS reprojection, and pixel-window helpers.
icon: material/earth
tags:
  - API
  - Reference
---

# terraflow.geo

The geo module owns ROI clipping and CRS alignment. The pipeline invariant is **all output coordinates are EPSG:4326** — `geo.py` reprojects any input that differs.

## Overview

- ROI bounds in any CRS are reprojected to the raster CRS (all four corners, then axis-aligned bounding box) before windowing.
- ROI clipping snaps requested bounds to an intersecting pixel window so very small ROIs avoid oversized raster reads.
- Degenerate windows (NaN dimensions after reprojection) raise `ValueError` with diagnostic context.

## API Reference

::: terraflow.geo
