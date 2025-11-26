---
title: "TerraFlow: A Reproducible Workflow for Geospatial Agricultural Modeling"
tags:
  - Python
  - geospatial
  - agriculture
  - reproducibility
  - workflow
authors:
  - name: Gnaneswara Marupilla
    orcid: 0000-0002-6030-8707
    affiliation: 1
affiliations:
  - name: Your Institution or Company
    index: 1
date: 2025-11-25
bibliography: paper.bib
---

# Summary

TerraFlow is an open-source Python library for building reproducible geospatial
workflows in agricultural modeling. It provides a configurable pipeline that
combines raster datasets (for example, public land cover products such as the
USDA Cropland Data Layer) with tabular climate information to produce simple,
interpretable suitability scores and derived outputs such as maps and
summaries.

Rather than implement a single, domain-specific crop or yield model, TerraFlow
focuses on the *infrastructure* that many projects need but frequently
re-implement in an ad hoc way: configuration, data ingestion, geospatial
subsetting, feature computation, and basic visualization. By packaging these
steps into a small, testable library with clear separation of concerns,
TerraFlow makes it easier for researchers and engineers to share end-to-end
workflows that can be executed consistently across machines, environments, and
teams.

Because it is built on widely adopted open-source components (`rasterio`,
`pandas`, `pydantic`, `plotly`), TerraFlow can serve both as a lightweight
reference implementation for geospatial agricultural workflows and as a
teaching and onboarding tool for new practitioners.

# Statement of need

Agricultural and environmental modeling efforts routinely face the same
practical challenges: downloading and managing public geospatial layers,
subsetting them to a region of interest, combining them with climate or
management data, and computing indices or risk scores that can inform
decisions. In many academic and applied projects, these tasks are implemented
as one-off scripts with tightly coupled dependencies, limited validation, and
little documentation, which makes the resulting analyses difficult to
reproduce, review, or extend.

This is particularly important in agriculture, where geospatial analyses are
used to support decisions related to crop planning, resource allocation, and
risk management at regional to national scales. Reproducible workflows built on
public data products are a natural foundation for transparent, evidence-based
decision support.

TerraFlow addresses this need by providing:

- A small but complete reference pipeline built on widely used open-source
  geospatial and data-analysis libraries.
- A declarative, validated configuration model for inputs, regions of interest,
  and model parameters, using `pydantic`.
- Clear separation between data ingestion, geospatial operations, model logic,
  and visualization, encouraging modular design.
- Automated tests and linting that demonstrate how research software can adopt
  modern engineering practices without requiring a large codebase.

The target users are researchers, data scientists, and engineers who work with
raster and tabular data in agricultural or environmental contexts and who need
a minimal, understandable starting point for reproducible geospatial analysis.
The same structure also makes TerraFlow suitable as a pedagogical example in
courses on geospatial data science or scientific software engineering.

# Software description

## Implementation

TerraFlow is implemented in Python 3.10+ and organized as a standard library
package (`terraflow`) with the following main modules:

- `config`: Pydantic-based models for validating pipeline configuration,
  including input paths, region of interest, and model parameters.
- `ingest`: utilities for loading raster datasets (e.g., GeoTIFF) and climate
  CSV tables.
- `geo`: a thin layer over `rasterio` that will support clipping and
  subsetting rasters to a user-defined region of interest.
- `model`: a simple, transparent suitability model that combines normalized
  vegetation, temperature, and rainfall features into a scalar score and a
  qualitative label.
- `pipeline`: orchestration code that wires together configuration, ingestion,
  geospatial processing, and modeling, and writes tabular outputs to disk.
- `viz`: helper functions built on `plotly` for generating interactive maps
  from pipeline outputs.

A small command-line interface is provided via:

```bash
terraflow --config examples/demo_config.yml

which runs the configured pipeline and writes results to the specified output
directory.

## Example usage

The repository includes an example configuration file that demonstrates how to
run TerraFlow on real public-domain data. The example uses a subset of the USDA
Cropland Data Layer as the raster input and a small synthetic climate table as
the tabular input. Running the pipeline produces:

A CSV file with per-cell suitability scores and qualitative labels.

An interactive HTML map that visualizes the scores over the region of
interest.

The example is intentionally simple and is designed to be replaced with other
raster and tabular datasets. In this way, TerraFlow functions as a template or
scaffold that projects can adapt to their own modeling logic while retaining
the same reproducible structure.

## Acknowledgements

The design of TerraFlow is inspired by best practices in reproducible
computational modeling and prior work in scientific workflow and simulation
tools. The author thanks the maintainers of the open-source geospatial
ecosystem for making robust building blocks such as rasterio and plotly
available, as well as the providers of public geospatial datasets, including
the USDA National Agricultural Statistics Service.

## References
<!-- Add references in paper.bib and cite them here, for example: @misc{usda_cdl, title = {Cropland Data Layer}, author = {{USDA National Agricultural Statistics Service}}, year = {2023}, url = {https://nassgeodata.gmu.edu/CropScape/} } -->
