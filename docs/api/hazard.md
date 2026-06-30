---
title: Hazard API
description: API reference for terraflow.hazard — GDD, frost days, heat-stress days, and simplified SPEI implementations.
icon: material/alert-octagon-outline
tags:
  - API
  - Reference
---

# terraflow.hazard

WMO/ETCCDI-aligned hazard indicators introduced in v0.5.0 (#138d).
Backs four of the `TemporalAggregation.kind` values that
`terraflow.temporal.aggregate_per_station` dispatches to.

## Overview

- `growing_degree_days(df, base_temp_c)` — per-station **cumulative**
  sum of `max(0, T_d - base)` across every row in the
  (scenario-filtered) DataFrame. Note: this is a window-cumulative total,
  not a per-year average — a 30-year scenario window yields ~30× the
  value of a 1-year window. Divide by `(year_max - year_min + 1)` if you
  need an annualised GDD.
- `frost_days(df, threshold_c)` — per-station **cumulative** count of
  days where `T ≤ threshold` across every row in the (scenario-filtered)
  DataFrame. Maps to WMO ETCCDI **FD0** when threshold = 0 °C, but note
  the WMO definition is per-year — TerraFlow's implementation returns the
  window total. Divide by the window's year count for the canonical
  annual FD0.
- `heat_stress_days(df, threshold_c)` — per-station **cumulative** count
  of days where `T ≥ threshold` across every row in the (scenario-filtered)
  DataFrame. Maps to WMO ETCCDI **TX35** when threshold = 35 °C; same
  per-year vs window-total caveat as `frost_days` above.
- `spei(df, timescale_months)` — simplified Thornthwaite-PET-based
  Standardised Precipitation-Evapotranspiration Index at the final month
  of the input window.

## SPEI simplifications

Documented honestly so a user can decide whether the simplification is
acceptable for their analysis:

| Aspect | Canonical SPEI (R package) | TerraFlow `spei()` |
|---|---|---|
| Standardisation | Log-logistic CDF fit | **Z-score** |
| Daylight-hour correction | Latitude-dependent in PET | **Omitted** |
| Heat-index reference | Multi-decade climatology | **Per-station fit on input window** |

For relative scenario comparisons (e.g. "is SSP5-8.5 drier than
historical?") these simplifications are typically acceptable. For
absolute SPEI claims against published thresholds (e.g. "moderate
drought" at SPEI < -1) prefer the canonical R package via reticulate or
a pre-computed SPEI column passed through `precip_percentile` as a
substitute.

## Quick example

```python
import pandas as pd
from terraflow.hazard import growing_degree_days, frost_days, heat_stress_days, spei

df = pd.read_csv("data/demo_timeseries.csv", parse_dates=["date"])

gdd = growing_degree_days(df, base_temp_c=10.0)
fd  = frost_days(df,        threshold_c=0.0)
ts  = heat_stress_days(df,  threshold_c=35.0)
spei3 = spei(df, timescale_months=3)
```

## API Reference

::: terraflow.hazard
