import json
import os
from pathlib import Path

import pytest

from terraflow.core.run_identity import (
    canonicalize_config,
    compute_run_fingerprint,
    fingerprint_file,
    hash_roi_geometry,
)
from terraflow.pipeline import (
    _collect_input_paths,
    _expand_input_paths,
    _resolve_roi_hash,
)


def _set_mtime(path: Path, mtime: int) -> None:
    os.utime(path, (mtime, mtime))


def test_canonical_config_stable_ordering():
    cfg_a = {
        "b": 1,
        "a": {"d": 2, "c": [3, 2]},
    }
    cfg_b = {
        "a": {"c": [3, 2], "d": 2},
        "b": 1,
    }

    assert canonicalize_config(cfg_a) == canonicalize_config(cfg_b)


def test_run_fingerprint_deterministic_for_same_inputs(tmp_path: Path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("alpha", encoding="utf-8")
    file_b.write_text("bravo", encoding="utf-8")

    mtime = 1_700_000_000
    _set_mtime(file_a, mtime)
    _set_mtime(file_b, mtime)

    roi = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0}
    config_dict: dict[str, object] = {
        "raster_path": str(file_a),
        "climate_csv": str(file_b),
        "roi": roi,
        "output_dir": "outputs",
    }

    roi_hash = hash_roi_geometry(roi)
    inputs = [fingerprint_file(str(file_a)), fingerprint_file(str(file_b))]

    fp1 = compute_run_fingerprint(config_dict, roi_hash, inputs)
    fp2 = compute_run_fingerprint(config_dict, roi_hash, inputs)

    assert fp1 == fp2


def test_run_fingerprint_changes_when_file_changes(tmp_path: Path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("alpha", encoding="utf-8")
    file_b.write_text("bravo", encoding="utf-8")

    roi = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0}
    config_dict: dict[str, object] = {
        "raster_path": str(file_a),
        "climate_csv": str(file_b),
        "roi": roi,
    }

    roi_hash = hash_roi_geometry(roi)
    inputs = [fingerprint_file(str(file_a)), fingerprint_file(str(file_b))]
    fp1 = compute_run_fingerprint(config_dict, roi_hash, inputs)

    file_b.write_text("bravo!", encoding="utf-8")
    inputs_changed = [fingerprint_file(str(file_a)), fingerprint_file(str(file_b))]
    fp2 = compute_run_fingerprint(config_dict, roi_hash, inputs_changed)

    assert fp1 != fp2


def test_run_fingerprint_does_not_depend_on_absolute_path(tmp_path: Path):
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    file_a = dir_a / "data.bin"
    file_b = dir_b / "data.bin"
    file_a.write_bytes(b"same-content")
    file_b.write_bytes(b"same-content")

    mtime = 1_700_000_100
    _set_mtime(file_a, mtime)
    _set_mtime(file_b, mtime)

    roi = {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0}
    config_dict: dict[str, object] = {
        "raster_path": "data/soil.tif",
        "roi": roi,
    }
    roi_hash = hash_roi_geometry(roi)

    fp1 = compute_run_fingerprint(
        config_dict,
        roi_hash,
        [fingerprint_file(str(file_a))],
    )
    fp2 = compute_run_fingerprint(
        config_dict,
        roi_hash,
        [fingerprint_file(str(file_b))],
    )

    assert fp1 == fp2


def test_fingerprint_file_missing_raises(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        fingerprint_file(str(missing))


def test_hash_roi_geometry_from_geojson_variants(tmp_path: Path):
    polygon = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }
    feature = {"type": "Feature", "geometry": polygon, "properties": {}}
    feature_collection = {
        "type": "FeatureCollection",
        "features": [feature],
    }

    polygon_path = tmp_path / "polygon.geojson"
    polygon_path.write_text(json.dumps(polygon), encoding="utf-8")
    feature_path = tmp_path / "feature.geojson"
    feature_path.write_text(json.dumps(feature), encoding="utf-8")
    collection_path = tmp_path / "collection.geojson"
    collection_path.write_text(json.dumps(feature_collection), encoding="utf-8")

    hash_polygon = hash_roi_geometry(str(polygon_path))
    hash_feature = hash_roi_geometry(str(feature_path))
    hash_collection = hash_roi_geometry(str(collection_path))

    assert hash_polygon == hash_feature == hash_collection


def test_hash_roi_geometry_invalid_geojson_raises(tmp_path: Path):
    bad_path = tmp_path / "missing.geojson"
    with pytest.raises(FileNotFoundError, match="ROI GeoJSON file not found"):
        hash_roi_geometry(str(bad_path))

    feature_no_geom = {"type": "Feature", "properties": {}}
    no_geom_path = tmp_path / "no_geom.geojson"
    no_geom_path.write_text(json.dumps(feature_no_geom), encoding="utf-8")
    with pytest.raises(ValueError, match="missing geometry"):
        hash_roi_geometry(str(no_geom_path))

    empty_collection = {"type": "FeatureCollection", "features": []}
    empty_path = tmp_path / "empty.geojson"
    empty_path.write_text(json.dumps(empty_collection), encoding="utf-8")
    with pytest.raises(ValueError, match="no geometries"):
        hash_roi_geometry(str(empty_path))

    unsupported = {"type": "Point", "coordinates": [0, 0]}
    unsupported_path = tmp_path / "point.geojson"
    unsupported_path.write_text(json.dumps(unsupported), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported GeoJSON type"):
        hash_roi_geometry(str(unsupported_path))


def test_expand_and_collect_input_paths(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    file_a = data_dir / "a.tif"
    file_b = data_dir / "b.tif"
    file_c = data_dir / "c.csv"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")
    file_c.write_text("c", encoding="utf-8")

    config_dict: dict[str, object] = {
        "raster_path": "data/a.tif",
        "climate_csv": "data/c.csv",
        "climate": {"weather_raster_glob": "data/*.tif"},
        "roi": {"type": "bbox", "xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0},
    }

    paths = _collect_input_paths(config_dict, tmp_path)
    expected = {file_a.resolve(), file_b.resolve(), file_c.resolve()}
    assert set(paths) == expected

    glob_paths = _expand_input_paths("data/*.tif", tmp_path)
    assert {path.resolve() for path in glob_paths} == {
        file_a.resolve(),
        file_b.resolve(),
    }

    with pytest.raises(FileNotFoundError, match="No files match input pattern"):
        _expand_input_paths("data/*.nc", tmp_path)


def test_resolve_roi_hash_from_path(tmp_path: Path):
    polygon = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
    }
    roi_path = tmp_path / "roi.geojson"
    roi_path.write_text(json.dumps(polygon), encoding="utf-8")

    config_dict: dict[str, object] = {"roi": {"path": str(roi_path)}}
    roi_hash = _resolve_roi_hash(config_dict, tmp_path)
    assert isinstance(roi_hash, str)

    with pytest.raises(ValueError, match="ROI configuration missing"):
        _resolve_roi_hash({}, tmp_path)
