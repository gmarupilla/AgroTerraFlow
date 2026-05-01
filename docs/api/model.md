---
title: Model API
description: API reference for terraflow.model — suitability scoring and label assignment.
icon: material/calculator-variant
tags:
  - API
  - Reference
---

# terraflow.model

Suitability scoring is a normalized weighted composite of vegetation index, mean temperature, and total rainfall. Scores in `[0, 1]` are mapped to ordinal labels.

## Public functions

- `suitability_score(v, t, r, params)` — single-cell scalar score.
- `suitability_score_array(v, t, r, params)` — vectorised NumPy version used by the pipeline.
- `suitability_label(score)` — score → ordinal class.

## API Reference

::: terraflow.model
