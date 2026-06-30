---
title: CMIP6 API
description: API reference for terraflow.cmip6 — CMIP6 NetCDF scenario ingest behind the optional [cmip6] extra.
icon: material/database-outline
tags:
  - API
  - Reference
---

# terraflow.cmip6

CMIP6 NetCDF scenario ingest behind the optional `[cmip6]` install extra.
The module opens climate scenario NetCDFs (typically daily `tas` or `pr`
cubes), samples them at station coordinates, and returns the long-format
station time-series that the `terraflow.temporal` aggregation engine
consumes.

## Install

```bash
pip install "terraflow-agro[cmip6]"
```

This installs `xarray>=2024.1` and `netcdf4>=1.7`. They are imported lazily
inside each callable so users on the historical CSV path never pay the
import cost.

## Overview

- `cmip6_metadata(path)` — SHA-256 + size + CMIP6 global attrs
  (variant_label, source_id, experiment_id, institution_id, table_id).
  Exposed as a public helper so callers can fold NetCDF provenance into
  their own manifest. The main `terraflow run` pipeline does **not** yet
  ingest NetCDFs directly — users today convert each NetCDF to a long-format
  station CSV via `cmip6_to_station_timeseries(...)` and the CSV's
  SHA-256 enters the run fingerprint via the existing
  `_collect_input_paths` path. First-class `climate.cmip6_scenarios:`
  config support (per-NetCDF SHA-256 + unit conversion + calendar handling
  inside the pipeline) ships in v0.6.0 — see
  [issue #148](https://github.com/gmarupilla/AgroTerraFlow/issues/148).
- `load_cmip6_scenario(path, variable, period)` — opens a NetCDF lazily
  and slices the time axis by an inclusive `(year_min, year_max)` window.
  Handles non-Gregorian calendars (`365_day`, `noleap`, `360_day`) via the
  calendar-aware `dt.year` path.
- `extract_station_timeseries(da, stations, output_variable)` — vectorised
  nearest-neighbour selection at station coordinates. Returns a DataFrame
  in the shape `(station_id, lat, lon, date, <output_variable>)`.
- `cmip6_to_station_timeseries(path, stations, ...)` — one-call wrapper
  around the previous two.

Tolerates both `lat`/`lon` and `latitude`/`longitude` coord names commonly
seen across CMIP6 sources.

## Quick example

```python
import pandas as pd
from terraflow.cmip6 import cmip6_to_station_timeseries

stations = pd.DataFrame({
    "station_id": ["KS01", "KS02", "KS03"],
    "lat":        [38.5,   39.0,   39.5],
    "lon":        [-100.5, -100.0, -99.5],
})

ts = cmip6_to_station_timeseries(
    "data/cmip6/tas_day_MPI-ESM1-2-HR_historical_19910101-20201231.nc",
    stations,
    period=(1991, 2020),
    output_variable="temperature_c",
)
```

## API Reference

::: terraflow.cmip6
