FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for rasterio/GDAL + curl for uv installer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        build-essential \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv into /usr/local/bin so it is on PATH for all subsequent RUN steps
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

# Install package (metadata first for layer caching)
COPY pyproject.toml README.md ./
COPY terraflow ./terraflow
RUN uv pip install --system .

# Copy demo inputs and the synthetic-raster generator
COPY data ./data
COPY scripts ./scripts
COPY examples ./examples

# Generate synthetic demo raster (data/usda_cdl.tif) — no network needed
RUN python scripts/make_demo_raster.py

# Generate synthetic station time-series (data/demo_timeseries.csv) so the
# climate-impact demo config works in --network none environments.
RUN python scripts/make_demo_timeseries.py

# Pipeline writes here at runtime
RUN mkdir -p outputs

# Run as non-root user
RUN groupadd --system --gid 1001 terraflow && \
    useradd --system --uid 1001 --gid terraflow --home-dir /app --shell /sbin/nologin terraflow && \
    chown -R terraflow:terraflow /app
USER terraflow

# Default: run the demo pipeline; override --config for custom runs
ENTRYPOINT ["python", "-m", "terraflow.cli"]
CMD ["run", "--config", "examples/demo_config.yml"]
