---
title: "TerraFlow: A Reproducible, Uncertainty-Aware Geospatial Workflow for Agricultural Suitability Modelling"
tags:
  - Python
  - geospatial
  - agriculture
  - kriging
  - sensitivity analysis
  - reproducibility
authors:
  - name: Gnaneswara Marupilla
    orcid: 0000-0002-6030-8707
    corresponding: true
    affiliation: '1'
  - name: Chandhini Bayina
    orcid: 0009-0002-1359-1762
    affiliation: '2'
affiliations:
  - index: 1
    name: Independent Researcher & Software Engineer (Scientific Computing)
  - index: 2
    name: University of Central Missouri, Missouri, United States
date: 23 April 2026
bibliography: biblio.bib
repository-code: 'https://github.com/gmarupilla/AgroTerraFlow'
url: 'https://terraflow.marupilla.dev'
repository-artifact: 'https://doi.org/10.5281/zenodo.18490119'
identifiers:
  - type: doi
    value: 10.5281/zenodo.18490119
    description: Zenodo archive (pre-JOSS publication)
---

# Summary

TerraFlow is an open-source Python library that turns a raster (e.g. a
land-cover GeoTIFF), a table of weather-station observations, and a YAML
configuration into a scored per-cell suitability table with complete,
machine-readable provenance.  A single `terraflow run` invocation clips
the raster to a user-specified region of interest, reprojects it to
WGS84, spatially interpolates station climate to cell centroids (linear,
inverse-distance, or Ordinary Kriging with automatic variogram
selection), computes a normalised weighted suitability score, and
writes three guaranteed artifacts — `features.parquet`, `manifest.json`,
`report.json` — to a content-addressable run directory.  Two companion
sub-commands, `terraflow sensitivity` and `terraflow validate`, produce
Sobol' and Morris indices [@herman2017salib; @saltelli2008global] and
spatial block cross-validation with Cohen's kappa and Moran's I on the
same run.  Identical inputs always produce the same `run_fingerprint`,
making results independently verifiable.

![TerraFlow architecture showing configuration, pipeline orchestration, ingestion, geospatial operations, modelling, and outputs.](figure1.jpeg){ width=85% }

# Statement of need

Scientists building agricultural or environmental suitability maps
routinely stitch together a raster product (e.g. the USDA Cropland
Data Layer [@usda_cdl]), point climate observations, and a scoring
model.  The stitching is typically done as a collection of
notebooks and ad-hoc scripts, each of which re-implements ROI clipping,
CRS alignment, station-to-cell interpolation, nodata accounting, and
result export.  Three failures recur: (i) results are not reproducible
because file paths, package versions, or random seeds drift silently
between runs; (ii) interpolation uncertainty and model-parameter
sensitivity are rarely quantified, so downstream claims rest on a
single unvalidated score; and (iii) reviewers and collaborators have
no reliable way to regenerate a specific figure from a specific
configuration and specific input bytes.

TerraFlow addresses all three by providing a single configuration-driven
pipeline that: (a) fingerprints every run from the canonicalised YAML
config plus SHA-256 content hashes of each input and writes an atomic
`manifest.json`; (b) supports Ordinary Kriging with leave-one-out
cross-validation-based variogram selection and propagates per-cell
kriging standard deviation into Monte-Carlo confidence intervals on the
final score; and (c) ships global sensitivity analysis and spatial
block validation as first-class subcommands whose outputs live in the
same run directory as the primary artifacts.  The intended audience is
agricultural data scientists, agronomy and ecology researchers, and
graduate students who need a transparent, low-friction starting point
without building a reproducibility and uncertainty stack from scratch.

# State of the field

Several tools cover parts of this pipeline but none cover it end-to-end
with provenance and uncertainty as first-class concerns.
`rasterstats` [@rasterstats] computes zonal statistics from
raster–vector pairs but does not handle CRS normalisation, climate
interpolation, or provenance.  `rioxarray` / `xarray`
[@rioxarray; @hoyer2017xarray] provide powerful N-dimensional raster
operations but leave pipeline assembly and provenance to the user.
Google Earth Engine [@gorelick2017gee] enables planetary-scale
analysis but requires internet access and a Google account and cannot
be used in air-gapped environments common in government and
agricultural workflows.  `QGIS` [@qgis] supplies an interactive GUI
but is not designed for scripted, batch-reproducible runs.
`rasterio` [@gillies2013rasterio] and `pandas` [@mckinney2010pandas]
are indispensable lower-level building blocks but do not offer a
pipeline, provenance layer, or uncertainty quantification.
We built TerraFlow rather than contributing to these libraries because
reproducibility and uncertainty propagation are architectural concerns
that span every stage — ingest, clipping, interpolation, scoring,
export — and cannot be bolted onto a statistics or tiling library
without a top-level orchestration contract.

# Software design

TerraFlow is organised into nine modules with strict contracts
[@wilson2017good].  `config` validates the YAML configuration with
Pydantic [@pydantic] before any I/O runs.  `ingest` builds a
`DataCatalog` — an immutable metadata snapshot of each layer's CRS,
bounds, nodata value, shape, and SHA-256 — without reading pixel
arrays, separating availability checks from computation.  `geo`
handles windowed ROI clipping and CRS reprojection via `pyproj`.
`climate` implements three spatial-interpolation strategies; the
kriging path uses `pykrige` and selects among spherical, exponential,
Gaussian, and optionally nested variogram candidates [@cressie1993spatial]
by leave-one-out cross-validation RMSE on the first climate variable.
`model` computes the normalised weighted suitability score.  `pipeline`
orchestrates the end-to-end flow, derives a `numpy.random.default_rng`
seed from the SHA-256 of the run fingerprint, samples up to
`max_cells` valid cells, and writes the artifacts atomically.
`sensitivity` and `validation` are optional stages consuming the same
DataCatalog, so every analysis is pinned to the exact inputs recorded
in the manifest.  Two design decisions matter most for research use:
every artifact is schema-versioned (the pipeline invalidates a cached
run when `features.parquet` carries a stale `terraflow_schema_version`),
and the `run_fingerprint` deliberately excludes file mtimes and
absolute paths so the same content hashes produce the same fingerprint
across machines and filesystem copies.

![TerraFlow pipeline: configuration is canonicalised, input files are hashed, and outputs land under a content-addressable run directory.](figure2.jpeg){ width=85% }

# Research impact statement

TerraFlow is a new release (v0.3.0) aimed at the near-term
reproducibility needs of agricultural researchers.  Concrete
community-readiness signals are in place: 231 automated tests across
15 test files, an enforced 85 % coverage floor, type-checked Python
3.10–3.12 on CI, a public PyPI package (`terraflow-agro`), a Homebrew
tap for macOS, and a Dockerfile whose smoke test runs the full demo
pipeline with `--network none` and verifies that `features.parquet`,
`manifest.json`, and `report.json` are produced offline.  The
documentation site publishes a reproducibility page enumerating what
the run fingerprint covers and the known sources of non-determinism.

To make the reproducibility guarantees concrete, we report the
metrics produced by a single end-to-end run of the bundled demo
(`terraflow run`, `sensitivity`, and `validate` on
`examples/demo_config.yml`).  The demo ROI spans ~608 km × 233 km
of western Kansas; the 20-station synthetic climate network is
interpolated to 2 000 sampled raster cells:

| Stage | Metric | Value |
|-------|--------|-------|
| Pipeline | Sampled cells / valid cells in ROI | 2 000 / 137 592 (97 % coverage) |
| Pipeline | Total wall-clock runtime | 0.35 s |
| Kriging  | Selected variogram model | spherical |
| Kriging  | LOOCV RMSE, `mean_temp` | 0.29 °C |
| Kriging  | LOOCV RMSE, `total_rain` | 7.01 mm |
| Monte-Carlo | 90 % score CI mean width | 0.073 (n = 200 draws) |
| Sobol' | S1 indices (`w_v`, `w_t`, `w_r`) | 0.331, 0.333, 0.333 |
| Sobol' | ST indices (`w_v`, `w_t`, `w_r`) | 0.333, 0.333, 0.333 |
| Block CV | Mean fold accuracy (5 folds) | 0.48 |
| Kappa | Cohen's κ against reference CSV | −0.05 |
| Spatial | Moran's I on score residuals | 0.19 |

The kriging LOOCV RMSE on `mean_temp` is small relative to the 16.8–22.0 °C
inter-station range, confirming that the selected spherical variogram
captures the synthetic climate gradient.  The balanced Sobol' indices
are the expected result of weights constrained to sum to one over
variables with comparable normalised dynamic range; they demonstrate
the full sensitivity-analysis pipeline rather than a scientific claim
about the demo data.  The near-zero Cohen's κ is likewise expected —
the demo raster is randomised crop codes and the reference labels are
independent — and its purpose here is to show that the validation
stage emits the metric, not that the demo model predicts reality.  A
reviewer can reproduce every number in the table by running
`make get-demo-data && terraflow run -c examples/demo_config.yml` and
the two companion subcommands, and can verify the published
`run_fingerprint` matches without needing any shared compute
infrastructure.  We expect adoption among graduate courses and
agronomy research groups that currently maintain ad-hoc scripted
pipelines; usage metrics (PyPI downloads, GitHub stars, citation
graph via Zenodo DOI 10.5281/zenodo.18490119) will be reported in
future releases.

# AI usage disclosure

The authors used Anthropic Claude as a coding assistant during
implementation of the kriging, sensitivity, validation, and export
modules, and during the drafting of this manuscript.  All
AI-assisted suggestions were reviewed, edited, and validated by the
human authors before being committed or included.  Core design
decisions — the DataCatalog boundary contract, the run-fingerprint
hashing scheme, the choice of LOOCV-based variogram selection, the
Monte-Carlo uncertainty propagation model, and the artifact schema —
were made by the human authors.  All AI-assisted code is covered by
the project's 233 automated tests and continuous-integration quality
gates.

# Acknowledgements

TerraFlow builds on the scientific Python ecosystem including
`rasterio` [@gillies2013rasterio], `pandas` [@mckinney2010pandas],
`pykrige`, SALib [@herman2017salib], scikit-learn, Pydantic
[@pydantic], Shapely [@shapely], `rasterstats` [@rasterstats], and
Apache Arrow [@pyarrow].  Sample raster data originates from the USDA
National Agricultural Statistics Service Cropland Data Layer
[@usda_cdl], which is in the public domain (17 U.S.C. § 105).

# References
