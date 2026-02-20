---
title: Core API
description: API reference for terraflow.config, terraflow.pipeline, and terraflow.model — configuration schema, pipeline orchestration, and suitability scoring.
icon: material/cog
tags:
  - API
  - Reference
---

# terraflow.core

The core modules define the configuration schema and the end-to-end pipeline.

## Quick Start

```python
from terraflow.pipeline import main
from terraflow.config import load_config

# Load and validate configuration
config = load_config("config.yml")

# Run the complete pipeline
main("config.yml")
```

!!! tip "Module Organization"
    - **config**: YAML schema validation and Pydantic models
    - **pipeline**: End-to-end orchestration and artifact generation
    - **model**: Suitability scoring algorithms and label assignment

## API Reference

::: terraflow.config

::: terraflow.pipeline

::: terraflow.model
