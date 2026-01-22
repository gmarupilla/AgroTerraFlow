FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.cargo/bin:${PATH}"

# System dependencies for rasterio / GDAL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml README.md ./
COPY terraflow ./terraflow
RUN uv pip install --system .

# Copy library code and example config
COPY examples ./examples

# Default entrypoint: run CLI; user passes --config or uses default CMD
ENTRYPOINT ["python", "-m", "terraflow.cli"]
CMD ["--config", "examples/demo_config.yml"]
