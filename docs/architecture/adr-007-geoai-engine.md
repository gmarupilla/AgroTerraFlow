# ADR-007: GeoAI Engine Adapter

**Status:** Accepted
**Date:** 2026-06-08

## Context

TerraFlow's core pipeline (`terraflow run`) scores agricultural suitability from a
land-cover raster and climate CSV, but it does not directly handle the upstream
remote-sensing tasks needed to produce that raster — most notably field-boundary
delineation, landcover classification, and canopy-height regression. Practitioners
either pre-compute these layers in QGIS / Google Earth Engine, or stitch together
ad-hoc Python notebooks per dataset.

The open-source [`opengeos/geoai`](https://github.com/opengeos/geoai) project
(Wu 2026, JOSS-pending) wraps a curated set of foundation and segmentation models
behind a uniform Python API. Three of its capabilities map directly onto
TerraFlow's existing data contract:

| GeoAI capability | TerraFlow runner | Output layer |
|---|---|---|
| Field-boundary segmentation (FTW-v1) | `terraflow geoai fields` | GeoJSON polygons + per-field statistics |
| Landcover classification | `terraflow geoai landcover` | Categorical raster aligned to the input grid |
| Canopy-height regression | `terraflow geoai canopy` | Continuous raster in metres |

Integrating these as **first-class TerraFlow subcommands** — rather than asking
users to script the calls themselves — preserves the project's two non-negotiable
guarantees: reproducible-by-fingerprint outputs and a uniform CLI surface.

## Decision

We add a thin adapter module, `terraflow.geoai_engine`, that:

1. **Lives behind an optional `[geoai]` extra.** Installing
   `pip install "terraflow-agro[geoai]"` pulls in `geoai-py` and `torch`; the
   base install stays lightweight. The adapter raises a clear `ImportError`
   with the install hint when the extra is missing, so the base CLI continues
   to work and tests do not need ML dependencies on the default CI matrix.
2. **Exposes three orchestrators** — `run_fields`, `run_landcover`, `run_canopy` —
   each taking a config path and returning the run directory. A single
   private `_run(engine, runner_fn, config_path)` helper handles validation,
   fingerprinting, caching, and artifact writing; engine-specific bodies are
   thin and replaceable.
3. **Reuses the existing fingerprinting machinery.** The new
   `compute_geoai_fingerprint(config, inputs, model_metadata)` in
   `terraflow.core.run_identity` hashes the canonicalized config, sorted input
   file hashes, and a small `model_metadata` payload (name, weights SHA,
   library major.minor, device, torch major.minor). Same inputs → same
   fingerprint → cached run is reused; different `device` (cpu / cuda / mps)
   or torch minor bump yields a different cache directory, matching the
   semantics already established for `compute_run_fingerprint`.
4. **Writes a documented artifact set.** Every GeoAI run produces
   `<output_dir>/runs/<geoai_fingerprint>/geoai/geoai_manifest.json` and
   `report.json` (engine, duration, device, torch version, deterministic
   flag). Engine bodies write their declared layer (`fields.geojson` +
   `field_stats.parquet`, `landcover.tif`, `canopy.tif`).
5. **Pins `chip_size` to powers of two ≥ 32.** Most segmentation backbones
   downsample by 32 internally; `GeoAIConfig` enforces this in Pydantic so
   misconfigured inferences fail loudly at config-load time rather than
   silently in the middle of a long run.
6. **Seeds `torch.manual_seed` from the fingerprint.** Identical inputs on
   the same device produce bit-identical outputs in the deterministic-kernel
   path; CUDA non-determinism is documented as the known limit (see
   [Reproducibility](../reproducibility.md)).

## Alternatives considered

- **Vendor `geoai-py` directly into TerraFlow.** Rejected. Torch + geoai-py
  weigh hundreds of megabytes; bundling them would push the base wheel into a
  size class that breaks `pip install terraflow-agro` for users who only want
  the climate pipeline.
- **Spin off a separate `terraflow-geoai` package.** Considered. Postponed:
  the engine orchestration (config validation, fingerprinting, manifest
  schema) is identical to the rest of TerraFlow, so duplicating it across
  two packages costs more than the optional-extra split.
- **Treat GeoAI as a notebook-only example.** Rejected. Reproducibility and
  caching demand the same fingerprinted-run directory layout used elsewhere
  in TerraFlow, which is the whole point of having a CLI orchestrator.

## Consequences

- Users who want the GeoAI engines opt in via `pip install terraflow-agro[geoai]`.
  Base install stays unchanged.
- A new opt-in CI workflow (`.github/workflows/geoai-integration.yml`) installs
  the extra and runs the GeoAI test subset only when paths under
  `terraflow/geoai_engine.py` or `tests/test_geoai_engine.py` change; baseline
  CI does not pay the torch-install cost.
- ROI clipping is **deliberately deferred** — runners process the full raster
  for v0.4.0 and rely on the ROI being baked into the input. The manifest
  records `roi_applied: false` and a `roi_note` so consumers do not
  silently assume ROI was honoured. A follow-up issue will add native ROI
  clipping to the geoai runners with a regression test.
- Real pretrained-weight SHA-256 digests are placeholders until the weight
  registry is wired up alongside `geoai-py >= 0.2`.
