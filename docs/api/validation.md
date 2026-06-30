---
title: Validation API
description: API reference for terraflow.validation — spatial-block cross-validation.
icon: material/check-decagram
tags:
  - API
  - Reference
---

# terraflow.validation

Spatial-block cross-validation (Roberts et al. 2017) on the suitability label grid. Invoked from the CLI as `terraflow validate -c config.yml`; results are appended to `report.json` under the `validation` key. For spatial-autocorrelation diagnostics on score residuals, call `esda.Moran` directly on `features.parquet`; for inter-rater agreement against a reference label set, call `sklearn.metrics.cohen_kappa_score`.

## API Reference

::: terraflow.validation
