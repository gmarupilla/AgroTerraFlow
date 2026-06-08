"""GeoAI engine adapter — wraps `geoai-py` for fields/landcover/canopy inference.

Each public runner (`run_fields`, `run_landcover`, `run_canopy`):
- Requires the optional `[geoai]` extra (`geoai-py`, `torch`).
- Validates that ``config.geoai.engine`` matches the runner.
- Computes a deterministic ``geoai_fingerprint`` over config + raster hash + model
  metadata (incl. device + torch version, so identical inputs on different
  devices map to different cache directories).
- Writes artifacts to ``<output_dir>/runs/<geoai_fingerprint>/geoai/``.
- Always writes ``geoai_manifest.json`` + ``report.json``.
- Seeds ``torch.manual_seed`` from the fingerprint for reproducibility.
- Skips inference on a cache hit (manifest already present).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict

try:
    import geoai
    import torch

    _GEOAI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via patch in tests
    geoai = None
    torch = None
    _GEOAI_AVAILABLE = False

from .config import PipelineConfig, build_config, load_config_dict
from .core.run_identity import compute_geoai_fingerprint, fingerprint_file
from .pipeline import _atomic_write_text
from .utils import logger

_INSTALL_HINT = (
    "geoai-py and torch are required for the `terraflow geoai` engine. "
    "Install with: pip install terraflow-agro[geoai]"
)

# Pretrained-weight identifiers per engine. SHA values are placeholders pinned
# to the geoai-py bundled checkpoints; #94 wires in real digests.
_MODEL_NAME: Dict[str, str] = {
    "fields": "ftw-v1",
    "landcover": "landcover-v1",
    "canopy": "canopy-v1",
}
_WEIGHTS_SHA: Dict[str, str] = {
    "fields": "0" * 64,
    "landcover": "0" * 64,
    "canopy": "0" * 64,
}


def _require_geoai() -> None:
    if not _GEOAI_AVAILABLE:
        raise ImportError(_INSTALL_HINT)


def _device() -> str:
    if not _GEOAI_AVAILABLE:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return parts[0] if parts else "0"


def _torch_major_minor() -> str:
    if not _GEOAI_AVAILABLE:
        return "0.0"
    return _major_minor(getattr(torch, "__version__", "0.0"))


def _geoai_major_minor() -> str:
    if not _GEOAI_AVAILABLE:
        return "0.0"
    return _major_minor(getattr(geoai, "__version__", "0.0"))


def _seed_torch(fingerprint: str) -> None:
    if not _GEOAI_AVAILABLE:
        return
    seed = int.from_bytes(fingerprint[:8].encode("ascii"), "big") % (2**31)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _model_metadata(engine: str) -> Dict[str, str]:
    return {
        "name": _MODEL_NAME[engine],
        "weights_sha256": _WEIGHTS_SHA[engine],
        "geoai_major_minor": _geoai_major_minor(),
        "device": _device(),
        "torch_major_minor": _torch_major_minor(),
    }


def _resolve_input_paths(config_path: Path, config_dict: dict) -> None:
    """Resolve relative raster_path / output_dir against config dir (in place)."""
    config_dir = config_path.resolve().parent
    for key in ("raster_path", "output_dir"):
        raw = config_dict.get(key)
        if raw is None:
            continue
        p = Path(str(raw))
        if not p.is_absolute():
            config_dict[key] = str((config_dir / p).resolve())


def _run(
    engine: str,
    runner_fn: Callable[[PipelineConfig, Path], None],
    config_path: Path | str,
) -> Path:
    _require_geoai()

    config_path = Path(config_path)
    config_dict = load_config_dict(config_path)
    _resolve_input_paths(config_path, config_dict)
    cfg = build_config(config_dict)

    if cfg.geoai is None:
        raise ValueError(
            "Config has no `geoai:` block — required for the geoai engine."
        )
    if cfg.geoai.engine != engine:
        raise ValueError(
            f"Config `geoai.engine={cfg.geoai.engine!r}` does not match "
            f"runner `{engine!r}`."
        )

    raster_fp = fingerprint_file(str(cfg.raster_path))
    input_fingerprints = [
        {"sha256": raster_fp["sha256"], "size_bytes": raster_fp["size_bytes"]}
    ]
    model_meta = _model_metadata(engine)

    fingerprint = compute_geoai_fingerprint(config_dict, input_fingerprints, model_meta)
    run_dir = Path(cfg.output_dir) / "runs" / fingerprint / "geoai"
    manifest_path = run_dir / "geoai_manifest.json"

    if manifest_path.exists():
        logger.info(f"geoai cache hit — {run_dir}")
        return run_dir

    run_dir.mkdir(parents=True, exist_ok=True)
    _seed_torch(fingerprint)

    start = time.perf_counter()
    runner_fn(cfg, run_dir)
    elapsed = time.perf_counter() - start

    _atomic_write_text(
        manifest_path,
        json.dumps(
            {
                "engine": engine,
                "geoai_fingerprint": fingerprint,
                "model": model_meta,
                "inputs": input_fingerprints,
                "config": config_dict,
                "roi_applied": False,
                "roi_note": (
                    "ROI clipping deferred in v0.4.0 — runner processed the "
                    "full raster. Bake ROI into the input upstream if needed."
                ),
            },
            sort_keys=True,
            indent=2,
            default=str,
        ),
    )
    _atomic_write_text(
        run_dir / "report.json",
        json.dumps(
            {
                "engine": engine,
                "duration_s": round(elapsed, 6),
                "device": model_meta["device"],
                "torch_major_minor": model_meta["torch_major_minor"],
                "deterministic": True,
            },
            sort_keys=True,
            indent=2,
        ),
    )

    return run_dir


# ---------------------------------------------------------------------------
# Engine-specific runner bodies. Each writes its declared artifact set into
# *run_dir*. Real geoai-py calls land in #94 — for now bodies are minimal
# placeholders that tests monkey-patch.
# ---------------------------------------------------------------------------


def _do_fields(cfg: PipelineConfig, run_dir: Path) -> None:  # pragma: no cover
    _require_geoai()
    raise NotImplementedError("geoai.ftw integration lands in #94")


def _do_landcover(cfg: PipelineConfig, run_dir: Path) -> None:  # pragma: no cover
    _require_geoai()
    raise NotImplementedError("geoai.classify integration lands in #94")


def _do_canopy(cfg: PipelineConfig, run_dir: Path) -> None:  # pragma: no cover
    _require_geoai()
    raise NotImplementedError("geoai.canopy integration lands in #94")


def run_fields(config_path: Path | str) -> Path:
    """Run field-boundary detection. Returns the run directory."""
    return _run("fields", _do_fields, config_path)


def run_landcover(config_path: Path | str) -> Path:
    """Run landcover classification. Returns the run directory."""
    return _run("landcover", _do_landcover, config_path)


def run_canopy(config_path: Path | str) -> Path:
    """Run canopy-height regression. Returns the run directory."""
    return _run("canopy", _do_canopy, config_path)


__all__ = [
    "run_fields",
    "run_landcover",
    "run_canopy",
    "_require_geoai",
    "_GEOAI_AVAILABLE",
]
