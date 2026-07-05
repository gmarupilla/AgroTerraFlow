"""Tests for the `terraflow drought` CLI sub-app and backward-compatibility of existing commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from terraflow.cli import app

from .drought_synthetic import make_benchmark, make_feature_table, write_synthetic_col

runner = CliRunner()


def test_existing_commands_still_work():
    # Adding the drought sub-app must not break the original commands.
    for cmd in ("run", "sensitivity", "validate"):
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, result.output


def test_drought_help_lists_subcommands():
    result = runner.invoke(app, ["drought", "--help"])
    assert result.exit_code == 0
    for sub in ("fetch", "build", "evaluate"):
        assert sub in result.output


def _write_config(tmp_path: Path, **over) -> Path:
    lines = {
        "states": "['17', '19']",
        "year_min": 2000,
        "year_max": 2001,
        "rma_dir": f'"{tmp_path}"',
        "feature_table": f'"{tmp_path / "feature_table.parquet"}"',
        "output_dir": f'"{tmp_path / "out"}"',
    }
    lines.update(over)
    body = "\n".join(f"{k}: {v}" for k, v in lines.items())
    path = tmp_path / "cfg.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_cli_build(tmp_path: Path):
    geoids = ["17001", "19005"]
    make_feature_table(geoids, [2000, 2001]).to_parquet(tmp_path / "feature_table.parquet", index=False)
    for y in (2000, 2001):
        rows = [
            {
                "year": y,
                "state": g[:2],
                "county": g[2:],
                "commodity": "CORN",
                "cause": "Drought",
                "liability": 1000,
                "indemnity": 300,
            }
            for g in geoids
        ]
        write_synthetic_col(tmp_path / f"colsom_{y}.zip", rows)

    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["drought", "build", "-c", str(cfg)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "benchmark.parquet").exists()


def test_cli_evaluate(tmp_path: Path):
    # Pre-write a benchmark so evaluate can load it directly.
    out = tmp_path / "out"
    out.mkdir()
    geoids = [f"{s}{c:03d}" for s in ("17", "19") for c in range(1, 6)]
    make_benchmark(geoids, [2000, 2001, 2002, 2003]).to_parquet(out / "benchmark.parquet", index=False)

    cfg = _write_config(tmp_path, year_max=2003, test_years="[2003]", train_max_year=2002, states="['17', '19']")
    result = runner.invoke(app, ["drought", "evaluate", "-c", str(cfg)])
    assert result.exit_code == 0, result.output
    assert (out / "leaderboard.csv").exists()


def test_cli_fetch_monkeypatched(tmp_path: Path, monkeypatch):
    calls = {}

    def fake_download(years, dest_dir, *, overwrite=False):
        calls["years"] = years
        return [Path(dest_dir) / f"colsom_{y}.zip" for y in years]

    monkeypatch.setattr("terraflow.drought.cli.download_col_years", fake_download)
    result = runner.invoke(
        app, ["drought", "fetch", "--rma-dir", str(tmp_path), "--year-min", "2000", "--year-max", "2001"]
    )
    assert result.exit_code == 0, result.output
    assert calls["years"] == [2000, 2001]
