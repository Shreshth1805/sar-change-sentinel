from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Classification = Literal["man_made", "natural", "uncertain"]


class SyntheticJobRequest(BaseModel):
    aoi_name: str = "Demo AOI (New Delhi)"
    seed: int | None = 42
    width: int = Field(default=200, ge=64, le=512)
    height: int = Field(default=200, ge=64, le=512)
    include_classifications: list[Classification] = ["man_made"]


class GeeJobRequest(BaseModel):
    aoi_name: str
    aoi_geojson: dict
    pre_start: date
    pre_end: date
    post_start: date
    post_end: date
    scale_m: float = 10.0
    gee_project: str | None = None
    include_classifications: list[Classification] = ["man_made"]
