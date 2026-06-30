---
title: Temporal API
description: API reference for terraflow.temporal — multi-temporal climate aggregation engine driving the scenario × hazard fan-out.
icon: material/calendar-clock-outline
tags:
  - API
  - Reference
---

# terraflow.temporal

Multi-temporal climate aggregation engine introduced in v0.5.0 (#138b).
Computes per-station aggregations of a long-format daily climate
time-series and fans them out across configured scenarios. The output
is the cell-input that `terraflow.climate_impact` interpolates to the
suitability grid.

## Overview

- `filter_scenario(df, scenario)` — slice a long-format station
  time-series to a `Scenario.period` year window.
- `aggregate_per_station(df, rule)` — dispatch a `TemporalAggregation`
  to its kind-specific implementation. Returns one scalar per station.
- `compute_per_station_aggregations(df, rules, scenarios)` — outer
  product. Returns a DataFrame indexed by `station_id` with columns
  `<rule_label>__<scenario_name>` (one per rule × scenario pair).

Supported `kind` values (declared on `ClimateConfig.temporal_aggregations`):

| kind | Required fields | Notes |
|---|---|---|
| `annual_mean` | — | Long-run mean of `temperature_c`. |
| `seasonal_mean` | `months: [1..12]` | Mean over selected calendar months. |
| `growing_degree_days` | `base_temp_c: float` | Sum of `max(0, T - base)` per year, mean over window. Implementation in `terraflow.hazard`. |
| `frost_days` | `threshold_c: float` | Count of days at-or-below threshold. WMO ETCCDI FD0 when threshold = 0. |
| `heat_stress_days` | `threshold_c: float` | Count of days at-or-above threshold. WMO ETCCDI TX35 when threshold = 35. |
| `precip_percentile` | `percentile: 0..100` | Nth percentile of daily precipitation. |
| `spei` | `timescale_months: int > 0` | Simplified Thornthwaite SPEI at the final month of the input window. Implementation in `terraflow.hazard`. |

Stations with no rows after a scenario filter resolve to `NaN` so downstream
kriging LOOCV sees missing values cleanly rather than silently dropping
stations.

## Quick example

```python
import pandas as pd
from terraflow.temporal import compute_per_station_aggregations
from terraflow.config import TemporalAggregation, Scenario

df = pd.read_csv("data/demo_timeseries.csv", parse_dates=["date"])
rules = [
    TemporalAggregation(kind="annual_mean"),
    TemporalAggregation(kind="growing_degree_days", base_temp_c=10.0),
]
scenarios = [
    Scenario(name="historical", period=[1991, 2020]),
    Scenario(name="ssp245",     period=[2041, 2070]),
]
panel = compute_per_station_aggregations(df, rules, scenarios)
panel.head()
#         annual_mean__historical  annual_mean__ssp245  ...
# KS01                       12.4                15.1
```

## API Reference

::: terraflow.temporal
