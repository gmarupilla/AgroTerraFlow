# TerraFlow in 10 Minutes

Everything you need to go from zero to a working suitability map — what it is, why it exists, how it works, and a live run you can follow along with.

---

## What is TerraFlow?

TerraFlow is a command-line tool that answers one question:

> **"Given a piece of land, how suitable is it for a particular crop or use — right now, given the current climate?"**

It takes three inputs:

| Input | What it is | Example |
|---|---|---|
| A land-cover map (raster) | A satellite-derived map of the land, broken into pixels | USDA Cropland Data Layer (CDL) |
| A climate data file | Temperature and rainfall readings from nearby weather stations | CSV with lat, lon, mean_temp, total_rain |
| A configuration file | Your choices: which region, what crop thresholds, how many sites | `config.yml` |

And produces one output: `results.csv` — a table where every row is a sampled location with a **suitability score** (0–1) and a **label** (low / medium / high).

---

## Why does it exist?

Assessing land suitability is traditionally done by hand — an agronomist looks at soil maps, calls the local weather office, and applies expert judgment to a spreadsheet. That process is:

- **Slow** — days or weeks for a single region
- **Inconsistent** — different analysts reach different conclusions
- **Not reproducible** — the next analyst can't trace exactly what was done

TerraFlow makes it:

- **Fast** — seconds for hundreds of locations
- **Consistent** — same config always gives same result
- **Fully reproducible** — every run is fingerprinted; two people with the same config and data get byte-identical outputs

---

## How does the pipeline work?

```
Your config.yml
      │
      ▼
1. Load land-cover raster (GeoTIFF)
      │   ← crop to your region of interest (ROI)
      ▼
2. Load climate CSV (weather stations)
      │   ← interpolate to each land pixel
      ▼
3. Score each pixel
      │   vegetation index  ×  weight_v
      │ + temperature score ×  weight_t
      │ + rainfall score    ×  weight_r
      ▼
4. Write results.csv
      cell_id | lat | lon | score | label
```

**Key design choices:**

- Coordinates are always output in WGS84 degrees (lat/lon) regardless of what map projection the input raster uses.
- The same config + data always produces the same output — sampling is seeded from a SHA-256 fingerprint of your inputs.
- Relative paths in configs are resolved relative to the config file itself, so configs are portable.

---

## Try it now (5 commands)

```bash
# 1. Clone and install
git clone https://github.com/gmarupilla/AgroTerraFlow.git
cd TerraFlow
pip install -e ".[dev]"

# 2. Run the demo
terraflow -c examples/demo_config.yml

# 3. Look at the results
head -5 outputs/demo_run/results.csv
```

Expected output (values will vary by sampled cells):

```
cell_id,lat,lon,v_index,mean_temp,total_rain,score,label
0,39.14,-100.82,87.0,20.3,142.1,0.71,high
1,38.55,-99.20,42.0,19.8,138.4,0.44,medium
2,39.88,-97.61,12.0,20.1,135.9,0.23,low
...
```

---

## What the output columns mean

| Column | Meaning |
|---|---|
| `cell_id` | Index of the sampled pixel within your ROI |
| `lat` / `lon` | Geographic coordinates in WGS84 degrees |
| `v_index` | Raw value from the land-cover raster at this pixel |
| `mean_temp` | Interpolated temperature (°C) at this location |
| `total_rain` | Interpolated rainfall (mm) at this location |
| `score` | Suitability score from 0 (worst) to 1 (best) |
| `label` | Human-readable tier: `low` / `medium` / `high` |

---

## Configuring for your crop

The config file controls everything. Here is a minimal example:

```yaml
raster_path: "../data/my_land_cover.tif"
climate_csv: "../data/weather_stations.csv"
output_dir: "../outputs/my_run"

roi:
  type: bbox
  xmin: -101.0   # West boundary (longitude)
  ymin: 38.0     # South boundary (latitude)
  xmax: -94.0    # East boundary (longitude)
  ymax: 40.0     # North boundary (latitude)

model_params:
  v_min: 0.0     # Lowest acceptable vegetation index
  v_max: 255.0   # Highest vegetation index in your raster
  t_min: 10.0    # Minimum suitable temperature (°C)
  t_max: 35.0    # Maximum suitable temperature (°C)
  r_min: 100.0   # Minimum suitable annual rainfall (mm)
  r_max: 800.0   # Maximum suitable annual rainfall (mm)
  w_v: 0.4       # Weight for vegetation score (must sum to 1.0)
  w_t: 0.3       # Weight for temperature score
  w_r: 0.3       # Weight for rainfall score

max_cells: 500   # How many locations to sample
```

Save this as `config.yml` and run:

```bash
terraflow -c config.yml
```

---

## What happens next?

| I want to… | Go to… |
|---|---|
| Understand the results without writing code | [Field Guide](field-guide.md) |
| Customise the config in detail | [Configuration Schema](config/schema.md) |
| Contribute to the codebase | [Development Guide](DEVELOPMENT.md) |
| Understand the architecture and design decisions | [Architecture Overview](architecture/overview.md) |
| See the full list of known issues and improvements | `AUDIT.md` (git-ignored, developers only) |
