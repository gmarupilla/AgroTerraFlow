# Run Identity

Every pipeline execution is identified by a deterministic `run_fingerprint`. In v0.1 it is computed as:

```
run_fingerprint = hash(canonical_config + roi_hash + input_fingerprints)
```

Where:

- **canonical_config** is the normalized configuration with sorted keys and resolved paths.
- **roi_hash** represents the ROI geometry (bbox in v0.1).
- **input_fingerprints** capture file hashes for raster and climate inputs.

## Why deterministic fingerprints matter

- Enables reproducible runs and artifact comparisons.
- Makes outputs immutable by default.
- Simplifies cacheing and downstream automation.

When any of the components changes, the fingerprint changes, producing a new run directory.
