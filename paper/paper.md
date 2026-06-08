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
machine-readable provenance. A single `terraflow run` invocation clips
the raster to a user-specified region of interest, reprojects it to
WGS84, spatially interpolates station climate to cell centroids (linear,
inverse-distance, or Ordinary Kriging with automatic variogram
selection), computes a normalised weighted suitability score, and
writes three guaranteed artifacts — `features.parquet`, `manifest.json`,
`report.json` — to a content-addressable run directory. Three companion
sub-commands extend the same contract: `terraflow sensitivity` and
`terraflow validate` produce Sobol' and Morris indices
[@herman2017salib; @saltelli2008global] and spatial-block cross-validation
with Cohen's κ and Moran's I, while the optional `terraflow geoai`
sub-app exposes pretrained field-boundary, landcover, and canopy-height
models from the `geoai` foundation-model library [@wu2026geoai] as
fingerprinted, cache-aware inference runners. Every analysis — climate
interpolation, scoring, sensitivity, validation, GeoAI inference —
shares a single `run_fingerprint` (or `geoai_fingerprint`), so identical
inputs always produce the same directory name and bit-identical outputs
within documented limits, making results independently verifiable.

![TerraFlow architecture showing configuration, pipeline orchestration, ingestion, geospatial operations, modelling, and outputs.](figure1.jpeg){ width=85% }

# Statement of need

Scientists building agricultural or environmental suitability maps
routinely stitch together a raster product (e.g. the USDA Cropland
Data Layer [@usda_cdl]), point climate observations, a scoring model,
and — increasingly — outputs from pretrained remote-sensing models for
field-boundary delineation, landcover classification, or canopy-height
regression. The stitching is typically done as a collection of
notebooks and ad-hoc scripts, each of which re-implements ROI clipping,
CRS alignment, station-to-cell interpolation, nodata accounting,
inference orchestration, and result export. Four failures recur:
(i) results are not reproducible because file paths, package
versions, random seeds, or — for ML inference — accelerator devices
and torch versions drift silently between runs;
(ii) interpolation uncertainty and model-parameter sensitivity are
rarely quantified, so downstream claims rest on a single unvalidated
score;
(iii) reviewers and collaborators have no reliable way to regenerate
a specific figure from a specific configuration and specific input
bytes; and
(iv) the climate-modelling side and the deep-learning side of an
agricultural workflow live in separate scripts with separate
provenance conventions, so a single end-to-end study can include
several incompatible notions of "the same run".

TerraFlow addresses all four by providing a single configuration-driven
pipeline that: (a) fingerprints every run from the canonicalised YAML
config plus SHA-256 content hashes of each input and writes an atomic
`manifest.json`; (b) supports Ordinary Kriging with leave-one-out
cross-validation-based variogram selection and propagates per-cell
kriging standard deviation into Monte-Carlo confidence intervals on
the final score; (c) ships global sensitivity analysis and spatial
block validation as first-class subcommands whose outputs live in the
same run directory as the primary artifacts; and (d) exposes the
`geoai` library [@wu2026geoai] through `terraflow geoai
{fields,landcover,canopy}` so foundation-model inference participates
in the same fingerprint, manifest, and cache-hit semantics used by the
climate pipeline. The intended audience is agricultural data
scientists, agronomy and ecology researchers, and graduate students
who need a transparent, low-friction starting point without building
a reproducibility, uncertainty, and inference stack from scratch.

# State of the field

Several tools cover parts of this pipeline but none cover it end-to-end
with provenance, uncertainty, and pretrained-model inference as
first-class concerns.

`rasterstats` [@rasterstats] computes zonal statistics from
raster–vector pairs but does not handle CRS normalisation, climate
interpolation, or provenance. `rioxarray` / `xarray`
[@rioxarray; @hoyer2017xarray] provide powerful N-dimensional raster
operations but leave pipeline assembly and provenance to the user.
Google Earth Engine [@gorelick2017gee] enables planetary-scale
analysis but requires internet access and a Google account and cannot
be used in air-gapped environments common in government and
agricultural workflows. `QGIS` [@qgis] supplies an interactive GUI
but is not designed for scripted, batch-reproducible runs. `rasterio`
[@gillies2013rasterio] and `pandas` [@mckinney2010pandas] are
indispensable lower-level building blocks but do not offer a pipeline,
provenance layer, or uncertainty quantification.

On the GeoAI side, the `geoai` library [@wu2026geoai] provides a
uniform Python API to pretrained field-boundary, landcover, and
canopy-height models, but — by design — leaves run identity,
configuration validation, output-directory conventions, and cache
invalidation to the caller. Practitioners therefore wrap `geoai`
inference in ad-hoc scripts with no link back to the climate-modelling
provenance, defeating end-to-end reproducibility.

We built TerraFlow rather than contributing to these libraries because
reproducibility, uncertainty propagation, and the integration of
classical interpolation with foundation-model inference are
architectural concerns that span every stage — ingest, clipping,
interpolation, scoring, ML inference, export — and cannot be bolted
onto a statistics, tiling, or model-zoo library without a top-level
orchestration contract.

# Software design

TerraFlow is organised into modules with strict contracts
[@wilson2017good].

**Core pipeline.** `config` validates the YAML configuration with
Pydantic [@pydantic] before any I/O runs. `ingest` builds a
`DataCatalog` — an immutable metadata snapshot of each layer's CRS,
bounds, nodata value, shape, and SHA-256 — without reading pixel
arrays, separating availability checks from computation. `geo`
handles windowed ROI clipping and CRS reprojection via `pyproj`.
`climate` implements three spatial-interpolation strategies; the
kriging path uses `pykrige` and selects among spherical, exponential,
Gaussian, and optionally nested variogram candidates
[@cressie1993spatial] by leave-one-out cross-validation RMSE on the
first climate variable. `model` computes the normalised weighted
suitability score. `pipeline` orchestrates the end-to-end flow,
derives a `numpy.random.default_rng` seed from the SHA-256 of the
run fingerprint, samples up to `max_cells` valid cells, and writes the
artifacts atomically. `sensitivity` and `validation` are optional
stages consuming the same `DataCatalog`, so every analysis is pinned
to the exact inputs recorded in the manifest. Two design decisions
matter most for research use: every artifact is schema-versioned
(the pipeline invalidates a cached run when `features.parquet`
carries a stale `terraflow_schema_version`), and the `run_fingerprint`
deliberately excludes file mtimes and absolute paths so the same
content hashes produce the same fingerprint across machines and
filesystem copies.

**GeoAI engine adapter (v0.4.0).** A new `geoai_engine` module wraps
the `geoai` library [@wu2026geoai] behind three orchestrators —
`run_fields`, `run_landcover`, `run_canopy` — exposed as the
`terraflow geoai {fields,landcover,canopy}` sub-app. Each runner
validates the `geoai:` block of the YAML config against a Pydantic
`GeoAIConfig` schema (engine name, power-of-two chip size ≥ 32,
confidence threshold in [0, 1], positive batch size), then computes
a `geoai_fingerprint` from the canonicalised config, sorted input
SHA-256 hashes, and a `model_metadata` payload that includes the
model name, weights SHA-256, the `geoai` library `major.minor`, and
the runtime-detected device (`cpu` / `cuda` / `mps`) plus the
installed `torch` `major.minor`. Because the device and torch minor
version participate in the hash, the same configuration legitimately
produces different fingerprints — and different cache directories —
when run on different accelerators or under a different torch
release, surfacing what would otherwise be silent output drift in
foundation-model inference. `torch.manual_seed` is set
deterministically from the fingerprint before every run, and the
runner skips inference entirely when the fingerprinted manifest
already exists, providing the same content-addressable caching as the
climate pipeline. Outputs land at
`<output_dir>/runs/<geoai_fingerprint>/geoai/` alongside a
`geoai_manifest.json` (engine, fingerprint, model metadata, input
hashes, full config, an explicit `roi_applied: false` flag describing
the deferred-ROI status, and the config snapshot) and a
`report.json` (duration, device, deterministic flag). The library is
an opt-in extra (`pip install "terraflow-agro[geoai]"`); the base
install remains lightweight and the default CI matrix continues to
test the climate pipeline without `torch`.

![TerraFlow pipeline: configuration is canonicalised, input files are hashed, and outputs land under a content-addressable run directory.](figure2.jpeg){ width=85% }

# Research impact statement

TerraFlow v0.4.0 is aimed at the near-term reproducibility and
inference-orchestration needs of agricultural researchers. Concrete
community-readiness signals are in place: 289 automated tests across
the climate, sensitivity, validation, export, and GeoAI engine
modules; an enforced 85 % coverage floor (current coverage 87 %);
type-checked Python 3.10–3.12 on CI; a public PyPI package
(`terraflow-agro`); a Homebrew tap for macOS; an opt-in GeoAI CI
workflow gated on changes to the engine, schema, and CLI files; and
a Dockerfile whose smoke test runs the full climate demo with
`--network none` and verifies that `features.parquet`, `manifest.json`,
and `report.json` are produced offline. The documentation site
publishes a reproducibility page enumerating what each fingerprint
covers (including a dedicated section on the GeoAI device and torch
sensitivity) and the known sources of non-determinism.

To make the climate-pipeline reproducibility guarantees concrete, we
report the metrics produced by a single end-to-end run of the bundled
demo (`terraflow run`, `sensitivity`, and `validate` on
`examples/demo_config.yml`). The demo ROI spans ~608 km × 233 km of
western Kansas; the 20-station synthetic climate network is
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

The kriging LOOCV RMSE on `mean_temp` is small relative to the
16.8–22.0 °C inter-station range, confirming that the selected
spherical variogram captures the synthetic climate gradient. The
balanced Sobol' indices are the expected result of weights
constrained to sum to one over variables with comparable normalised
dynamic range; they demonstrate the full sensitivity-analysis
pipeline rather than a scientific claim about the demo data. The
near-zero Cohen's κ is likewise expected — the demo raster is
randomised crop codes and the reference labels are independent —
and its purpose here is to show that the validation stage emits the
metric, not that the demo model predicts reality. A reviewer can
reproduce every number in the table by running `make get-demo-data
&& terraflow run -c examples/demo_config.yml` and the two companion
subcommands, and can verify the published `run_fingerprint` matches
without needing any shared compute infrastructure.

The GeoAI engine ships with a fully exercised orchestration contract
(config validation, fingerprinting, caching, manifest emission,
seeded inference) backed by a 12-test mocked-engine suite that
patches the heavy ML dependencies, so the cache-hit and
fingerprint-sensitivity invariants are guaranteed without requiring
`torch` on the default CI runners. End-to-end accuracy benchmarks
against real Sentinel-2 inputs are out of scope for this submission;
they are a planned v0.5.x companion paper.

We expect adoption among graduate courses and agronomy research
groups that currently maintain ad-hoc scripted pipelines and that
wish to compose foundation-model inference with classical climate
interpolation under a single provenance contract. Usage metrics
(PyPI downloads, GitHub stars, citation graph via Zenodo DOI
10.5281/zenodo.18490119) will be reported in future releases.

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
