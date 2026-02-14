# Run Identity

Every pipeline execution is identified by a deterministic `run_fingerprint` computed as:

```
run_fingerprint = sha256({
	config: sha256(canonical_config),
	roi: roi_hash,
	inputs: [sha256, size_bytes, mtime]
})
```

Where:

- **canonical_config** is the normalized configuration with sorted keys.
- **roi_hash** represents the ROI geometry (bbox or GeoJSON polygon).
- **input_fingerprints** capture file hashes, sizes, and mtimes for inputs.

## Why deterministic fingerprints matter

- Enables reproducible runs and artifact comparisons.
- Makes outputs immutable by default.
- Simplifies caching and downstream automation.

When any of the components changes, the fingerprint changes, producing a new run directory.
