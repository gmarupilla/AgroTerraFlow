"""Deterministic build fingerprinting.

Vendored (deliberately, not imported) from ``terraflow/core/run_identity.py`` so this
package stays spin-out independent of TerraFlow. The shapely/ROI geometry parts of the
original are dropped — the benchmark fingerprints a config dict plus input file hashes.

The fingerprint is content-addressable only: config canonical JSON + per-input
SHA-256 and byte size. File ``mtime`` is intentionally excluded so the fingerprint is
stable across filesystem copies and CI re-checks.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path


def canonicalize_config(config_dict: dict) -> bytes:
    """Return canonical JSON bytes for a config dict (sorted keys, tight separators)."""
    canonical_json = json.dumps(
        config_dict,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return canonical_json.encode("utf-8")


def fingerprint_file(path: str | Path, chunk_size: int = 8_388_608) -> dict:
    """Compute a streaming SHA-256 for a file and return its fingerprint info."""
    file_path = Path(path).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    stat = file_path.stat()
    return {
        "path": str(file_path),
        "sha256": hasher.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime": int(stat.st_mtime),
    }


def compute_build_fingerprint(config_dict: dict, input_fingerprints: list[dict]) -> str:
    """Compute a deterministic build fingerprint for the benchmark assembly.

    Derived exclusively from content-addressable components:
    - canonical config JSON (sorted keys)
    - per-input SHA-256 + byte-size (``mtime`` excluded)

    Returns a URL-safe base64 digest (no padding).
    """
    config_hash = hashlib.sha256(canonicalize_config(config_dict)).hexdigest()

    # mtime deliberately excluded: fingerprint must be content-based only.
    inputs_payload = [{"sha256": fp["sha256"], "size_bytes": fp["size_bytes"]} for fp in input_fingerprints]
    inputs_payload.sort(key=lambda item: (item["sha256"], item["size_bytes"]))

    payload = {"config": config_hash, "inputs": inputs_payload}
    payload_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    digest = hashlib.sha256(payload_bytes).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
