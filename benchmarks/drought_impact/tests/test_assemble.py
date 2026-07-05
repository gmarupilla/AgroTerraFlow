import json

from drought_impact.assemble import assemble_benchmark


def test_assemble_writes_artifacts_and_columns(bench_cfg):
    benchmark, manifest = assemble_benchmark(bench_cfg, write=True)
    for col in ("GEOID", "year", "drought_loss_cost", "significant_loss", "insured_acre_fraction"):
        assert col in benchmark.columns
    # predictor columns present
    assert any(c.startswith("spei_anom_") for c in benchmark.columns)
    assert (bench_cfg.output_dir / "benchmark.parquet").exists()
    assert (bench_cfg.output_dir / "manifest.json").exists()
    assert manifest["n_rows"] == len(benchmark)
    assert manifest["n_positive"] == int(benchmark["significant_loss"].sum())


def test_build_fingerprint_is_deterministic(bench_cfg):
    _, m1 = assemble_benchmark(bench_cfg, write=True)
    written = json.loads((bench_cfg.output_dir / "manifest.json").read_text())
    _, m2 = assemble_benchmark(bench_cfg, write=True)
    assert m1["build_fingerprint"] == m2["build_fingerprint"] == written["build_fingerprint"]


def test_leading_columns_order(bench_cfg):
    benchmark, _ = assemble_benchmark(bench_cfg, write=False)
    assert list(benchmark.columns[:2]) == ["GEOID", "year"]
