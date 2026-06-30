"""Tests for terraflow.climate_impact — climate-impact pipeline orchestration (#138e)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from terraflow.climate_impact import (
    load_timeseries_csv,
    run_climate_impact_features,
)
from terraflow.config import (
    ROI,
    ClimateConfig,
    ModelParams,
    PipelineConfig,
    Scenario,
    TemporalAggregation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_timeseries_csv(
    path: Path,
    stations: list[tuple[str, float, float]],
    *,
    start: str = "2010-01-01",
    end: str = "2010-12-31",
    temp_c: float = 18.0,
    precip_mm: float = 2.5,
) -> Path:
    """Write a minimal long-format station time-series CSV.

    *stations* is ``[(station_id, lat, lon), ...]``. Daily rows over the
    inclusive *start/end* window. Constant values (used for shape tests).
    """
    dates = pd.date_range(start=start, end=end, freq="D")
    rows = []
    for sid, lat, lon in stations:
        for d in dates:
            rows.append(
                {
                    "station_id": sid,
                    "lat": lat,
                    "lon": lon,
                    "date": d.strftime("%Y-%m-%d"),
                    "temperature_c": temp_c,
                    "precipitation_mm": precip_mm,
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return path


def _minimal_cfg(
    timeseries_csv: Path, *, with_aggregations: bool = True
) -> PipelineConfig:
    """Build a minimal PipelineConfig with the climate-impact block populated."""
    aggregations = []
    scenarios = []
    if with_aggregations:
        aggregations = [
            TemporalAggregation(kind="annual_mean"),
            TemporalAggregation(kind="growing_degree_days", base_temp_c=10.0),
        ]
        scenarios = [
            Scenario(name="historical", period=[2010, 2010]),
        ]
    climate = ClimateConfig(
        strategy="spatial",
        interpolation_method="linear",
        temporal_aggregations=aggregations,
        scenarios=scenarios,
        timeseries_csv=str(timeseries_csv) if with_aggregations else None,
    )
    return PipelineConfig(
        raster_path=Path("data/dummy.tif"),
        climate_csv=Path("data/dummy.csv"),
        output_dir=Path("outputs"),
        roi=ROI(type="bbox", xmin=-101.0, ymin=39.0, xmax=-99.0, ymax=41.0),
        model_params=ModelParams(
            v_min=0.0,
            v_max=1.0,
            t_min=0.0,
            t_max=40.0,
            r_min=0.0,
            r_max=300.0,
            w_v=0.4,
            w_t=0.3,
            w_r=0.3,
        ),
        climate=climate,
    )


def _cells_df(n: int = 5) -> pd.DataFrame:
    """Build a synthetic cells DataFrame with cell_id, lat, lon."""
    return pd.DataFrame(
        {
            "cell_id": list(range(n)),
            "lat": np.linspace(39.5, 40.5, n),
            "lon": np.linspace(-100.5, -99.5, n),
        }
    )


# ---------------------------------------------------------------------------
# load_timeseries_csv — schema enforcement
# ---------------------------------------------------------------------------


def test_load_timeseries_csv_validates_full_schema(tmp_path: Path):
    path = _write_timeseries_csv(
        tmp_path / "ts.csv",
        stations=[("S1", 40.0, -100.0)],
        start="2010-01-01",
        end="2010-01-05",
    )
    df = load_timeseries_csv(path)
    assert {
        "station_id",
        "lat",
        "lon",
        "date",
        "temperature_c",
        "precipitation_mm",
    } <= set(df.columns)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert pd.api.types.is_float_dtype(df["temperature_c"])


def test_load_timeseries_csv_rejects_missing_columns(tmp_path: Path):
    df = pd.DataFrame({"station_id": ["S1"], "lat": [40.0], "lon": [-100.0]})
    path = tmp_path / "bad.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required column"):
        load_timeseries_csv(path)


def test_load_timeseries_csv_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_timeseries_csv(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# run_climate_impact_features — happy path
# ---------------------------------------------------------------------------


def test_run_climate_impact_features_writes_parquet_with_scenario_columns(
    tmp_path: Path,
):
    """3 stations × 2 rules × 1 scenario → climate_features.parquet has 2 derived cols × N cells."""
    ts_path = _write_timeseries_csv(
        tmp_path / "ts.csv",
        stations=[("S1", 39.5, -100.5), ("S2", 40.0, -100.0), ("S3", 40.5, -99.5)],
        temp_c=20.0,
        precip_mm=3.0,
    )
    cfg = _minimal_cfg(ts_path)
    cells = _cells_df(5)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    out_path = run_climate_impact_features(cfg, run_dir, cells)

    assert out_path.exists()
    assert out_path.name == "climate_features.parquet"
    df = pd.read_parquet(out_path)
    assert "cell_id" in df.columns
    assert "annual_mean__historical" in df.columns
    assert "growing_degree_days__base10__historical" in df.columns
    assert len(df) == 5
    # Constant 20°C → annual_mean ≈ 20 at every cell; GDD ≈ 365*10 = 3650 (constant input).
    assert df["annual_mean__historical"].iloc[0] == pytest.approx(20.0, abs=0.01)
    assert df["growing_degree_days__base10__historical"].iloc[0] == pytest.approx(
        365 * 10.0, abs=10
    )


def test_run_climate_impact_features_raises_on_empty_rules(tmp_path: Path):
    cfg = _minimal_cfg(tmp_path / "anything.csv", with_aggregations=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(ValueError, match="empty"):
        run_climate_impact_features(cfg, run_dir, _cells_df())


def test_run_climate_impact_features_raises_on_missing_timeseries(tmp_path: Path):
    """Even with aggregations + scenarios, omitting timeseries_csv must surface
    a clear error rather than silently producing empty data."""
    cfg = _minimal_cfg(tmp_path / "ts.csv", with_aggregations=True)
    # Force timeseries_csv to None at the climate sub-config level after construction.
    cfg.climate.timeseries_csv = None
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(ValueError, match="timeseries_csv"):
        run_climate_impact_features(cfg, run_dir, _cells_df())


def test_run_climate_impact_features_two_scenarios_produces_2x_columns(tmp_path: Path):
    """Two scenarios with identical climate → two columns per rule, equal values."""
    ts_path = _write_timeseries_csv(
        tmp_path / "ts.csv",
        stations=[("S1", 39.5, -100.5), ("S2", 40.0, -100.0), ("S3", 40.5, -99.5)],
        start="2010-01-01",
        end="2011-12-31",
        temp_c=18.0,
        precip_mm=2.0,
    )
    cfg = _minimal_cfg(ts_path)
    # Add a second scenario over the same temperature distribution.
    cfg.climate.scenarios = [
        Scenario(name="historical", period=[2010, 2010]),
        Scenario(name="ssp245", period=[2011, 2011]),
    ]
    cells = _cells_df(3)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    out_path = run_climate_impact_features(cfg, run_dir, cells)
    df = pd.read_parquet(out_path)
    assert "annual_mean__historical" in df.columns
    assert "annual_mean__ssp245" in df.columns
    # Same climate → same interpolated value across both scenarios.
    np.testing.assert_allclose(
        df["annual_mean__historical"].to_numpy(),
        df["annual_mean__ssp245"].to_numpy(),
        atol=0.01,
    )


# ---------------------------------------------------------------------------
# validate_all — gate update (#138e)
# ---------------------------------------------------------------------------


def test_validate_all_rejects_aggregations_without_timeseries_csv(tmp_path: Path):
    cfg = _minimal_cfg(tmp_path / "ts.csv", with_aggregations=True)
    cfg.climate.timeseries_csv = None
    with pytest.raises(ValueError, match="timeseries_csv"):
        cfg.validate_all()


def test_validate_all_accepts_climate_impact_with_timeseries(tmp_path: Path):
    """Previously NotImplementedError — #138e activates the path."""
    ts_path = _write_timeseries_csv(
        tmp_path / "ts.csv",
        stations=[("S1", 40.0, -100.0)],
    )
    cfg = _minimal_cfg(ts_path)
    cfg.validate_all()  # no raise
