---
title: TerraFlow
description: Reproducible geospatial modeling for agricultural suitability analysis — config-driven, fingerprinted, and spatially aware.
icon: material/sprout
---

# TerraFlow Documentation

TerraFlow is a reproducible geospatial tool for agricultural suitability modeling — it takes a land-cover map, climate data, and a configuration file, and produces a scored, location-stamped results table.

**Choose your starting point:**

---

## I want to understand what this is (10 min)

> New to TerraFlow? Start here — no coding required.

**[→ TerraFlow in 10 Minutes](quickstart.md)**

Covers: what TerraFlow does, the problem it solves, how the pipeline works, a live demo, and what the output means.

---

## I work with the results (land manager, consultant, extension agent)

> You receive results from TerraFlow but don't run it yourself.

**[→ Field Guide — Understanding TerraFlow Results](field-guide.md)**

Covers: what each output column means, how to read scores and labels, how to open results in Excel or a mapping tool, common questions, and how to share results with others.

---

## I run or develop TerraFlow (technical user, contributor)

> You install TerraFlow, configure it, or contribute to the codebase.

**Start running:**
- [CLI Usage](cli/usage.md) — how to call `terraflow` from the command line
- [Configuration Schema](config/schema.md) — every YAML field documented, including `roi_crs`
- [Configuration Examples](config/examples.md) — ready-to-use config templates

**Understand the system:**
- [Architecture Overview](architecture/overview.md) — module boundaries and data flow
- [Run Identity & Fingerprinting](architecture/run-identity.md) — how reproducibility is guaranteed
- [Output Artifact Contract](architecture/artifacts.md) — what files are written and their schemas
- [Architecture Decisions (ADRs)](architecture/) — why key design choices were made

**Contribute:**
- [Development Guide](DEVELOPMENT.md) — environment setup, testing, coverage
- [Contributing Guidelines](contributing.md) — PR process, code standards
- [Roadmap](ROADMAP.md) — what's planned next

**API reference:**
- [Climate module](api/climate.md)
- [Core module](api/core.md)
- [Ingest module](api/ingest.md)

---

## v0.2.0 highlights

- **Per-cell climate values** — spatial interpolation using `scipy.griddata` (not a single global mean)
- **CRS-aware ROI clipping** — supply your bounding box in WGS84 degrees regardless of the raster's native projection
- **Guaranteed WGS84 output** — `lat`/`lon` columns always contain geographic degrees
- **Reproducible sampling** — cell selection is seeded from the run fingerprint; same config = same rows
- **Portable configs** — relative paths resolve against the config file's location, not the caller's working directory
