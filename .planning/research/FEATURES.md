# Feature Landscape

**Domain:** Research-grade geospatial / agricultural suitability Python library
**Researched:** 2026-03-18
**Milestone context:** Subsequent milestone — TerraFlow 0.2.x already exists; features being added are sensitivity analysis, model validation, spatial statistics rigor (kriging diagnostics), CRS validation, H3 index export, and JOSS paper finalization.

---

## Confidence Note

External web search and WebFetch were unavailable in this session. JOSS criteria are assessed from training data (HIGH confidence — JOSS publishes its reviewer checklist openly and it has been stable for several years; criteria are well-documented in the research software engineering literature). Feature landscape assessment for geospatial/ag libraries is MEDIUM-HIGH confidence from training data cross-referenced against the project's own bibliography (rasterstats, rioxarray, GEE, PyKrige, SALib) and the paper's Statement of Need.

---

## Table Stakes

Features that JOSS reviewers will check and that peer reviewers in geospatial/ag science will expect. Missing = paper rejected or revision requested with major changes.

| Feature | Why Expected | Complexity | Current State | Notes |
|---------|--------------|------------|---------------|-------|
| Installable from PyPI with `pip install` | JOSS checklist item 1: software must be installable | Low | Done — `terraflow-agro==0.2.1` | Must stay working |
| Automated test suite (not trivial) | JOSS checklist: tests must exist and pass | Low | Done — 127 tests, 85% coverage threshold | Coverage gaps in MC uncertainty path, CRS edge cases |
| CI that runs tests on every PR | JOSS checklist: automated testing | Low | Done — GitHub Actions 3.10/3.11/3.12 matrix | Green |
| CLI entry point that works after install | JOSS checklist: software must be functional | Low | Done — `terraflow -c config.yml` | |
| API documentation (docstrings + rendered docs) | JOSS checklist: API documented | Medium | Done — MkDocs site, module docstrings | Verify all new public functions have docstrings before submission |
| Example / quickstart that a reviewer can run | JOSS checklist: example usage required | Low | Partially done — `examples/demo_config.yml` but requires synthetic raster script | Must be runnable without real USDA data download |
| `CITATION.cff` with ORCID | JOSS requirement for attribution | Low | Done — both authors, both ORCIDs | |
| `CHANGELOG.md` with version history | JOSS review: reviewers check project history | Low | Done — reconstructed history back to 0.1.0 | Close [Unreleased] → 0.3.0 before submission |
| OSI-approved license | JOSS requirement | Low | Assumed done (verify `LICENSE` file present) | Verify |
| Zenodo archive / DOI | JOSS requires archived version | Low | Done — `10.5281/zenodo.18490119` | Update archive at submission time |
| Deterministic / reproducible outputs | Core identity of TerraFlow; paper's central claim | High | Done — SHA-256 fingerprint, seeded sampling | |
| Provenance artifact (`manifest.json`) | Research reproducibility expectation | Medium | Done — schema v1 | |
| Geostatistically defensible interpolation | Any geospatial reviewer will check | High | Done — OrdinaryKriging with LOOCV (Stage 1) | This was the single largest scientific credibility gap; now addressed |
| Per-cell interpolation uncertainty | Required for credible uncertainty propagation downstream | High | Done — `{var}_krig_std` columns in features.parquet (Stage 1) | |
| Interpolation cross-validation metrics | Quantitative claim: "RMSE = X °C" | Medium | Done — LOOCV metrics in `report.json` under `interpolation_cv` (Stage 1) | Needs to appear in paper.md with actual numbers from demo run |
| Monte Carlo uncertainty propagation | Peer expectation for uncertainty-aware pipelines | High | Done — `score_ci_low`/`score_ci_high` per cell (Stage 2) | MC path test coverage gap — needs regression tests |
| CRS validation with informative errors | Broad exception handlers mask CRS bugs; JOSS reviewer will test edge cases | Medium | Partial — broad `except Exception` in `geo.py`; CRS mismatch detection not informative | Active milestone item |
| Parquet output with schema versioning | Cross-language reproducibility; research data standards | Medium | Done — schema v1 Parquet metadata | |

---

## JOSS-Specific Requirements (Not Just "Nice to Have")

These are items from the JOSS reviewer checklist that go beyond general software quality. Each maps directly to a JOSS review checklist item. A reviewer who finds any of these missing will open a mandatory revision request.

| JOSS Checklist Item | Status | Gap / Action |
|---------------------|--------|--------------|
| Paper has a Statement of Need | Done | paper.md has SoN section; strengthen "without TerraFlow you'd write N lines of boilerplate" argument |
| Paper describes software functionality | Done | Architecture section present |
| Paper includes references to prior work | Partial — biblio.bib has rasterstats, GEE, rioxarray, QGIS, rasterio | Missing: citation for SALib (Saltelli et al.), PyKrige/kriging (Cressie 1993, Matheron 1963), Monte Carlo UQ (JCGM 2008), FAO GAEZ — add when those stages are implemented |
| Paper describes research applications / target audience | Done | "agricultural data scientists, agronomy researchers, graduate students" |
| Software is open source with OSI license | Assumed done; verify LICENSE file |
| Software repository URL matches paper | Done — github.com/gmarupilla/AgroTerraFlow |
| Software has tests | Done | Gaps: MC path, CRS edge cases — patch before submission |
| Tests pass on reviewer's machine | CI green, Docker e2e works | Ensure synthetic raster path works end-to-end without network |
| Quantitative results in paper | MISSING — paper has no numbers table | Add: interpolation LOOCV RMSE, MC uncertainty width, Sobol indices (if Stage 3 done) |
| Paper date current | MISSING — paper.md says 2025-11-27 | Update to submission date |
| Community guidelines (CONTRIBUTING.md) | Done — docs/contributing.md | |
| Installation instructions | Done — README quickstart | |

---

## Differentiators

Features that distinguish TerraFlow from rasterstats, rioxarray, and ad-hoc scripts. These are what make the JOSS paper interesting beyond "yet another pipeline."

| Feature | Value Proposition | Complexity | Status | Notes |
|---------|-------------------|------------|--------|-------|
| Content-addressable run fingerprinting | Same inputs → same run directory, globally unique, no timestamps | High | Done | No peer in the ag geospatial space does this; make it prominent in paper |
| Kriging with automatic variogram selection | BLUP + auto-selects spherical/exponential/Gaussian by LOOCV | High | Done | Differentiates from IDW-only or griddata tools |
| Geostatistical LOOCV reported in output artifact | Quantitative interpolation accuracy claim in `report.json` | Medium | Done | Enables paper to make "RMSE = X" claim; no comparable ag tool does this |
| Monte Carlo uncertainty propagation through suitability model | Per-cell CI bounds (p05, p95) on suitability score | High | Done | Distinguishes from point-estimate tools; enables "suitability call is robust/uncertain" |
| Sensitivity analysis (Sobol' indices via SALib) | Quantifies which model weights drive variance — first-order and total-effect indices | High | Active milestone | No ag suitability library does this out of the box; strong differentiator for the paper |
| Model validation against reference classification (Cohen's κ) | Benchmarks scores against FAO GAEZ or user-supplied reference | High | Active milestone | Transforms paper from "reproducible" to "reproducible AND directionally correct" |
| Atomic artifact writes + no-op rerun detection | Prevents partial outputs; avoids redundant computation | Medium | Done | Rarely seen in research pipeline tools |
| H3 index export | Suitability results indexed by H3 cell for DeckGL/Pandas H3 interop | Medium | Active milestone | Opens TerraFlow to spatial analytics toolchains that are H3-native |
| Variogram diagnostics in output artifacts | Variogram model name, parameters, selection RMSE per variable in report.json | Medium | Partially done (LOOCV metrics) | Reviewers familiar with geostatistics will look for this; expand report.json to include variogram model + nugget/sill/range |
| CRS-agnostic pipeline with explicit validation | Any input CRS → WGS84 output, with informative errors on mismatch | Medium | Partial — reprojection works, error messages not informative | Completing this makes TerraFlow more robust than most research scripts |

---

## Anti-Features

Features to explicitly NOT build for this milestone. Each has a clear reason why building it would harm the project.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Web UI / dashboard | Out of scope for library; JOSS reviews libraries not applications; adds significant maintenance burden | `viz` module produces HTML map via Plotly — that is sufficient for exploratory use |
| Real-time / streaming ingestion | TerraFlow is a batch pipeline by design; streaming would require a fundamentally different architecture | Document that TerraFlow is for offline, reproducible batch analysis |
| ML-based weight learning (neural net, random forest) | Adds black-box methods without citable agronomic basis; would undermine the "transparent model" differentiator | Sobol' sensitivity analysis (Stage 3) provides quantitative weight guidance within the existing parametric model |
| Universal Kriging with elevation covariate | Scientifically superior in mountainous terrain but requires an elevation raster input, increasing user friction; ADR-005 explicitly deferred this | Document as Future Work in paper.md; defer to post-JOSS release |
| Bayesian hierarchical suitability model | High implementation complexity; no established standard to cite that maps cleanly to TerraFlow's parametric model | MC uncertainty propagation (already done) provides calibrated CI bounds without requiring a full Bayesian treatment |
| Non-Python client SDKs | Premature for v0.x; splits maintenance burden | Python-first for JOSS submission; output is Parquet → any language can consume it |
| STAC / COG cloud integration | Changes input contract fundamentally; Q3 2026+ in roadmap | Document in Future Work; do not implement before JOSS |
| Polygon ROI (GeoJSON/Shapefile) | Requires geopandas dependency, significant geo module refactor; good future feature but not needed for JOSS | Bbox ROI is sufficient for the demo; document polygon ROI as a planned enhancement |
| Temporal analysis / time-series kriging | Out of scope for v0.x; would require schema v2 | Document as Future Work |
| Automated FAO GAEZ / USDA NASS data download | Adds network dependency; makes tests fragile; licensing uncertainty for bundled data | Provide reference CSV example in `examples/`; let user supply their own reference labels |

---

## Feature Dependencies

Dependencies between active milestone features (build order matters):

```
Kriging (Stage 1, DONE)
  └── Monte Carlo uncertainty (Stage 2, DONE)
        └── Sensitivity analysis (Stage 3, Active)
              └── Paper sensitivity results table (JOSS paper finalization)

Kriging LOOCV metrics (Stage 1, DONE)
  └── Variogram diagnostics in report.json (Active — expand existing metrics)
        └── Paper interpolation accuracy claim with numbers (JOSS paper)

CRS validation / informative errors (Active)
  └── CRS edge case tests (Active)
        └── CI green on CRS edge cases (table stakes for JOSS)

Model validation against reference (Stage 4, Active)
  └── Cohen's κ / confusion matrix in report.json (Active)
        └── Paper validation results table (JOSS paper finalization)
            └── JOSS paper: "directionally consistent with agronomy"

H3 index export (Active — independent of above)
  └── Features parquet gains h3_index column (new schema column, not v2 break)
```

---

## MVP Recommendation for This Milestone

Prioritize (ordered by JOSS submission impact):

1. **CRS validation with informative errors** — table stakes; blocking test coverage gap
2. **Sensitivity analysis (Sobol' / Morris via SALib)** — differentiator; enables quantitative weight justification in paper; ~1 week effort
3. **Model validation against reference classification** — highest single JOSS impact; transforms reproducibility claim into scientific claim; ~2 weeks
4. **Variogram diagnostics in report.json** — medium effort, high reviewer satisfaction for geostatisticians; extend existing LOOCV output
5. **Paper finalization: add numbers table, update date, add SALib/kriging citations** — low effort, directly unblocks submission
6. **H3 index export** — lower JOSS priority (useful but not a reviewer requirement); implement after items 1-5

Defer to post-JOSS:
- Universal Kriging with elevation covariate: scientifically superior but increases user friction; ADR-005 explicitly deferred
- Polygon ROI: good future feature; not needed for paper
- STAC/COG cloud integration: Q3 2026+
- Large raster windowed reads: performance optimization; not a JOSS blocker

---

## Sources

All sources are internal to this session (no external search available). Confidence is based on:

- Project files: `.planning/PROJECT.md`, `.planning/codebase/CONCERNS.md` — HIGH confidence, authoritative
- Memory files: `project_joss_triage.md`, `project_research_roadmap.md` (3 days old; verify current code state) — HIGH confidence for decisions, MEDIUM for line-level code claims
- Paper: `paper/paper.md`, `paper/biblio.bib` — HIGH confidence
- ADR-005: `docs/architecture/adr-005-kriging-interpolation.md` — HIGH confidence
- JOSS review criteria: training data (JOSS publishes its reviewer checklist; stable for several years) — HIGH confidence for criteria categories, MEDIUM for exact wording
- Geospatial/ag library ecosystem: training data + paper's own Statement of Need comparisons — MEDIUM confidence; verify against current rasterstats, rioxarray, pysal documentation if deeper ecosystem comparison is needed
