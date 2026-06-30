---
title: Run Identity & Fingerprinting
description: How TerraFlow computes deterministic run fingerprints from config, ROI, and input file hashes to guarantee reproducibility.
icon: material/fingerprint
tags:
  - Architecture
  - Reproducibility
  - Reference
---

# Run Identity

Every pipeline execution is identified by a deterministic `run_fingerprint`
computed as a base64url-encoded SHA-256:

```
run_fingerprint = base64url( sha256({
    config: sha256( canonical_config_json ),
    roi:    sha256( normalized_geometry_WKB ),
    inputs: [ { sha256, size_bytes } … ]   ← sorted, mtime excluded
}) )
```

### Why mtime is excluded

File modification timestamps (`mtime`) are **intentionally not part of the
fingerprint hash**.  Including them would make the fingerprint non-deterministic
across filesystem copies, CI clones, and archive extractions — defeating the
purpose of content-based identity.  `mtime` is recorded in `manifest.json`
for human-readable provenance tracing only.

---

## Components

### 1. Canonical config

The raw YAML config dict is serialised to JSON with **sorted keys** and
minimal separators (no extra whitespace).  This ensures the hash is stable
regardless of key insertion order in the source YAML.

```python
json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
```

### 2. ROI geometry hash

The region of interest is canonicalised using Shapely:

1. Repair invalid geometries (`buffer(0)`).
2. Snap coordinates to a 1e-7° grid (`set_precision`).
3. Normalise vertex order (`normalize`).
4. Serialise to WKB (2D, 7 decimal places).
5. SHA-256 the WKB bytes.

This means **the same geographic polygon expressed in different vertex orders
produces the same hash**.

Supported ROI forms in the YAML config:

| YAML form | Behaviour |
|---|---|
| `roi.type: bbox` with `xmin/ymin/xmax/ymax` | Converts bbox to Shapely `box`, then hashes |
| `roi.path: path/to/roi.geojson` | Loads GeoJSON Polygon / MultiPolygon / Feature / FeatureCollection and hashes |

### 3. Input file fingerprints

Each input file (raster, climate CSV) is read in 8 MiB chunks and its
SHA-256 digest and byte-size are recorded.  These are sorted by
`(sha256, size_bytes)` before hashing so **input order in the config does
not affect the fingerprint**.

---

## Run directory

The run directory is created at:

```
<output_dir>/runs/<run_fingerprint>/
```

If all three required artifacts (`features.parquet`, `manifest.json`,
`report.json`) already exist in that directory when the pipeline is
invoked with the same inputs, the pipeline returns the cached result
without re-scoring (**no-op rerun**).

---

## Reproducibility guarantees

| Claim | Mechanism |
|---|---|
| Same config + same ROI + same input files → same fingerprint | Content-based SHA-256, mtime excluded |
| Same fingerprint → same run directory path | Deterministic base64url encoding |
| Same run directory → same `features.parquet` schema | Schema version frozen in Parquet metadata |
| Different input content → different fingerprint | SHA-256 collision probability negligible |
| Filesystem copy / CI clone → same fingerprint | mtime excluded from hash |
| Random cell sampling reproducible across runs | `numpy.random.default_rng(seed)` initialised with first 64 bits of `sha256(run_fingerprint)` (`pipeline.py`) |

---

## Limitations

- The fingerprint covers **declared** input files (raster, climate CSV, ROI
  GeoJSON) only.  If a pipeline step reads additional files not listed in the
  config, those are not tracked.
