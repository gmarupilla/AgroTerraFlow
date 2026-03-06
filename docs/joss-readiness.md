---
title: JOSS Readiness Checklist
description: Self-assessment of TerraFlow's readiness for submission to the Journal of Open Source Software.
icon: material/check-decagram
tags:
  - JOSS
  - Reference
  - Quality
---

# JOSS Readiness Checklist

Self-assessment against the
[JOSS review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html).
Reviewers are encouraged to use this page as a starting point.

---

## Software licence

- [x] MIT licence present at repository root ([LICENSE](https://github.com/gmarupilla/AgroTerraFlow/blob/main/LICENSE))

---

## Authors and affiliations

- [x] `paper.md` lists all authors with ORCID identifiers and affiliations
- [x] Affiliation 1: Independent Researcher & Software Engineer (Scientific Computing)
- [x] Affiliation 2: University of Central Missouri, Missouri, United States

---

## Statement of need

- [x] `paper.md` §Statement of Need explains the problem TerraFlow solves
- [x] Compares to related tools: `rasterstats`, `rasterio`, `pandas`, Plotly,
      Google Earth Engine, QGIS (comparison in paper §Statement of Need)
- [x] Target audience identified: agricultural data scientists, agronomy
      researchers, graduate students in environmental data science

---

## Installation instructions

- [x] PyPI package: `pip install terraflow-agro`
- [x] Source install: `pip install -e ".[dev]"` (see [Quickstart](quickstart.md))
- [x] System dependencies documented (GDAL via rasterio wheels; no manual GDAL build needed)
- [x] Docker image available for reproducible environment

---

## Example usage

- [x] [Quickstart](quickstart.md) walks through a 10-minute end-to-end run
- [x] [Field Guide](field-guide.md) for non-technical users
- [x] `examples/demo_config.yml` included in the repository
- [x] `make run-demo` target documented

---

## Automated tests

- [x] 124+ tests across 14 test files (`pytest`)
- [x] Tests cover: CLI, config validation, ingest, geospatial ops, climate
      interpolation, model scoring, statistics, visualisation, run identity,
      artifact contracts
- [x] Coverage target: 85% (`fail_under = 85` in `pyproject.toml`)
- [x] CI on Python 3.13 (GitHub Actions, `ci.yml`)
- [x] Smoke run with synthetic data in CI

---

## Documentation

- [x] Project homepage: <https://terraflow.marupilla.dev>
- [x] Install & quickstart: [docs/quickstart.md](quickstart.md)
- [x] API reference auto-generated from docstrings (`mkdocstrings`)
- [x] Architecture Decision Records (ADRs 001–004) documenting key design
      choices
- [x] Artifact contract documented: [docs/architecture/artifacts.md](architecture/artifacts.md)
- [x] Reproducibility guarantees documented: [docs/architecture/run-identity.md](architecture/run-identity.md)
- [x] CRS policy documented: [docs/architecture/adr-004-crs-reprojection.md](architecture/adr-004-crs-reprojection.md)
- [x] Failure modes / error taxonomy documented in artifact contract page

---

## Community guidelines

- [x] `CONTRIBUTING.md` / `docs/contributing.md` present
- [x] `CODE_OF_CONDUCT.md` present
- [x] Bug tracker: <https://github.com/gmarupilla/AgroTerraFlow/issues>
- [x] `SECURITY.md` present

---

## Versioning and archival

- [x] Version declared in `pyproject.toml` (`version = "0.2.0"`)
- [x] `CHANGELOG.md` present
- [x] Published to PyPI (`terraflow-agro`)
- [x] Zenodo DOI assigned: [`10.5281/zenodo.18490119`](https://doi.org/10.5281/zenodo.18490119)
      (recorded in `paper.md` front-matter as `repository-artifact`)
- [ ] JOSS paper submitted — **pending**

---

## Known gaps (resolve before submission)

| Gap | Action required |
|---|---|
| `paper.md` date is `2025-11-27` | Update to actual JOSS submission date |
| Random cell sampling is not seeded | Already documented in paper §Reproducibility and [Run Identity](architecture/run-identity.md#limitations) |
| Evaluation section lacks quantitative results | Add a `paper/eval.py` script that computes metrics from the demo dataset and include output in paper |
