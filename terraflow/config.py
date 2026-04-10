import math
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ModelParams(BaseModel):
    """Parameters for normalization and weighting in the suitability model.

    The weights w_v, w_t, w_r should sum to approximately 1.0 for proper
    normalization, though this is not strictly enforced.

    Attributes
    ----------
    v_min, v_max:
        Min/max vegetation index values for normalization.
    t_min, t_max:
        Min/max temperature values for normalization (in °C).
    r_min, r_max:
        Min/max rainfall values for normalization (in mm).
    w_v, w_t, w_r:
        Weights for vegetation, temperature, and rainfall (should sum to 1.0).
    uncertainty_samples:
        Number of Monte Carlo draws per cell for uncertainty propagation.
        0 (default) disables Monte Carlo.  Requires ``interpolation_method='kriging'``
        to produce per-cell standard deviations.  Adds ``score_ci_low`` and
        ``score_ci_high`` columns to ``features.parquet`` and an ``uncertainty``
        block to ``report.json``.
    """

    v_min: float
    v_max: float
    t_min: float
    t_max: float
    r_min: float
    r_max: float
    w_v: float
    w_t: float
    w_r: float
    uncertainty_samples: int = 0  # 0 = off; >0 = Monte Carlo draws per cell

    model_config = ConfigDict(extra="forbid")

    @field_validator("uncertainty_samples")
    @classmethod
    def validate_uncertainty_samples(cls, v: int) -> int:
        """Ensure uncertainty_samples is non-negative."""
        if v < 0:
            raise ValueError(f"uncertainty_samples must be >= 0, got {v}")
        return v

    @field_validator("v_min", "t_min", "r_min")
    @classmethod
    def validate_min_values(cls, v: float, info) -> float:
        """Ensure min values are reasonable numbers."""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Min value must be numeric, got {type(v)}")
        return v

    @field_validator("v_max", "t_max", "r_max")
    @classmethod
    def validate_max_values(cls, v: float, info) -> float:
        """Ensure max values are reasonable numbers."""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Max value must be numeric, got {type(v)}")
        return v

    def validate_ranges(self) -> None:
        """Validate that min < max for all ranges. Call after initialization."""
        if self.v_min >= self.v_max:
            raise ValueError(
                f"v_min ({self.v_min}) must be less than v_max ({self.v_max})"
            )
        if self.t_min >= self.t_max:
            raise ValueError(
                f"t_min ({self.t_min}) must be less than t_max ({self.t_max})"
            )
        if self.r_min >= self.r_max:
            raise ValueError(
                f"r_min ({self.r_min}) must be less than r_max ({self.r_max})"
            )

        # Check weights are non-negative
        if self.w_v < 0 or self.w_t < 0 or self.w_r < 0:
            raise ValueError("Weights must be non-negative")

        # Check weights sum to approximately 1.0 (allow small tolerance)
        weight_sum = self.w_v + self.w_t + self.w_r
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to approximately 1.0, got {weight_sum:.3f} "
                f"(w_v={self.w_v}, w_t={self.w_t}, w_r={self.w_r})"
            )


class ROI(BaseModel):
    """Region of interest. For now we support only a bounding box.

    Attributes
    ----------
    type:
        Type of ROI (currently only 'bbox' is supported).
    xmin, ymin, xmax, ymax:
        Bounding box coordinates expressed in *roi_crs* (default WGS 84 degrees).
    roi_crs:
        EPSG code or WKT string for the CRS of the bounding box coordinates.
        Defaults to ``"EPSG:4326"`` (latitude/longitude degrees).  The pipeline
        automatically reprojects to the raster's native CRS before clipping.
    """

    type: Literal["bbox"] = "bbox"
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    roi_crs: str = "EPSG:4326"

    model_config = ConfigDict(extra="forbid")

    def validate_bounds(self) -> None:
        """Validate that bounds are sensible. Call after initialization."""
        if self.xmin >= self.xmax:
            raise ValueError(f"xmin ({self.xmin}) must be less than xmax ({self.xmax})")
        if self.ymin >= self.ymax:
            raise ValueError(f"ymin ({self.ymin}) must be less than ymax ({self.ymax})")


class ClimateConfig(BaseModel):
    """Climate data configuration for spatial matching and interpolation.

    Supports two strategies for aligning climate observations to raster cells:
    - 'spatial': Interpolate climate values using geographic coordinates (lat/lon).
    - 'index': Match cells to climate records by row index or explicit cell ID.

    When strategy is 'spatial', three interpolation methods are available:
    - 'linear': Delaunay-triangulation linear interpolation (scipy.griddata, default).
    - 'kriging': Ordinary Kriging — geostatistically optimal with per-cell uncertainty
      (requires pykrige; ≥5 stations recommended).
    - 'idw': Inverse Distance Weighting — fast, no uncertainty estimate.

    Attributes
    ----------
    strategy:
        Matching strategy: 'spatial' (interpolation) or 'index' (direct matching).
    interpolation_method:
        Interpolation algorithm when strategy='spatial'.
        Choices: 'linear' (default), 'kriging', 'idw'.
    cell_id_column:
        Column name in climate CSV for cell ID (used with 'index' strategy).
        If None with 'index' strategy, uses row order matching.
    fallback_to_mean:
        If True, use global mean climate for cells outside interpolation range
        or when climate data is sparse (default True).
    """

    strategy: Literal["spatial", "index"] = "spatial"
    interpolation_method: Literal["linear", "kriging", "idw"] = "linear"
    cell_id_column: str | None = None
    fallback_to_mean: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        """Ensure strategy is valid."""
        if v not in ("spatial", "index"):
            raise ValueError(f"strategy must be 'spatial' or 'index', got '{v}'")
        return v

    @field_validator("interpolation_method")
    @classmethod
    def validate_interpolation_method(cls, v: str) -> str:
        """Ensure interpolation_method is valid."""
        if v not in ("linear", "kriging", "idw"):
            raise ValueError(
                f"interpolation_method must be 'linear', 'kriging', or 'idw', got '{v}'"
            )
        return v

    def validate_config(self) -> None:
        """Validate consistency of climate configuration."""
        # interpolation_method only applies to spatial strategy
        pass


class WeightBounds(BaseModel):
    """Bounds for a single weight parameter in sensitivity analysis."""

    low: float
    high: float
    model_config = ConfigDict(extra="forbid")

    @field_validator("high")
    @classmethod
    def high_gt_low(cls, v: float, info) -> float:
        low = info.data.get("low")
        if low is not None and v <= low:
            raise ValueError(f"high ({v}) must be greater than low ({low})")
        return v


class SensitivityConfig(BaseModel):
    """Configuration for sensitivity analysis (per D-04)."""

    w_v: WeightBounds
    w_t: WeightBounds
    w_r: WeightBounds
    n_samples: int = 1024
    method: Literal["sobol", "morris", "both"] = "both"
    model_config = ConfigDict(extra="forbid")

    @field_validator("n_samples")
    @classmethod
    def validate_n_samples_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"n_samples must be positive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_power_of_two(self) -> "SensitivityConfig":
        if self.method in ("sobol", "both"):
            v = self.n_samples
            if (v & (v - 1)) != 0:
                nearest = 2 ** round(math.log2(v))
                raise ValueError(
                    f"n_samples must be a power of 2 for Sobol' sampling, got {v}. "
                    f"Nearest power of 2: {nearest}"
                )
        return self


class ValidationConfig(BaseModel):
    """Configuration for model validation (Phase 3)."""

    n_blocks_side: int = 4
    buffer_deg: float = 0.5
    reference_csv: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ExportConfig(BaseModel):
    """Configuration for H3 export (Phase 4)."""

    h3_resolution: int = 8
    model_config = ConfigDict(extra="forbid")

    @field_validator("h3_resolution")
    @classmethod
    def validate_h3_resolution(cls, v: int) -> int:
        if not (0 <= v <= 15):
            raise ValueError(f"h3_resolution must be 0-15, got {v}")
        return v


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration.

    Attributes
    ----------
    raster_path:
        Path to the input raster file (GeoTIFF).
    climate_csv:
        Path to the climate data CSV file.
    output_dir:
        Directory for output results.
    roi:
        Region of interest specification.
    model_params:
        Suitability model parameters.
    climate:
        Climate data configuration (strategy, fallback behavior, etc.).
    max_cells:
        Maximum number of cells to sample from the ROI (default 500).
    """

    raster_path: Path
    climate_csv: Path
    output_dir: Path
    roi: ROI
    model_params: ModelParams
    climate: ClimateConfig = ClimateConfig()  # Default: spatial strategy with fallback
    max_cells: int = 500  # maximum number of cells to sample from the ROI
    sensitivity: Optional[SensitivityConfig] = None  # Optional sensitivity analysis config
    validation: Optional[ValidationConfig] = None  # Optional validation config
    export: Optional[ExportConfig] = None  # Optional H3 export config

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_cells")
    @classmethod
    def validate_max_cells(cls, v: int) -> int:
        """Ensure max_cells is a positive integer."""
        if v <= 0:
            raise ValueError(f"max_cells must be positive, got {v}")
        return v

    def validate_all(self) -> None:
        """Validate all constraints. Call after model initialization."""
        self.roi.validate_bounds()
        self.model_params.validate_ranges()
        self.climate.validate_config()


def load_config_dict(path: str | Path) -> dict:
    """Load YAML config from disk into a raw dict.

    Parameters
    ----------
    path:
        Path to the YAML configuration file.

    Returns
    -------
    dict:
        Parsed configuration as a Python dict.

    Raises
    ------
    FileNotFoundError:
        If the config file does not exist.
    yaml.YAMLError:
        If the YAML is malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML config: {e}") from e

    if data is None:
        raise ValueError("Configuration file is empty")

    return data


def build_config(data: dict) -> PipelineConfig:
    """Validate a raw config dict into a PipelineConfig."""
    try:
        cfg = PipelineConfig.model_validate(data)
        cfg.validate_all()
        return cfg
    except ValueError as e:
        raise ValueError(f"Configuration validation failed: {e}") from e


def load_config(path: str | Path) -> PipelineConfig:
    """Load YAML config from disk and validate with Pydantic.

    Parameters
    ----------
    path:
        Path to the YAML configuration file.

    Returns
    -------
    PipelineConfig:
        Validated configuration object.

    Raises
    ------
    FileNotFoundError:
        If the config file does not exist.
    yaml.YAMLError:
        If the YAML is malformed.
    ValueError:
        If the configuration is invalid.
    """
    data = load_config_dict(path)
    return build_config(data)
