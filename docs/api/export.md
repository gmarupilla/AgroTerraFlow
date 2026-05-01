---
title: Export API
description: API reference for terraflow.export — H3-indexed output for downstream interop.
icon: material/hexagon-multiple
tags:
  - API
  - Reference
---

# terraflow.export

Re-indexes pipeline output to H3 hexagonal cells for interop with DeckGL, Kepler.gl, and h3pandas. The `h3-py` dependency is optional — install with `pip install terraflow-agro[h3]`.

## Public surface

- `to_h3(features, resolution=8)` — convert a `features` DataFrame to an H3-indexed structure.
- `run_export(config, ...)` — orchestrator used by `terraflow export --format h3`.

## API Reference

::: terraflow.export
