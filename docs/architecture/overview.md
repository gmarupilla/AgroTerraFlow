# Architecture Overview

TerraFlow v0.1 is intentionally simple: it ingests local geospatial datasets, runs a deterministic suitability
pipeline, and writes outputs to a structured run directory. The core focus is **reproducibility** rather
than an exhaustive modeling toolkit.

## High-level flow

1. **Ingest** local raster and climate CSV inputs.
2. **Clip** raster data to the requested region of interest.
3. **Aggregate** climate metrics for the run.
4. **Score** each sampled cell and create a results table.
5. **Persist** outputs under a run-specific directory.

## Design principles

- **Deterministic runs:** the same inputs and configuration yield the same run fingerprint and outputs.
- **Clear boundaries:** ingestion and core modeling are separate modules with minimal coupling.
- **Local-first:** v0.1 only loads datasets from local files (no remote fetches).
- **Traceable artifacts:** run outputs have a defined, inspectable contract.

For boundary details and run identity rules, see the following pages.
