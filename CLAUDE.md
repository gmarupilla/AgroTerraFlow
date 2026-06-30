# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Environment
make venv          # Create .venv via uv
make dev           # Install package + dev dependencies in editable mode

# Testing
make test          # pytest -v (all tests)
make test-cov      # pytest with coverage report (≥85% required)
make smoke-test    # End-to-end smoke: pytest tests/test_e2e_smoke.py -m smoke

# Single test
pytest tests/test_climate.py::test_kriging_loocv -v

# Linting & formatting
make lint          # ruff check + black (line-length=120)
make lint-fix      # ruff --fix + black
make typecheck     # mypy

# Docs
make docs-serve    # Live-reload MkDocs
```

Pre-commit hooks run ruff + black automatically on staged files (`make pre-commit` to install).

## Architecture

TerraFlow is a config-driven geospatial agricultural suitability pipeline. Given a raster (land cover GeoTIFF) and a climate CSV, it produces scored cell features with full provenance tracking.

**Data flow:**
1. `config.py` — Pydantic v2 validates YAML → `PipelineConfig` (raster path, climate CSV, ROI, model weights)
2. `ingest.py` — `DataCatalog` holds metadata for `RasterLayer` + `ClimateLayer`; pixels not loaded until needed
3. `core/run_identity.py` — SHA256 fingerprint of canonicalized config + input file hashes → deterministic `run_id`
4. `geo.py` — Clips raster to ROI bbox; reprojects to EPSG:4326 (WGS84 is the invariant CRS)
5. `climate.py` — `ClimateInterpolator` spatially interpolates station CSV to cell centroids (methods: `linear`, `kriging`, `idw`)
6. `model.py` — `suitability_score()` computes normalized weighted combination of vegetation index, temperature, rainfall
7. `pipeline.py` — Orchestrates steps 2–6; writes artifacts to `<output_dir>/runs/<run_fingerprint>/`
8. `sensitivity.py` — Sobol'/Morris analysis via SALib (triggered by `terraflow sensitivity`)
9. `validation.py` — Spatial block CV + Cohen's kappa + Moran's I (triggered by `terraflow validate`)

**Output artifacts** (all under `outputs/<run_fingerprint>/`):
- `features.parquet` — tidy schema: `run_id, cell_id, lat, lon, v_index, mean_temp, total_rain, score, label`
- `manifest.json` — config snapshot + input fingerprints (provenance)
- `report.json` — QA stats, coverage ratios, timings
- `results.csv` — backward-compatible export

All artifacts land under `<output_dir>/runs/<run_fingerprint>/` (where `output_dir` is set in the YAML config).

**Key invariants:**
- CRS is always EPSG:4326; `geo.py` reprojects any input that isn't
- Identical inputs always produce identical `run_fingerprint` → cached outputs can be reused
- Coverage threshold enforced: runs fail if valid-cell ratio falls below configured minimum

## Module map

| Module | What it owns |
|--------|-------------|
| `cli.py` | Typer CLI — `run`, `sensitivity`, `validate` subcommands |
| `config.py` | `PipelineConfig`, `ModelParams`, `ROI`, `ClimateConfig` (`temporal_aggregations` + `scenarios`), `TemporalAggregation`, `Scenario`, `SensitivityConfig`, `ValidationConfig` Pydantic models |
| `ingest.py` | `RasterLayer`, `ClimateLayer`, `DataCatalog` |
| `geo.py` | ROI clipping, CRS alignment |
| `climate.py` | `ClimateInterpolator` (linear / kriging / IDW) |
| `climate_impact.py` | `run_climate_impact_features` — auto-invoked by `pipeline.run_pipeline` when `temporal_aggregations` + `scenarios` are set; writes `climate_features.parquet` |
| `temporal.py` | Multi-temporal climate aggregation engine — `compute_per_station_aggregations` outer-products rules × scenarios |
| `hazard.py` | WMO/ETCCDI-aligned indicators — `growing_degree_days`, `frost_days`, `heat_stress_days`, simplified Thornthwaite `spei` |
| `cmip6.py` | CMIP6 NetCDF ingest behind optional `[cmip6]` extra — `cmip6_metadata`, `load_cmip6_scenario`, `cmip6_to_station_timeseries`; handles non-Gregorian calendars |
| `model.py` | `suitability_score`, `suitability_label`, `suitability_score_array` |
| `pipeline.py` | End-to-end orchestration, artifact writing; auto-invokes `climate_impact.run_climate_impact_features` when configured |
| `sensitivity.py` | Sobol' / Morris analysis |
| `validation.py` | Spatial-block CV only (Cohen's κ + Moran's I removed in v0.5.0) |
| `core/run_identity.py` | Deterministic run fingerprinting |

## Tests

Fixtures are in `tests/conftest.py` — `synthetic_raster` creates a 5×5 GeoTIFF in EPSG:4326; `synthetic_climate_csv` / `*_dense` / `*_sparse` cover different station densities.

Smoke tests (`@pytest.mark.smoke`) in `test_e2e_smoke.py` run the full pipeline end-to-end with synthetic data.

Coverage floor is 85% (`fail_under = 85` in `pyproject.toml`).

## PR checklist

Per project conventions, every PR must:
- Update `README.md` (sparse — just what changed)
- Add/update docs in `docs/` (detailed)
- Add a Jupyter notebook example in `notebooks/` and register it in `docs/notebooks/`
- Update `mkdocs.yml` nav if new pages added
- Add an entry to `CHANGELOG.md` under `[Unreleased]`

## Packaging & Release

### Versioning

Version is declared in **two places** — both must be updated together:
- `pyproject.toml` line `version = "X.Y.Z"`
- `terraflow/__init__.py` `__version__ = "X.Y.Z"`

Project follows [Semantic Versioning](https://semver.org). Current version: `0.5.0`.

### Release steps

```bash
# 1. Update version in both files
# 2. Update CHANGELOG.md: move [Unreleased] items under a new [X.Y.Z] heading with date
# 3. Commit the version bump
git commit -m "chore: bump version to vX.Y.Z"
# 4. Tag and push — this fires both publish workflows
git tag vX.Y.Z
git push origin main --tags
```

### PyPI (`publish-pypi.yml`)

Triggers on `v*.*.*` tag push. Builds sdist + wheel, attests provenance, and publishes
to PyPI via `pypa/gh-action-pypi-publish`. Requires secret: `PYPI_API_TOKEN`.

Package name on PyPI: `terraflow-agro`. Install: `pip install terraflow-agro`.

### Homebrew tap (`publish-homebrew.yml`)

Triggers on the same `v*.*.*` tag, runs in parallel with the PyPI workflow.
Fetches the GitHub archive tarball, computes its SHA-256, then patches
`Formula/terraflow.rb` in `gmarupilla/homebrew-terraflow` (separate GitHub repo)
and pushes the update.

Requires secret: `HOMEBREW_TAP_TOKEN` (GitHub PAT with `repo` write scope on
`gmarupilla/homebrew-terraflow`).

Formula source of truth: `packaging/homebrew/Formula/terraflow.rb`  
Local helper (dev use): `packaging/homebrew/update_sha.sh <version>` — cross-platform
(works on macOS BSD sed and Linux GNU sed).

User install: `brew tap gmarupilla/terraflow && brew install terraflow`

### Optional extras

| Extra | Packages | Install |
|-------|----------|---------|
| `[cmip6]` | `xarray>=2024.1`, `netcdf4>=1.7` | `pip install terraflow-agro[cmip6]` |
| `[viz]` | `plotly` | `pip install terraflow-agro[viz]` |

## CI/CD Overview

All workflows live in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR to main | Tests (Py 3.10–3.12), lint, mypy, coverage, smoke tests, Docker E2E |
| `publish-pypi.yml` | `v*.*.*` tag | Build + publish to PyPI with provenance attestation |
| `publish-homebrew.yml` | `v*.*.*` tag | Auto-update Homebrew tap formula |
| `docs.yml` | push to main | Build + deploy MkDocs to GitHub Pages |
| `docs-preview.yml` | PR | Build docs preview |
| `quality.yml` | push/PR | Additional code quality checks |
| `claude.yml` | PR | AI-assisted review (skips bot authors) |
| `security.yml` | schedule/push | Dependency vulnerability scan |
| `license-check.yml` | push/PR | Verify dependency licenses |
| `sonarcloud.yml` | push/PR | SonarCloud static analysis |
| `manuscript.yml` | push/PR | Build JOSS paper PDF |

Coverage floor: 85% (`fail_under = 85` in `pyproject.toml`). Codecov tracks trends.

## Documentation Structure

MkDocs with Material theme, deployed to `https://terraflow.marupilla.dev`.

```
docs/
├── index.md                  # Home / landing page
├── quickstart.md             # 10-minute getting started
├── field-guide.md            # Practical usage guide
├── DEVELOPMENT.md            # Dev setup, release checklist
├── ROADMAP.md                # Feature roadmap
├── contributing.md           # Contribution guidelines
├── architecture/
│   ├── overview.md           # System architecture overview
│   ├── adr-001–006.md        # Architecture Decision Records
│   ├── boundaries.md         # System boundaries
│   ├── run-identity.md       # Run fingerprinting design
│   └── artifacts.md          # Output artifact contract
├── config/
│   ├── schema.md             # Full YAML config reference
│   └── examples.md           # Annotated config examples
├── cli/
│   └── usage.md              # CLI subcommand reference
├── install/
│   └── homebrew.md           # Homebrew install guide (macOS)
├── guides/
│   └── h3-export.md          # H3 hexagonal export guide
├── api/
│   ├── core.md               # terraflow.core autodoc
│   ├── ingest.md             # terraflow.ingest autodoc
│   └── climate.md            # terraflow.climate autodoc
└── notebooks/                # Rendered Jupyter notebooks
    ├── terraflow_v0_2_0_comprehensive_test.ipynb
    ├── kriging_uncertainty_demo.ipynb
    ├── 02_sensitivity_analysis.ipynb
    ├── 03_model_validation.ipynb
    ├── 04_h3_export.ipynb
    └── 05_extended_variogram_mode.ipynb
```

When adding a new page: create the `.md` file, add it to `mkdocs.yml` nav, and
(if it's a guide/feature) add a notebook in `notebooks/` registered under the
`Notebooks:` nav section.

## Key External Repos & Services

| Resource | URL / location |
|----------|---------------|
| Homebrew tap | `github.com/gmarupilla/homebrew-terraflow` |
| PyPI package | `pypi.org/project/terraflow-agro` |
| Docs site | `terraflow.marupilla.dev` |
| SonarCloud | project key `gmarupilla_AgroTerraFlow` |
| Codecov | `codecov.io/gh/gmarupilla/AgroTerraFlow` |
