---
title: GeoAI Engine API
description: API reference for terraflow.geoai_engine — optional fields, landcover, and canopy runners.
icon: material/satellite-variant
tags:
  - API
  - Reference
  - GeoAI
---

# terraflow.geoai_engine

Thin adapter that wraps [`opengeos/geoai`](https://github.com/opengeos/geoai)
behind three CLI-callable runners. Requires the optional `[geoai]` extra:

```bash
pip install "terraflow-agro[geoai]"
```

The runners share a single private orchestrator (`_run`) which validates the
config, computes a deterministic `geoai_fingerprint`, skips inference on
cache hit, and writes `geoai_manifest.json` + `report.json` for every run.

See the [GeoAI guide](../geoai.md) and
[ADR-007](../architecture/adr-007-geoai-engine.md) for the user-facing and
design-rationale views.

## Public surface

- `run_fields(config_path)` — field-boundary detection (FTW-v1).
- `run_landcover(config_path)` — landcover classification.
- `run_canopy(config_path)` — canopy-height regression.
- `_GEOAI_AVAILABLE` — `True` when `geoai-py` and `torch` are importable; tests
  monkey-patch this to mock-out heavy ML deps.

## API Reference

::: terraflow.geoai_engine
