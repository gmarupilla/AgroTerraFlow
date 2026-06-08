"""Mocked-engine tests for ``terraflow.geoai_engine`` (issue #92).

The optional ``[geoai]`` extra is *not* installed in baseline CI, so every test
patches ``_GEOAI_AVAILABLE`` to True and replaces the torch / geoai-touching
helpers with no-ops. Engine bodies are monkey-patched to write the documented
artifact set; this lets us cover orchestration (config validation, fingerprinting,
caching, manifest/report) without any heavy ML deps.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Callable, Tuple

import pytest

from terraflow import geoai_engine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_config(
    tmp_path: Path,
    raster_path: Path,
    engine: str,
    confidence_threshold: float = 0.5,
    filename: str | None = None,
) -> Path:
    cfg = textwrap.dedent(f"""
        raster_path: "{raster_path}"
        climate_csv: "{tmp_path / 'climate.csv'}"
        output_dir: "{tmp_path / 'outputs'}"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 1.0
          ymax: 1.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        geoai:
          engine: "{engine}"
          chip_size: 64
          confidence_threshold: {confidence_threshold}
          batch_size: 2
        """)
    cfg_path = tmp_path / (filename or f"cfg_{engine}.yml")
    cfg_path.write_text(cfg, encoding="utf-8")
    return cfg_path


@pytest.fixture
def stub_geoai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the [geoai] extra is installed; no-op torch helpers."""
    monkeypatch.setattr(geoai_engine, "_GEOAI_AVAILABLE", True)
    monkeypatch.setattr(geoai_engine, "_seed_torch", lambda fp: None)
    monkeypatch.setattr(geoai_engine, "_device", lambda: "cpu")
    monkeypatch.setattr(geoai_engine, "_torch_major_minor", lambda: "2.0")
    monkeypatch.setattr(geoai_engine, "_geoai_major_minor", lambda: "0.1")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_require_geoai_raises_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(geoai_engine, "_GEOAI_AVAILABLE", False)
    with pytest.raises(ImportError, match=r"pip install terraflow-agro\[geoai\]"):
        geoai_engine._require_geoai()


def test_helpers_short_circuit_without_geoai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the [geoai] extra installed, helpers return safe defaults."""
    monkeypatch.setattr(geoai_engine, "_GEOAI_AVAILABLE", False)
    assert geoai_engine._device() == "cpu"
    assert geoai_engine._torch_major_minor() == "0.0"
    assert geoai_engine._geoai_major_minor() == "0.0"
    geoai_engine._seed_torch("abcd1234")  # no-op, must not raise


@pytest.mark.parametrize(
    "version, expected",
    [("2.3.1", "2.3"), ("0.1", "0.1"), ("3", "3")],
)
def test_major_minor_helper(version: str, expected: str) -> None:
    assert geoai_engine._major_minor(version) == expected


def test_runner_rejects_wrong_engine_in_config(
    tmp_path: Path, synthetic_raster: Path, stub_geoai: None
) -> None:
    cfg_path = _write_config(tmp_path, synthetic_raster, engine="landcover")
    with pytest.raises(ValueError, match="does not match"):
        geoai_engine.run_fields(cfg_path)


def test_runner_rejects_missing_geoai_block(
    tmp_path: Path, synthetic_raster: Path, stub_geoai: None
) -> None:
    cfg = textwrap.dedent(f"""
        raster_path: "{synthetic_raster}"
        climate_csv: "{tmp_path / 'climate.csv'}"
        output_dir: "{tmp_path / 'outputs'}"
        roi:
          type: "bbox"
          xmin: 0.0
          ymin: 0.0
          xmax: 1.0
          ymax: 1.0
        model_params:
          v_min: 0.0
          v_max: 1.0
          t_min: 0.0
          t_max: 40.0
          r_min: 0.0
          r_max: 300.0
          w_v: 0.4
          w_t: 0.3
          w_r: 0.3
        """)
    cfg_path = tmp_path / "cfg_no_geoai.yml"
    cfg_path.write_text(cfg, encoding="utf-8")
    with pytest.raises(ValueError, match="no `geoai:` block"):
        geoai_engine.run_fields(cfg_path)


def _stub_runner_factory(
    artifacts: Tuple[str, ...],
) -> Tuple[Callable[[object, Path], None], list[Path]]:
    """Return ``(runner_body, calls)`` — calls list records each invocation."""
    calls: list[Path] = []

    def _stub(_cfg: object, run_dir: Path) -> None:
        calls.append(run_dir)
        for name in artifacts:
            (run_dir / name).write_text("", encoding="utf-8")

    return _stub, calls


@pytest.mark.parametrize(
    "engine, runner_attr, public_fn, artifacts",
    [
        (
            "fields",
            "_do_fields",
            "run_fields",
            ("fields.geojson", "field_stats.parquet"),
        ),
        (
            "landcover",
            "_do_landcover",
            "run_landcover",
            ("landcover.tif", "landcover_proba.tif", "class_fractions.json"),
        ),
        (
            "canopy",
            "_do_canopy",
            "run_canopy",
            ("canopy_height.tif", "canopy_stats.json"),
        ),
    ],
)
def test_runner_writes_artifacts(
    tmp_path: Path,
    synthetic_raster: Path,
    stub_geoai: None,
    monkeypatch: pytest.MonkeyPatch,
    engine: str,
    runner_attr: str,
    public_fn: str,
    artifacts: Tuple[str, ...],
) -> None:
    stub, calls = _stub_runner_factory(artifacts)
    monkeypatch.setattr(geoai_engine, runner_attr, stub)

    cfg_path = _write_config(tmp_path, synthetic_raster, engine=engine)
    run_dir = getattr(geoai_engine, public_fn)(cfg_path)

    assert run_dir.parent.parent == tmp_path / "outputs" / "runs"
    for name in artifacts:
        assert (run_dir / name).exists(), f"missing artifact {name}"

    manifest = json.loads((run_dir / "geoai_manifest.json").read_text())
    assert manifest["engine"] == engine
    assert manifest["model"]["device"] == "cpu"
    assert manifest["model"]["torch_major_minor"] == "2.0"
    assert manifest["model"]["geoai_major_minor"] == "0.1"
    assert len(manifest["inputs"]) == 1
    assert set(manifest["inputs"][0].keys()) == {"sha256", "size_bytes"}

    report = json.loads((run_dir / "report.json").read_text())
    assert report["engine"] == engine
    assert report["device"] == "cpu"
    assert report["deterministic"] is True
    assert "duration_s" in report

    assert len(calls) == 1


def test_runner_cache_hit_skips_inference(
    tmp_path: Path,
    synthetic_raster: Path,
    stub_geoai: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub, calls = _stub_runner_factory(("fields.geojson", "field_stats.parquet"))
    monkeypatch.setattr(geoai_engine, "_do_fields", stub)

    cfg_path = _write_config(tmp_path, synthetic_raster, engine="fields")
    first = geoai_engine.run_fields(cfg_path)
    second = geoai_engine.run_fields(cfg_path)

    assert first == second
    assert len(calls) == 1


def test_threshold_bump_produces_new_fingerprint(
    tmp_path: Path,
    synthetic_raster: Path,
    stub_geoai: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub, calls = _stub_runner_factory(("fields.geojson", "field_stats.parquet"))
    monkeypatch.setattr(geoai_engine, "_do_fields", stub)

    cfg_a = _write_config(
        tmp_path,
        synthetic_raster,
        engine="fields",
        confidence_threshold=0.5,
        filename="cfg_a.yml",
    )
    cfg_b = _write_config(
        tmp_path,
        synthetic_raster,
        engine="fields",
        confidence_threshold=0.9,
        filename="cfg_b.yml",
    )

    dir_a = geoai_engine.run_fields(cfg_a)
    dir_b = geoai_engine.run_fields(cfg_b)

    assert dir_a != dir_b
    assert len(calls) == 2
