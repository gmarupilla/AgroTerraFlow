# GeoAI Engines

TerraFlow ships three optional remote-sensing runners that wrap
[`opengeos/geoai`](https://github.com/opengeos/geoai):

| Subcommand | Purpose | Output artifact set |
|---|---|---|
| `terraflow geoai fields` | Field-boundary detection (FTW-v1) | `fields.geojson`, `field_stats.parquet` |
| `terraflow geoai landcover` | Landcover classification | `landcover.tif` |
| `terraflow geoai canopy` | Canopy-height regression | `canopy.tif` |

Each runner writes its outputs to
`<output_dir>/runs/<geoai_fingerprint>/geoai/` alongside a
`geoai_manifest.json` (config snapshot, input hashes, model metadata) and a
`report.json` (duration, device, deterministic flag).

## Install the extra

The GeoAI engines depend on `geoai-py` and `torch`, which are *not* installed
with the base package:

```bash
pip install "terraflow-agro[geoai]"
```

The runners auto-detect the best available device at runtime (CUDA, Apple
Silicon MPS, then CPU). The device name is folded into the fingerprint, so
re-running the same config on a different device yields a different cache
directory — same inputs on the same device always reuse the cached run.

## Configure

Add a `geoai:` block to your existing TerraFlow YAML config. All fields are
validated by `GeoAIConfig` (Pydantic v2):

```yaml
geoai:
  engine: fields            # one of: fields | landcover | canopy
  chip_size: 256            # power of two, >= 32; backbone strides force this
  confidence_threshold: 0.5 # 0.0 .. 1.0
  batch_size: 8
```

The selected `engine` must match the runner — `terraflow geoai landcover`
with `engine: fields` raises a `ValueError` at config-load time.

## Run

```bash
# Field-boundary detection
terraflow geoai fields -c configs/my-region.yml

# Landcover classification
terraflow geoai landcover -c configs/my-region.yml

# Canopy-height regression
terraflow geoai canopy -c configs/my-region.yml
```

Each command prints the run directory on success:

```
GeoAI fields complete: /work/outputs/runs/abc123…/geoai
```

## Caching and reproducibility

Runners compute a `geoai_fingerprint` from:

- The canonicalized YAML config
- SHA-256 hashes + sizes of every input raster
- A `model_metadata` payload: `name`, `weights_sha256`, `geoai_major_minor`,
  `device`, `torch_major_minor`

If a manifest already exists at the fingerprinted run directory, the runner
returns immediately and skips inference. To force re-inference, change a
config value (e.g. nudge `confidence_threshold`) or delete the run directory.

PyTorch `manual_seed` is set deterministically from the fingerprint before
every run, so the seeded code path is reproducible — see
[Reproducibility](reproducibility.md) for the full guarantees and the known
non-deterministic CUDA kernels.

## Python API

```python
from terraflow import geoai_engine

run_dir = geoai_engine.run_fields("configs/my-region.yml")
print((run_dir / "field_stats.parquet").read_bytes()[:32])
```

The orchestrators are pure Python; they can be called from notebooks,
Airflow DAGs, or any other host that imports `terraflow`.

## See also

- [ADR-007: GeoAI Engine Adapter](architecture/adr-007-geoai-engine.md) — design rationale
- [Configuration schema](config/schema.md) — `GeoAIConfig` field reference
- [Reproducibility](reproducibility.md) — what the fingerprint covers
- [Demo notebook](notebooks/06_geoai_engine.ipynb) — end-to-end walkthrough on synthetic data
