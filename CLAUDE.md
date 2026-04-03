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
| `config.py` | `PipelineConfig`, `ModelParams`, `ROI` Pydantic models |
| `ingest.py` | `RasterLayer`, `ClimateLayer`, `DataCatalog` |
| `geo.py` | ROI clipping, CRS alignment |
| `climate.py` | `ClimateInterpolator` (linear / kriging / IDW) |
| `model.py` | `suitability_score`, `suitability_label` |
| `pipeline.py` | End-to-end orchestration, artifact writing |
| `sensitivity.py` | Sobol' / Morris analysis |
| `validation.py` | Spatial CV, kappa, Moran's I |
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
