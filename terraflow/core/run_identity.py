from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from shapely import wkb
from shapely.geometry import box, shape
from shapely.ops import unary_union


def canonicalize_config(config_dict: dict) -> bytes:
    """Return canonical JSON bytes for a parsed YAML config dict."""
    canonical_json = json.dumps(
        config_dict,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return canonical_json.encode("utf-8")


def fingerprint_file(path: str, chunk_size: int = 8_388_608) -> dict:
    """Compute a streaming SHA256 for a file and return its fingerprint info."""
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


def _normalize_geometry(geom) -> Any:
    if not geom.is_valid:
        geom = geom.buffer(0)

    try:
        from shapely import set_precision as _set_precision
    except ImportError:
        _set_precision = None

    if _set_precision is not None:
        geom = _set_precision(geom, grid_size=1e-7)

    try:
        from shapely import normalize as _normalize
    except ImportError:
        _normalize = None

    if _normalize is not None:
        geom = _normalize(geom)

    return geom


def _geometry_to_wkb(geom) -> bytes:
    try:
        return wkb.dumps(
            geom,
            hex=False,
            output_dimension=2,
            rounding_precision=7,
        )
    except TypeError:
        return wkb.dumps(geom, hex=False, output_dimension=2)


def _shape_geojson(geojson_obj: dict) -> Any:
    obj_type = geojson_obj.get("type")
    if obj_type == "Feature":
        geometry = geojson_obj.get("geometry")
        if geometry is None:
            raise ValueError("GeoJSON Feature is missing geometry")
        return shape(geometry)
    if obj_type == "FeatureCollection":
        features = geojson_obj.get("features") or []
        geometries = [
            shape(feature.get("geometry"))
            for feature in features
            if feature.get("geometry") is not None
        ]
        if not geometries:
            raise ValueError("GeoJSON FeatureCollection has no geometries")
        return unary_union(geometries)
    if obj_type in {"Polygon", "MultiPolygon"}:
        return shape(geojson_obj)

    raise ValueError(f"Unsupported GeoJSON type: {obj_type}")


def hash_roi_geometry(roi_geojson_path: str | dict) -> str:
    """Hash ROI geometry from a GeoJSON path or bbox dict."""
    if isinstance(roi_geojson_path, dict):
        required = {"xmin", "ymin", "xmax", "ymax"}
        if not required.issubset(roi_geojson_path):
            raise ValueError("ROI bbox is missing required bounds")
        geom = box(
            roi_geojson_path["xmin"],
            roi_geojson_path["ymin"],
            roi_geojson_path["xmax"],
            roi_geojson_path["ymax"],
        )
    else:
        geojson_path = Path(roi_geojson_path).resolve()
        if not geojson_path.exists():
            raise FileNotFoundError(f"ROI GeoJSON file not found: {geojson_path}")
        with geojson_path.open("r", encoding="utf-8") as handle:
            geojson_obj = json.load(handle)
        geom = _shape_geojson(geojson_obj)

    geom = _normalize_geometry(geom)
    wkb_bytes = _geometry_to_wkb(geom)
    return hashlib.sha256(wkb_bytes).hexdigest()


def compute_run_fingerprint(
    config_dict: dict,
    roi_hash: str,
    input_fingerprints: list[dict],
) -> str:
    """Compute a deterministic run fingerprint for the given inputs.

    The fingerprint is derived exclusively from content-addressable components:
    - canonical config JSON (sorted keys)
    - ROI geometry hash (WKB of normalised shapely geometry)
    - per-input SHA-256 + byte-size (mtime is intentionally excluded so the
      fingerprint is stable across filesystem copies and CI re-checks)
    """
    config_hash = hashlib.sha256(canonicalize_config(config_dict)).hexdigest()

    # mtime is deliberately excluded: fingerprint must be content-based only.
    inputs_payload = [
        {
            "sha256": fp["sha256"],
            "size_bytes": fp["size_bytes"],
        }
        for fp in input_fingerprints
    ]
    inputs_payload.sort(key=lambda item: (item["sha256"], item["size_bytes"]))

    payload = {
        "config": config_hash,
        "roi": roi_hash,
        "inputs": inputs_payload,
    }
    payload_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    digest = hashlib.sha256(payload_bytes).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


_GEOAI_REQUIRED_MODEL_KEYS = frozenset(
    {"name", "weights_sha256", "geoai_major_minor"}
)
_GEOAI_OPTIONAL_MODEL_KEYS = frozenset({"device", "torch_major_minor"})
_GEOAI_INPUT_KEYS = frozenset({"sha256", "size_bytes"})


def compute_geoai_fingerprint(
    config_dict: dict,
    input_fingerprints: list[dict],
    model_metadata: dict,
) -> str:
    """Deterministic fingerprint for a ``terraflow geoai`` engine run.

    ``model_metadata`` must contain:
      - ``name`` (str): model identifier
      - ``weights_sha256`` (str): pretrained-weights hash
      - ``geoai_major_minor`` (str): e.g. ``"0.1"`` (patch deliberately
        excluded so bug-fix releases of ``geoai`` do not invalidate caches).

    And may optionally contain:
      - ``device`` (str): ``"cpu"`` / ``"cuda"`` / ``"mps"`` — different devices
        yield different floating-point and cuDNN-kernel results.
      - ``torch_major_minor`` (str): e.g. ``"2.3"`` — minor torch bumps can
        shift kernel implementations.

    Only ``major.minor`` of the ``geoai`` library is mixed into the hash:
    patch bumps almost never change model outputs, and silent output drift
    from a real weight swap is already caught by ``weights_sha256``. Using
    the full version here would needlessly invalidate the cache on every
    bug-fix release.

    ``input_fingerprints`` entries must be dicts with exactly the keys
    ``sha256`` and ``size_bytes``; extra or missing keys raise ``ValueError``.
    """
    missing_model = _GEOAI_REQUIRED_MODEL_KEYS - model_metadata.keys()
    if missing_model:
        raise ValueError(
            f"model_metadata missing required keys: {sorted(missing_model)}"
        )
    unknown_model = (
        model_metadata.keys()
        - _GEOAI_REQUIRED_MODEL_KEYS
        - _GEOAI_OPTIONAL_MODEL_KEYS
    )
    if unknown_model:
        raise ValueError(
            f"model_metadata has unexpected keys: {sorted(unknown_model)}"
        )

    for idx, fp in enumerate(input_fingerprints):
        if set(fp.keys()) != _GEOAI_INPUT_KEYS:
            raise ValueError(
                f"input_fingerprints[{idx}] must have exactly keys "
                f"{sorted(_GEOAI_INPUT_KEYS)}, got {sorted(fp.keys())}"
            )

    config_hash = hashlib.sha256(canonicalize_config(config_dict)).hexdigest()

    inputs_payload = sorted(
        (
            {"sha256": fp["sha256"], "size_bytes": fp["size_bytes"]}
            for fp in input_fingerprints
        ),
        key=lambda item: (item["sha256"], item["size_bytes"]),
    )

    model_payload = {
        "name": model_metadata["name"],
        "weights_sha256": model_metadata["weights_sha256"],
        "geoai_major_minor": model_metadata["geoai_major_minor"],
    }
    for opt_key in _GEOAI_OPTIONAL_MODEL_KEYS:
        if opt_key in model_metadata:
            model_payload[opt_key] = model_metadata[opt_key]

    payload = {
        "config": config_hash,
        "inputs": inputs_payload,
        "model": model_payload,
    }
    payload_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    digest = hashlib.sha256(payload_bytes).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
