FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies for rasterio / GDAL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy library code and example config
COPY terraflow ./terraflow
COPY examples ./examples

# Default entrypoint: run CLI; user passes --config or uses default CMD
ENTRYPOINT ["python", "-m", "terraflow.cli"]
CMD ["--config", "examples/demo_config.yml"]
