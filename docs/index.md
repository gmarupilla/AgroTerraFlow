---
title: TerraFlow
description: Reproducible geospatial modeling for agricultural suitability analysis — config-driven, fingerprinted, and spatially aware.
icon: material/sprout
---

# TerraFlow

Reproducible geospatial tool for agricultural suitability modeling. Give it a land-cover map, climate data, and a config file — it hands you a scored, location-stamped results table.

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

## v0.2.0 highlights

<div class="grid" markdown>

:material-thermometer: **Per-cell climate values**
:   Spatial interpolation via `scipy.griddata` — not a single global mean.

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
