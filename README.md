# TerraFlow: Reproducible Geospatial Agricultural Modeling

[![CI](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/ci.yml)
[![Deploy Docs](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/docs.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/docs.yml)
[![Publish to PyPI](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/publish-pypi.yml)
[![Build JOSS Manuscript](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/manuscript.yml/badge.svg)](https://github.com/gmarupilla/AgroTerraFlow/actions/workflows/manuscript.yml)
[![PyPI](https://img.shields.io/pypi/v/terraflow-agro.svg)](https://pypi.org/project/terraflow-agro/)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=gmarupilla_AgroTerraFlow&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=gmarupilla_AgroTerraFlow)
[![Codecov](https://codecov.io/gh/gmarupilla/AgroTerraFlow/branch/main/graph/badge.svg)](https://codecov.io/gh/gmarupilla/AgroTerraFlow)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

TerraFlow is a reproducible, config-driven geospatial workflow for agricultural suitability modeling. Give it a land-cover raster, a climate CSV, and a YAML config — it returns a scored, location-stamped results table with full provenance.

**Documentation:** [terraflow.marupilla.dev](https://terraflow.marupilla.dev)

---

## Installation

```bash
uv pip install terraflow-agro
# or
pip install terraflow-agro
```

For kriging-based interpolation:

```bash
pip install terraflow-agro pykrige
```

## Quickstart

```bash
terraflow --config config.yml
```

A minimal config:

```yaml
raster_path: "data/land_cover.tif"
climate_csv: "data/climate.csv"
output_dir: "outputs"
roi:
  type: bbox
  xmin: -120.5
  ymin: 34.0
  xmax: -118.0
  ymax: 35.5
model_params:
  v_min: 0.0
  v_max: 1.0
  t_min: 10.0
  t_max: 35.0
  r_min: 100.0
  r_max: 800.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3
```

Results are written to `outputs/runs/<fingerprint>/`:

```
features.parquet   — scored cells (lat, lon, score, label, …)
results.csv        — same data in CSV
manifest.json      — full provenance record
report.json        — QA stats and timings
```

## CLI subcommands

| Subcommand | Purpose |
|---|---|
| `terraflow run -c config.yml` | Run the full pipeline |
| `terraflow sensitivity -c config.yml` | Sobol' / Morris sensitivity indices for model weights |
| `terraflow validate -c config.yml` | Spatial block CV, Cohen's kappa, Moran's I on residuals |

See [CLI docs](https://terraflow.marupilla.dev/cli/usage/) for full reference.

## Climate interpolation

Three spatial algorithms are available via `interpolation_method`:

| Method | Notes |
|---|---|
| `linear` (default) | `scipy.griddata` — fast, no extra deps |
| `kriging` | Ordinary Kriging via `pykrige`; adds `{var}_krig_std` uncertainty columns |
| `idw` | Inverse Distance Weighting (power=2) — faster than kriging, no uncertainty |

Combine `interpolation_method: kriging` with `uncertainty_samples: N` in `model_params` to get Monte Carlo score confidence intervals (`score_ci_low` / `score_ci_high`).

See [Config Schema](https://terraflow.marupilla.dev/config/schema/) for the full reference.

## Python API

```python
from terraflow.pipeline import run_pipeline

results_df = run_pipeline("config.yml")
```

## Development

```bash
git clone https://github.com/gmarupilla/AgroTerraFlow.git
cd AgroTerraFlow
make dev       # create .venv and install dev deps
make test      # run test suite
make lint      # ruff + black
make docs-build
```

## Architecture

Core modules: `cli`, `config`, `climate`, `geo`, `ingest`, `model`, `pipeline`, `stats`, `viz`.

Key design decisions are documented in Architecture Decision Records under `docs/architecture/`.

## Project Scope

TerraFlow is a reproducible pipeline for geospatial agricultural modeling. It
handles raster ingestion, ROI clipping, climate interpolation, suitability
scoring, and deterministic artifact generation.

**In scope:**
- Configuration-driven pipeline execution (YAML → Parquet + provenance artifacts)
- Spatial interpolation of point climate observations (linear, kriging, IDW)
- Per-cell suitability scoring with uncertainty quantification (Monte Carlo)
- Deterministic run fingerprinting and artifact caching

**Out of scope:**
- Real-time data ingestion or streaming workflows
- General-purpose raster analysis (use `rioxarray` or `rasterstats` instead)
- Cloud-scale distributed processing (no Dask/Spark integration planned)
- Web application or GUI layer

## Maintenance & Support

TerraFlow is actively maintained. Bug fixes are prioritized; the test suite and
CI pipeline are kept green on every commit.

Feature requests are evaluated against project scope — open an issue to discuss
before building. Not all requests will be accepted.

Support is provided on a best-effort basis via [GitHub Issues](https://github.com/gmarupilla/AgroTerraFlow/issues).
Response time is typically within a week. There is no paid support tier.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citation

If you use TerraFlow in your research, please cite our JOSS paper (manuscript in preparation).

## License

MIT License — free for academic, commercial, and open-source use.
