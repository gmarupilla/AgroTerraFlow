---
title: TerraFlow
description: Reproducible climate-impact assessment of agricultural suitability — config-driven, fingerprinted, uncertainty-aware.
icon: material/sprout
---

# TerraFlow

A reproducible framework for **climate-impact assessment of agricultural suitability** — including climate-induced crop hazards (drought, flood, heat stress, growing-degree-day shifts) under historical and projected future climate. Give it a land-cover map, a climate dataset, and a config file — it returns a scored, location-stamped results table with per-cell uncertainty intervals and a content-addressable run fingerprint that lets reviewers regenerate the exact same numbers three years later.

The same workflow methodology extends to habitat suitability, land-use planning, and conservation siting.

---

## Choose your path

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **TerraFlow in 10 Minutes**
    { .card-green }

    ---

    New to TerraFlow? Start here — no coding required. Covers what it does, the problem it solves, how the pipeline works, and what the output means.

    [:octicons-arrow-right-24: Get started](quickstart.md)

-   :material-map-marker-outline:{ .lg .middle } **Field Guide**
    { .card-blue }

    ---

    You receive results but don't run TerraFlow yourself. Plain-English guide to scores, labels, opening results in Excel or QGIS, and sharing with others.

    [:octicons-arrow-right-24: Read the Field Guide](field-guide.md)

-   :material-cog:{ .lg .middle } **Technical Reference**
    { .card-purple }

    ---

    You install, configure, or contribute to TerraFlow. CLI, YAML schema, architecture docs, ADRs, and API reference.

    [:octicons-arrow-right-24: CLI Usage](cli/usage.md) · [:octicons-arrow-right-24: Config Schema](config/schema.md)

</div>

---

## What's available

<div class="grid" markdown>

:material-thermometer: **Per-cell climate values**
:   Spatial interpolation via linear, kriging, or IDW — not a single global mean.

:material-chart-bell-curve: **Kriging + uncertainty**
:   `interpolation_method: kriging` adds per-cell `{var}_krig_std` columns. Pair with `uncertainty_samples` for Monte Carlo score confidence intervals.

:material-earth: **CRS-aware ROI clipping**
:   Supply your bounding box in WGS 84 degrees regardless of the raster's native projection.

:material-map: **Guaranteed WGS 84 output**
:   `lat`/`lon` columns always contain geographic degrees, safe for any mapping tool.

:material-fingerprint: **Reproducible sampling**
:   Cell selection is seeded from the run fingerprint — same config always yields the same rows.

:material-file-move: **Portable configs**
:   Relative paths resolve against the config file's location, not the caller's working directory.

</div>

---

## Technical documentation

**Start running:**

- [CLI Usage](cli/usage.md) — how to call `terraflow` from the command line
- [Configuration Schema](config/schema.md) — every YAML field documented, including `roi_crs`
- [Configuration Examples](config/examples.md) — ready-to-use config templates

**Understand the system:**

- [Architecture Overview](architecture/overview.md) — module boundaries and data flow
- [Run Identity & Fingerprinting](architecture/run-identity.md) — how reproducibility is guaranteed
- [Output Artifact Contract](architecture/artifacts.md) — what files are written and their schemas
- [Architecture Decisions (ADRs)](architecture/adr-001-band-selection.md) — why key design choices were made

**Contribute:**

- [Development Guide](DEVELOPMENT.md) — environment setup, testing, coverage
- [Contributing Guidelines](contributing.md) — PR process, code standards
- [Roadmap](ROADMAP.md) — what's planned next

**API reference:**

- [Climate module](api/climate.md) · [Core module](api/core.md) · [Ingest module](api/ingest.md)
