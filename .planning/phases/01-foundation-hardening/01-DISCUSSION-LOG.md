# Phase 1: Foundation Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 01-foundation-hardening
**Areas discussed:** CRS error type, Variogram units, plotly guard

---

## CRS Error Type

| Option | Description | Selected |
|--------|-------------|----------|
| Custom CRSMismatchError | New class inheriting ValueError; carries both CRS strings as attributes | ✓ |
| Plain ValueError | raise ValueError with formatted message; no new API surface | |
| pyproj.exceptions.CRSError | Re-raise pyproj's own error; semantically wrong for a mismatch | |

**User's choice:** Custom `CRSMismatchError(ValueError)`
**Notes:** Issue #48 names the class explicitly — match that name.

---

## Variogram Range Units

| Option | Description | Selected |
|--------|-------------|----------|
| Document units in report.json | Add `coordinate_units: 'degrees'` note in variogram block | ✓ |
| Reproject to UTM before fitting | Convert to metres; cleaner but adds complexity and UTM zone concerns | |
| Both: degrees now, UTM as v2 option | Ship degrees now; UTM as configurable option in v2 (GEO-03) | |

**User's choice:** Document units in report.json
**Notes:** This closes the STATE.md blocker directly. UTM option stays in GEO-03 backlog.

---

## plotly Import Guard

| Option | Description | Selected |
|--------|-------------|----------|
| ImportError with install hint | Guard inside each viz function; raise ImportError with pip install instruction | ✓ |
| Return None silently | Return None if plotly missing; hides the dep, harder to debug | |

**User's choice:** ImportError with install hint
**Notes:** Guard at function call time, not module level.

---

## Claude's Discretion

- Exact trove classifiers — follow scientific Python conventions
- `CRSMismatchError` location (exceptions.py vs geo.py) — Claude decides based on API surface
- `uncertainty_samples=1` behavior — warn or silent; Claude's call
