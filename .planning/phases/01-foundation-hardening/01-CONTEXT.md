# Phase 1: Foundation Hardening - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Tighten the pipeline surface that JOSS reviewers will scrutinize:
- Replace broad exception handlers with typed, informative CRS mismatch errors
- Add missing test coverage for kriging fallback and MC uncertainty edge cases
- Surface variogram diagnostics (nugget, sill, range, model name) in report.json
- Move plotly to an optional [viz] extra and add JOSS-required packaging metadata

New capabilities (sensitivity analysis, validation, H3 export) are out of scope.
</domain>

<decisions>
## Implementation Decisions

### CRS Mismatch Error (HARD-01)
- **D-01:** Raise a custom `CRSMismatchError(ValueError)` — not `pyproj.CRSError` (which signals invalid CRS strings, not mismatches) and not a plain `ValueError`. The class must carry both CRS strings as attributes so callers can inspect them: `e.raster_crs`, `e.climate_crs`.
- **D-02:** The check belongs where the pipeline first compares raster CRS against climate station coordinate assumptions. Existing broad `except Exception` handlers in `pipeline.py` that could swallow CRS failures should be narrowed where appropriate.

### Variogram Diagnostics (HARD-03)
- **D-03:** Surface PyKrige variogram parameters (nugget, sill, range, model name) in `report.json` under a `variogram_diagnostics` key alongside the existing `interpolation_cv` block.
- **D-04:** Range is in **degrees** (lat/lon coordinate space). Include `"coordinate_units": "degrees"` in the variogram diagnostics block to document this limitation honestly. UTM reprojection is deferred to v2 (captured as GEO-03 in REQUIREMENTS.md).

### Test Coverage (HARD-02)
- **D-05:** Add tests for MC uncertainty edge cases not currently covered:
  - Zero kriging variance (all `krig_std = 0`) — CI should equal the point estimate
  - `uncertainty_samples=1` — should not raise; warn or document behavior
  - `krig_std` containing NaN values — pipeline should handle gracefully
- **D-06:** Kriging fallback test (`test_kriging_fallback_to_linear_too_few_stations`) already exists — do not duplicate. Fill the MC-specific gaps only.

### plotly Optional Dependency (HARD-04)
- **D-07:** Move `plotly>=5.0.0` from core `dependencies` to `[project.optional-dependencies]` under a `viz` key in `pyproject.toml`.
- **D-08:** Guard plotly import inside each viz function (not at module top level). Raise `ImportError("plotly required: pip install terraflow-agro[viz]")` when called without the dep.
- **D-09:** Add JOSS-required packaging metadata: trove classifiers (Topic :: Scientific/Engineering, Intended Audience :: Science/Research, etc.) and a `Documentation` URL pointing to the MkDocs site.

### Claude's Discretion
- Exact set of trove classifiers — follow standard scientific Python conventions
- Whether to define `CRSMismatchError` in a dedicated `exceptions.py` or inline in `geo.py` — choose whichever keeps the public API surface clean
- Whether `uncertainty_samples=1` produces a `UserWarning` or just silent behavior — Claude's call based on what's most useful to a researcher

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Foundation Hardening — HARD-01 through HARD-04 acceptance criteria

### Relevant Source Files
- `terraflow/geo.py` — existing CRS handling for ROI/raster; integration point for CRSMismatchError
- `terraflow/pipeline.py` — broad exception handlers at lines 236, 269, 293, 397, 741, 746; report.json assembly at ~line 652; variogram diagnostics surfacing point ~line 694
- `terraflow/climate.py` — `ClimateInterpolator._init_kriging()`: variogram selection, LOOCV, `cv_metrics`; `MIN_KRIGING_STATIONS=5` fallback threshold
- `terraflow/viz.py` — plotly import location (currently top-level)
- `pyproject.toml` — current dependencies and optional-dependencies sections
- `tests/test_climate.py` — existing kriging tests (~line 555+); do not duplicate
- `tests/test_uncertainty.py` — existing MC tests; add zero-variance and single-sample edge cases here

### External References
- PyKrige OrdinaryKriging: variogram params accessible via `ok.variogram_model_parameters` after fitting
- Issue #48 (HARD-01), #49 (HARD-02), #50 (HARD-03), #51 (HARD-04) on GitHub

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ClimateInterpolator.cv_metrics`: LOOCV RMSE/MAE already computed and in report.json as `interpolation_cv` — variogram params extend this same pattern
- `geo.py` CRS reprojection logic: `Transformer.from_crs` already used — `CRSMismatchError` fits naturally here
- `test_kriging_fallback_to_linear_too_few_stations`: existing test to reference, not duplicate

### Established Patterns
- Atomic writes use bare `except Exception` to clean up temp files and re-raise — these are correct, do not change
- `_get_package_version()` uses `except Exception` for optional import fallback — also correct
- Error messages in `geo.py` already include CRS strings in the message text — follow this pattern for `CRSMismatchError`

### Integration Points
- `report.json` assembly is in `run_pipeline()` around line 652 of `pipeline.py` — variogram diagnostics block goes alongside `interpolation_cv`
- PyKrige `OrdinaryKriging` is instantiated inside `ClimateInterpolator._init_kriging()` — store `variogram_model_parameters` on `self` during that call

</code_context>

<specifics>
## Specific Ideas

- Issue #48 specifically names the error class `CRSMismatchError` — match that name exactly
- The `coordinate_units: "degrees"` annotation in variogram_diagnostics directly addresses the STATE.md blocker about range units
- HARD-04 is a pure packaging change — no behavior changes to the pipeline

</specifics>

<deferred>
## Deferred Ideas

- UTM reprojection for variogram range in metres — captured as GEO-03 in REQUIREMENTS.md (v2)
- `uncertainty_samples` minimum validation / warning — minor; Claude's discretion on implementation

</deferred>

---

*Phase: 01-foundation-hardening*
*Context gathered: 2026-03-29*
