# Artifact Contract

Each run writes a consistent set of artifacts under:

```
runs/<run_fingerprint>/
```

## Required outputs

| File | Purpose |
| --- | --- |
| `features.parquet` | Tabular features generated for each sampled cell. |
| `manifest.json` | Run metadata including configuration and input fingerprints. |
| `report.json` | Summary statistics and model outputs for quick inspection. |

## Notes for v0.1

- Artifacts are **local-only**; there is no remote storage integration yet.
- The run directory is treated as immutable once written.
- Downstream tooling should rely on `manifest.json` for provenance.
