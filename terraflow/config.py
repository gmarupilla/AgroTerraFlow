from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class ModelParams(BaseModel):
    """Parameters for normalization and weighting in the suitability model."""

    v_min: float
    v_max: float
    t_min: float
    t_max: float
    r_min: float
    r_max: float
    w_v: float
    w_t: float
    w_r: float

    model_config = ConfigDict(extra="forbid")


class ROI(BaseModel):
    """Region of interest. For now we support only a bounding box."""

    type: Literal["bbox"] = "bbox"
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    model_config = ConfigDict(extra="forbid")


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration."""

    raster_path: Path
    climate_csv: Path
    output_dir: Path
    roi: ROI
    model_params: ModelParams
    max_cells: int = 500  # maximum number of cells to sample from the ROI

    model_config = ConfigDict(extra="forbid")


def load_config(path: str | Path) -> PipelineConfig:
    """Load YAML config from disk and validate with Pydantic."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return PipelineConfig.model_validate(data)
