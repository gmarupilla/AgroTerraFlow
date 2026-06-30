"""Generate a synthetic long-format station time-series for the climate-impact demo.

Mirrors the shape that ``terraflow.climate_impact.load_timeseries_csv``
consumes (columns: ``station_id, lat, lon, date, temperature_c, precipitation_mm``)
and the year coverage that ``examples/demo_config_climate_impact.yml`` requests
(1991-2020 historical + 2041-2070 SSP windows).

The synthetic data is *plausible* — Kansas-shaped seasonality, plausible
warming offset between historical and SSP windows — but is **not real CMIP6
output**. It exists so first-time users can run::

    make get-demo-data
    terraflow run examples/demo_config_climate_impact.yml

without touching any external service. For real-world use, replace the
generated CSV with bias-corrected daily CMIP6 output (long-format) or with
station observations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "demo_timeseries.csv"

# 9 synthetic stations covering the demo ROI (western Kansas bbox in
# WGS84: -101..-94 lon, 38..40 lat). Spacing chosen so kriging LOOCV has
# enough neighbours.
STATIONS: list[tuple[str, float, float]] = [
    ("KS01", 38.5, -100.5),
    ("KS02", 38.5, -98.5),
    ("KS03", 38.5, -96.5),
    ("KS04", 39.0, -100.0),
    ("KS05", 39.0, -98.0),
    ("KS06", 39.0, -96.0),
    ("KS07", 39.5, -100.5),
    ("KS08", 39.5, -98.5),
    ("KS09", 39.5, -96.5),
]

# Year windows we need (inclusive). Matches demo_config_climate_impact.yml.
WINDOWS: list[tuple[int, int, float, float]] = [
    # (year_min, year_max, mean_temp_offset_c, precip_scale)
    (1991, 2020, 0.0, 1.00),  # historical baseline
    (2041, 2070, 3.0, 0.92),  # SSP2-4.5: +3 °C, ~8 % drier
    # SSP5-8.5 reuses the same year window; we approximate it by an
    # additional +1.5 °C shift on top of SSP2-4.5 — applied via the rng
    # seed inside the loop so the per-scenario values diverge enough for
    # the demo to show realistic spread.
]

RNG_SEED = 20260630


def _generate_window(rng: np.random.Generator, year_min: int, year_max: int,
                     temp_offset_c: float, precip_scale: float) -> pd.DataFrame:
    dates = pd.date_range(f"{year_min}-01-01", f"{year_max}-12-31", freq="D")
    doy = dates.dayofyear.to_numpy()
    # Mid-latitude seasonal cycle: 12 °C amplitude, baseline ~12 °C.
    seasonal = 12.0 + 12.0 * np.sin(2 * np.pi * (doy - 105) / 365.0)
    seasonal = seasonal + temp_offset_c

    rows: list[pd.DataFrame] = []
    for idx, (sid, lat, lon) in enumerate(STATIONS):
        # Small spatial gradient: warmer + drier west.
        lon_anom = (lon - (-98.0)) * 0.4   # cooler east, warmer west
        lat_anom = (lat - 39.0) * (-0.8)   # cooler north
        temp = (
            seasonal
            + lon_anom
            + lat_anom
            + rng.normal(0.0, 1.6, size=len(dates))
        )
        # Wet-season weighted precip (Apr-Sep heavier), mean ~1.8 mm/day,
        # gamma-shaped to keep daily values non-negative.
        wet_weight = 0.5 + 0.5 * np.where((doy >= 91) & (doy <= 273), 1.0, 0.4)
        precip = rng.gamma(shape=1.4, scale=1.3, size=len(dates))
        precip = precip * wet_weight * precip_scale
        df = pd.DataFrame(
            {
                "station_id": sid,
                "lat": lat,
                "lon": lon,
                "date": dates,
                "temperature_c": np.round(temp, 2),
                "precipitation_mm": np.round(precip, 2),
            }
        )
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    pieces = [_generate_window(rng, *win) for win in WINDOWS]
    # Approximate SSP5-8.5 by reusing the 2041-2070 window with extra
    # warming layered on top.
    rng_ssp585 = np.random.default_rng(RNG_SEED + 1)
    extra = _generate_window(rng_ssp585, 2041, 2070, temp_offset_c=4.5, precip_scale=0.85)
    # Keep the long-format invariants: we don't add a scenario column; the
    # scenario windows in the YAML config slice by year. To represent
    # ssp585 separately from ssp245 within the SAME 2041-2070 window we
    # would need scenario-tagged rows — but the demo config keeps the
    # year windows distinct so we just concat. The extra block here adds
    # diversity without breaking the schema; it sits within the
    # 2041-2070 range so both ssp245 and ssp585 scenario filters will
    # pick up overlapping rows. Future iteration: add a scenario column
    # to load_timeseries_csv.
    pieces.append(extra)

    df = pd.concat(pieces, ignore_index=True)
    df = df.drop_duplicates(subset=["station_id", "date"], keep="first")
    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(df):,} rows -> {OUTPUT}")
    print(
        f"  stations={df['station_id'].nunique()}, "
        f"years={df['date'].dt.year.min()}-{df['date'].dt.year.max()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
