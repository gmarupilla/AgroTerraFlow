---
title: "TerraFlow: A Reproducible, Uncertainty-Aware Geospatial Workflow for Agricultural Suitability Modelling and Foundation-Model Inference"
tags:
  - Python
  - geospatial
  - agriculture
  - kriging
  - sensitivity analysis
  - reproducibility
  - geoai
  - foundation models
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
date: 8 June 2026
bibliography: biblio.bib
repository-code: 'https://github.com/gmarupilla/AgroTerraFlow'
url: 'https://terraflow.marupilla.dev'
---

# Summary

TerraFlow is an open-source Python library that turns a raster (e.g. a
land-cover GeoTIFF), a table of weather-station observations, and a YAML
configuration into a scored per-cell suitability table with complete,
machine-readable provenance. A single `terraflow run` clips the raster
to a region of interest, reprojects it to WGS84, spatially interpolates
station climate to cell centroids (linear, inverse-distance, or Ordinary
Kriging with automatic variogram selection), computes a normalised
weighted suitability score, and writes `features.parquet`,
`manifest.json`, and `report.json` to a content-addressable run
directory. Three companion sub-commands extend the same contract:
`terraflow sensitivity` and `terraflow validate` produce Sobol' and
Morris indices [@herman2017salib; @saltelli2008global] and spatial-block
cross-validation with Cohen's κ and Moran's I, and the optional
`terraflow geoai` sub-app exposes pretrained field-boundary, landcover,
and canopy-height models from the `geoai` foundation-model library
[@wu2026geoai] as fingerprinted, cache-aware inference runners. Every
analysis — climate interpolation, scoring, sensitivity, validation, and
foundation-model inference — shares a single deterministic
fingerprint, so identical inputs always produce the same directory name
and bit-identical outputs within documented limits.

![TerraFlow architecture showing configuration, pipeline orchestration, ingestion, geospatial operations, modelling, and outputs.](figure1.jpeg){ width=85% }

# Statement of need

Agricultural and environmental suitability mapping increasingly composes
two distinct toolchains: classical raster + climate-station workflows
(e.g. the USDA Cropland Data Layer [@usda_cdl] combined with point
weather observations) and pretrained foundation-model inference for
field-boundary delineation, landcover classification, and canopy-height
regression. The two are usually stitched together in ad-hoc notebooks
that re-implement ROI clipping, CRS alignment, station-to-cell
interpolation, nodata accounting, inference orchestration, and export
on every project. The consequence is a workflow-level reproducibility
gap: results depend on file paths, package versions, random seeds, and
— for ML inference — accelerator devices and torch versions that drift
silently between runs; interpolation uncertainty and parameter
sensitivity are rarely quantified; reviewers cannot regenerate a
specific figure from a specific configuration and specific input bytes;
and the climate-modelling and deep-learning halves of a single study
operate under incompatible notions of "the same run".

TerraFlow closes this gap with a single configuration-driven pipeline
that fingerprints every run from the canonicalised YAML config plus
SHA-256 content hashes of every input; supports Ordinary Kriging with
leave-one-out variogram selection and propagates per-cell kriging
standard deviation into Monte-Carlo confidence intervals; ships
sensitivity analysis and spatial-block validation as first-class
subcommands whose outputs share the run directory; and wraps the
`geoai` library [@wu2026geoai] under `terraflow geoai
{fields,landcover,canopy}` so foundation-model inference participates
in the same fingerprint, manifest, and cache-hit semantics as the
climate pipeline.

# State of the field

Several tools cover parts of this pipeline but none cover it end-to-end
with provenance, uncertainty, and pretrained-model inference as
first-class concerns. `rasterstats` [@rasterstats] computes zonal
statistics from raster-vector pairs but offers neither CRS
normalisation nor climate interpolation nor provenance. `rioxarray` /
`xarray` [@rioxarray; @hoyer2017xarray] provide N-dimensional raster
operations but leave pipeline assembly to the user. Google Earth
Engine [@gorelick2017gee] enables planetary-scale analysis but requires
internet access and a Google account, ruling it out for the air-gapped
environments common in government and agricultural workflows. `QGIS`
[@qgis] is interactive, not scripted. `rasterio` [@gillies2013rasterio]
and `pandas` [@mckinney2010pandas] are indispensable building blocks
without a top-level orchestration contract.

The `geoai` library [@wu2026geoai] provides a uniform Python API to
pretrained field-boundary, landcover, and canopy-height models, but —
by design — leaves run identity, configuration validation,
output-directory conventions, and cache invalidation to the caller.
Wrapping `geoai` inference in ad-hoc scripts with no link back to
climate-modelling provenance defeats end-to-end reproducibility.

We built TerraFlow rather than contributing to these libraries because
reproducibility, uncertainty propagation, and the integration of
classical interpolation with foundation-model inference are
architectural concerns that span ingest, clipping, interpolation,
scoring, ML inference, and export, and cannot be bolted onto a
statistics, tiling, or model-zoo library without a top-level
orchestration contract.

# Software design

TerraFlow is organised into modules with strict contracts
[@wilson2017good].

**Core pipeline.** `config` validates the YAML configuration with
Pydantic [@pydantic] before any I/O runs. `ingest` builds a
`DataCatalog` — an immutable metadata snapshot of each layer's CRS,
bounds, nodata value, shape, and SHA-256 — without reading pixel
arrays, separating availability checks from computation. `geo`
performs windowed ROI clipping and CRS reprojection via `pyproj`.
`climate` implements three spatial-interpolation strategies; the
kriging path uses `pykrige` and selects among spherical, exponential,
Gaussian, and optionally nested variogram candidates
[@cressie1993spatial] by leave-one-out cross-validation RMSE.
`model` computes the normalised weighted suitability score. `pipeline`
seeds `numpy.random.default_rng` from the SHA-256 of the run
fingerprint, samples up to `max_cells` valid cells, and writes
artifacts atomically. `sensitivity` and `validation` consume the same
`DataCatalog`, so every analysis is pinned to the exact inputs
recorded in the manifest. Two design choices matter most: artifacts
are schema-versioned (the pipeline invalidates a cached run on stale
`terraflow_schema_version`), and the `run_fingerprint` excludes file
mtimes and absolute paths so the same content hashes produce the same
fingerprint across machines and filesystem copies.

**GeoAI engine adapter.** `geoai_engine` wraps the `geoai` library
[@wu2026geoai] behind three orchestrators — `run_fields`,
`run_landcover`, `run_canopy` — exposed as the `terraflow geoai`
sub-app. Each runner validates the `geoai:` config block against a
Pydantic schema (engine name, power-of-two chip size ≥ 32, confidence
threshold in [0, 1], positive batch size), then computes a
`geoai_fingerprint` over the canonicalised config, sorted input
SHA-256 hashes, and a `model_metadata` payload covering the model
name, weights SHA-256, `geoai` library `major.minor`, the detected
device (`cpu`/`cuda`/`mps`), and the installed `torch` `major.minor`.
Because device and torch minor version participate in the hash, the
same configuration on a different accelerator yields a different
cache directory — surfacing what would otherwise be silent output
drift in foundation-model inference. `torch.manual_seed` is set
deterministically from the fingerprint, and the runner skips
inference on a manifest cache hit. Outputs land at
`<output_dir>/runs/<geoai_fingerprint>/geoai/`. The library is an
opt-in extra (`pip install "terraflow-agro[geoai]"`); the default
install remains lightweight.

![TerraFlow pipeline: configuration is canonicalised, input files are hashed, and outputs land under a content-addressable run directory.](figure2.jpeg){ width=85% }

# Research impact statement

TerraFlow addresses a workflow-level reproducibility gap in
agricultural and environmental geospatial modelling: the gap between
*input* fingerprinting (which several existing tools already provide)
and *workflow* fingerprinting that covers the climate-interpolation
strategy, score-model parameters, sensitivity-analysis settings,
spatial-validation reference set, and — critically — the
foundation-model device and library version. This gap matters most
where audit-quality reproduction is part of the deliverable:
precision-agriculture decision support, food-security and climate
adaptation planning, and agronomy education where students must
reproduce a published result before extending it.

The contract is enforced by a substantial validation surface:
**289 automated tests** across the climate, sensitivity, validation,
export, and GeoAI modules; an **85 % coverage floor** (current 87 %);
a type-checked CI matrix on Python 3.10–3.12; and a Dockerfile whose
smoke test runs the demo with `docker run --network none` and asserts
that `features.parquet`, `manifest.json`, and `report.json` land under
the mounted output directory **without any network access**. The
fingerprint contract is documented byte-by-byte on a dedicated
reproducibility page, including the GeoAI device-and-torch-minor
extension and known sources of non-determinism (`scipy` variogram-fit
drift across versions, `qhull` triangulation tie-breaking,
BLAS-dependent summation order).

To make these guarantees concrete, we report the metrics produced by
a single end-to-end run of the bundled demo on `examples/demo_config.yml`.
The demo ROI spans ~608 km × 233 km of western Kansas; a 20-station
synthetic climate network is interpolated to 2 000 sampled raster
cells:

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

Every number above is reproducible from `make get-demo-data &&
terraflow run -c examples/demo_config.yml` plus the two companion
subcommands; the published `run_fingerprint` is verifiable without
shared compute infrastructure. The GeoAI engine ships with the same
contract, backed by a 12-test mocked-engine suite that patches the
heavy ML dependencies so the cache-hit and fingerprint-sensitivity
invariants hold without requiring `torch` on the default CI runners.

To the authors' knowledge TerraFlow is the only open package that
composes Ordinary Kriging with LOOCV variogram selection,
Monte-Carlo uncertainty propagation, Sobol' and Morris sensitivity
analysis, spatial-block cross-validation, and pretrained
foundation-model inference under a single deterministic provenance
contract. The integration — not any one component — is the contribution.

# AI usage disclosure

The authors used Anthropic Claude — specifically the Claude Code
assistant invoking the `claude-opus-4-7` model for v0.4.0 GeoAI and
paper revisions, and earlier Claude Sonnet 4.x / Opus 4.x for the
v0.2.x – v0.3.0 climate-pipeline work — as a coding assistant during
software implementation, documentation, and manuscript drafting. The
OpenAI Codex GitHub App (`gpt-codex` model) provided automated
pull-request feedback. Every AI-suggested change was reviewed and
edited by the human authors before being committed. Core design
decisions — the `DataCatalog` boundary contract, the run-fingerprint
hashing scheme, LOOCV variogram selection, Monte-Carlo uncertainty
propagation, the artifact schema, and the GeoAI device/torch-minor
fingerprint contract — were made by the human authors. AI-assisted
code is verified by the project's 289 automated tests on the
Python 3.10/3.11/3.12 CI matrix, the 85 % coverage floor, SonarCloud
static analysis, and GitHub Dependency Review on every pull request.

# Acknowledgements

TerraFlow builds on the scientific Python ecosystem including
`rasterio` [@gillies2013rasterio], `pandas` [@mckinney2010pandas],
`pykrige`, SALib [@herman2017salib], scikit-learn, Pydantic
[@pydantic], Shapely [@shapely], `rasterstats` [@rasterstats],
Apache Arrow [@pyarrow], and — for the optional GeoAI engine — the
`geoai` library [@wu2026geoai] and `torch`. Sample raster data
originates from the USDA National Agricultural Statistics Service
Cropland Data Layer [@usda_cdl], which is in the public domain
(17 U.S.C. § 105).

# References
