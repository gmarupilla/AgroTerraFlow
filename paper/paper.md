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
    affiliation: '1'
  - name: Chandhini Bayina
    orcid: 0009-0002-1359-1762
    affiliation: '2'
affiliations:
  - index: 1
    name: Independent Researcher & Software Engineer (Scientific Computing)
  - index: 2
    name: University of Central Missouri, Missouri, United States
date: 2025-11-27
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

TerraFlow is an open-source Python library designed to provide reproducible,
auditable geospatial workflows for agricultural and environmental data science.
It provides a modular, configuration-driven pipeline for loading raster
datasets (e.g., land-cover maps, soil indices), clipping them to a user-defined
region of interest (ROI), merging them with spatially-interpolated climate
observations, computing per-cell suitability scores, and exporting
analysis-ready artifacts with full provenance.

Unlike ad-hoc script collections, every TerraFlow run produces three guaranteed
output artifacts — a Parquet feature table, a machine-readable provenance
manifest, and a QA report — stored under a deterministic, content-addressable
run directory.  The same configuration and input data always yield the same run
fingerprint, making results independently verifiable.

![TerraFlow architecture showing configuration, pipeline orchestration, ingestion, geospatial operations, modeling, and outputs.](figure1.jpeg)

# Statement of Need

Geospatial workflows in agriculture frequently combine public raster products
such as the USDA Cropland Data Layer (CDL) [@usda_cdl] with tabular climate
summaries, soil data, or management records.  Typical tasks include reading
multi-band or single-band GeoTIFFs, clipping to a study area, spatial
interpolation of point climate observations, feature engineering, and exporting
scored outputs.

Existing tools address parts of this problem but not the full pipeline:

- **`rasterstats`** [@rasterstats] provides efficient zonal statistics from
  raster + vector pairs, but does not handle climate interpolation, CRS
  normalisation, or provenance tracking.
- **`rioxarray` / `xarray`** [@rioxarray; @hoyer2017xarray] offer powerful
  N-dimensional raster operations but require users to assemble their own
  pipeline and provenance strategy.
- **Google Earth Engine (GEE)** [@gorelick2017gee] enables planetary-scale
  analysis but requires internet connectivity, a Google account, and does not
  support offline or air-gapped environments.
- **QGIS** [@qgis] provides an interactive GUI for geospatial analysis but is
  not designed for scripted, reproducible batch workflows.
- **`rasterio`** [@gillies2013rasterio] and **`pandas`** [@mckinney2010pandas]
  are indispensable lower-level building blocks, but they leave the pipeline
  assembly, validation, and provenance entirely to the user.

TerraFlow fills the gap between these tools by providing a fully reproducible,
tested, configuration-driven pipeline that integrates:

1. Pydantic-validated YAML configuration for clarity and versioning.
2. A `DataCatalog` abstraction that separates metadata collection from
   orchestration, making ingestion testable in isolation.
3. Spatially-aware climate interpolation (`scipy.griddata`) with
   configurable fallback strategies.
4. Automatic CRS detection and reprojection: output coordinates are always
   WGS84 geographic degrees regardless of input raster projection.
5. A deterministic run fingerprint computed from config + ROI geometry + input
   file SHA-256 hashes (timestamp-independent), enabling content-addressed
   run identities.
6. Guaranteed output artifacts: `features.parquet` (schema v1), `manifest.json`,
   and `report.json` written atomically to
   `<output_dir>/runs/<run_fingerprint>/`.
7. Automated tests (124+), continuous integration, and optional Docker execution.

The target audience includes agricultural data scientists, agronomy researchers,
and graduate students who need a transparent, low-dependency starting point for
geospatial modeling — without building a pipeline from scratch.

![TerraFlow pipeline workflow from configuration to final outputs.](figure2.jpeg)

# Software Description

## Architecture and Design

TerraFlow is organised into modules with strict boundary contracts, following
the principle of separation of concerns [@wilson2017good]:

### `config`

Validates all configuration fields using Pydantic [@pydantic], including raster
paths, climate CSV paths, ROI bounding box coordinates, CRS specification,
maximum sample counts, output directories, and model weights.  Configuration
is declared in YAML and validated before any I/O begins, providing early,
actionable error messages.

### `ingest`

Loads raster datasets via `rasterio` [@gillies2013rasterio] and climate tables
via `pandas` [@mckinney2010pandas].  The module exposes a `DataCatalog`
abstraction — a Pydantic model collecting CRS, spatial bounds, nodata value,
dtype, shape, and SHA-256 fingerprint for each input layer.  The `DataCatalog`
interface enforces that the ingest layer resolves metadata only and must not
orchestrate pipeline steps or write final features.

### `geo`

Handles ROI clipping and spatial operations:

- Bounding box validation and CRS reprojection via `pyproj`.
- ROI clipping using windowed reads (`rasterio`), respecting native nodata
  masking.
- Detection and rejection of degenerate clip windows (zero-area intersections).

This keeps geospatial logic localised and testable in isolation.

### `climate`

Implements two strategies for aligning tabular climate observations to raster
cells:

- **Spatial interpolation** (`scipy.interpolate.griddata`): bilinear
  interpolation of weather station values to cell centroids, with
  nearest-neighbour fallback for extrapolation.
- **Index matching**: row-order or cell-ID based alignment for pre-gridded
  climate data.

Global mean fallback (`fallback_to_mean`) handles sparse station networks.

### `model`

Implements a transparent, parametric suitability model that normalises
vegetation index, mean temperature, and total rainfall to `[0, 1]` using
user-defined min/max bounds, computes a weighted composite score, and assigns
a categorical label (`low`, `medium`, `high`).  Although intentionally simple,
the model demonstrates how TerraFlow can host domain-specific extensions
including crop-type, hydrological, or risk models.

### `core.run_identity`

Computes a deterministic `run_fingerprint` from three content-addressable
components:

1. **Canonical config JSON** — YAML parsed and re-serialised with sorted keys.
2. **ROI geometry hash** — Shapely geometry [@shapely] normalised via
   `set_precision` (1×10⁻⁷°) and `normalize`, then SHA-256 hashed over WKB
   bytes.  Equivalent polygons in different vertex orders produce identical
   hashes.
3. **Input file fingerprints** — SHA-256 + byte-size per file; file
   modification timestamps are deliberately excluded so the fingerprint is
   stable across filesystem copies and CI clones.

The fingerprint is encoded as a base64url string and used as the run directory
name, making run directories globally unique and content-addressed.

### `pipeline`

Coordinates the full workflow:

1. Load and validate configuration; resolve relative paths.
2. Compute run fingerprint; detect and return cached run if all artifacts
   exist (no-op rerun).
3. Build `DataCatalog` (metadata only, no pixel reads at this stage).
4. Load raster and climate data; clip raster to ROI.
5. Interpolate climate values to cell centroids.
6. Sample valid (non-nodata) cells up to `max_cells`; reproject centroids
   to WGS84.
7. Compute suitability scores.
8. Write `features.parquet`, `manifest.json`, `report.json`, and
   `results.csv` atomically to `<output_dir>/runs/<run_fingerprint>/`.

## Output Artifact Contract

Every run produces a stable, schema-versioned set of artifacts:

| Artifact | Schema version | Purpose |
|---|---|---|
| `features.parquet` | v1 (in Parquet metadata) | Tidy/wide per-cell feature table: `run_id`, `cell_id`, `lat`, `lon`, `v_index`, `mean_temp`, `total_rain`, `score`, `label` |
| `manifest.json` | v1 | Config snapshot, input SHA-256 fingerprints, `DataCatalog` metadata, code version, git SHA, UTC timestamp |
| `report.json` | v1 | Per-layer coverage fraction, nodata cell counts, raster/climate statistics, per-step wall-clock timings |

The `run_id` column in `features.parquet` links every row back to
`manifest.json`, enabling multi-run provenance joins.

Apache Arrow / Parquet [@pyarrow] is used as the canonical output format
because it is cross-platform, column-compressed, schema-preserving, and
natively readable by Python, R, Julia, and DuckDB.

### `viz`

Produces interactive HTML maps using Plotly [@plotly] for exploratory analysis
and stakeholder communication.

# Reproducibility

TerraFlow provides the following reproducibility guarantees:

- **Deterministic run identity**: the `run_fingerprint` depends only on file
  content (SHA-256), not on timestamps, machine identity, or execution order.
- **Cached re-runs**: identical inputs produce a no-op — the pipeline detects
  an existing run directory and returns the cached result without re-scoring.
- **Atomic artifact writes**: each file is written to a temporary path and
  renamed on success, preventing partially-written outputs from being
  mistaken for complete results.
- **CRS enforcement**: cell coordinates are always WGS84 geographic degrees in
  output, tested for both geographic (EPSG:4326) and projected (EPSG:32614)
  input rasters.
- **Seeded cell sampling**: when fewer cells are requested than exist in the
  ROI (`max_cells < n_valid_cells`), the sampled cell set is drawn using a
  `numpy.random.default_rng` generator seeded from the SHA-256 of the
  `run_fingerprint`.  Identical inputs always produce the same cell set.
- **Automated tests**: 127+ tests across 14 test files cover artifact schema
  contracts, determinism regression, CRS handling, nodata coverage, CLI
  behaviour, and unit tests for each module.
- **Continuous integration**: GitHub Actions CI runs lint, type checks, tests
  with coverage, a packaging sanity check, and a synthetic-data smoke run on
  every push and pull request.
- **Pinned dependencies and Docker**: optional Docker execution provides a
  fully reproducible environment across machines.

# Example Usage

The repository includes a demonstration configuration:

```bash
pip install terraflow-agro
terraflow -c examples/demo_config.yml
```

Running this command generates, under `outputs/demo_run/runs/<fingerprint>/`:

- `features.parquet` — per-cell suitability scores in analysis-ready Parquet format
- `manifest.json` — full provenance record
- `report.json` — QA summary including coverage fraction and step timings
- `results.csv` — backward-compatible CSV

Because all file paths, ROI bounds, and model parameters are declared in the
YAML config, workflows are portable: sharing the config file and input data is
sufficient to reproduce results on another machine.

# Future Work

Possible extensions include:

- STAC/COG integration for scalable cloud-native geospatial retrieval.
- Additional input layers: soil rasters, elevation (DEM), NDVI time series.
- ML-based yield or risk prediction models as pipeline model extensions.
- Uncertainty quantification and ensemble scoring.
- Educational notebooks demonstrating geospatial modeling concepts.

# Acknowledgements

TerraFlow builds on the scientific Python ecosystem including
`rasterio` [@gillies2013rasterio], `pandas` [@mckinney2010pandas],
Pydantic [@pydantic], Plotly [@plotly], Shapely [@shapely],
`rasterstats` [@rasterstats], and Apache Arrow [@pyarrow].
Sample raster data for demonstrations originates from the USDA National
Agricultural Statistics Service Cropland Data Layer [@usda_cdl].

References
