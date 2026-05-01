---
title: Validation API
description: API reference for terraflow.validation — spatial block CV, Cohen's kappa, and Moran's I.
icon: material/check-decagram
tags:
  - API
  - Reference
---

# terraflow.validation

Spatial block cross-validation (Roberts et al. 2017), Cohen's kappa against an optional reference CSV, and Moran's I on score residuals. Invoked from the CLI as `terraflow validate -c config.yml`; results are appended to `report.json` under the `validation` key.

## API Reference

::: terraflow.validation
