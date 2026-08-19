"""Orchestrates the full change-detection pipeline and assembles the audit trail.

Fixed stage order, mirroring the audited-pipeline pattern: every stage
returns a StepReport, and the full ordered list is returned alongside the
final result so the API/UI can show exactly what happened at each step —
from raw speckle-filtered pixels down to the alerts a human sees. Nothing
here is a black box: the audit trail plus the discrimination stage's
per-blob `reasons` (app/core/discrimination.py) together let anyone trace
a final alert back to the physical evidence that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from affine import Affine

from app.core import alerts as alerts_mod
from app.core import change_detection
from app.core import discrimination
from app.core import postprocessing
from app.core import preprocessing
from app.core.audit import StepReport


@dataclass
class PipelineConfig:
    speckle_window_size: int = 7
    speckle_enl: float = preprocessing.DEFAULT_ENL
    change_threshold_multiplier: float = 1.0
    cleanup_opening_size: int = 3
    cleanup_min_size_px: int = 8
    discrimination_min_blob_px: int = 8
    include_classifications: tuple[str, ...] = ("man_made",)
    pixel_area_sqm: float | None = None


@dataclass
class PipelineResult:
    aoi_name: str
    geojson: dict[str, Any]
    alerts: list[dict[str, Any]]
    blobs: list[dict[str, Any]]
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def run_pipeline(
    aoi_name: str,
    pre_vv: np.ndarray,
    post_vv: np.ndarray,
    pre_vh: np.ndarray | None = None,
    post_vh: np.ndarray | None = None,
    water_mask: np.ndarray | None = None,
    vegetation_mask: np.ndarray | None = None,
    slope_mask: np.ndarray | None = None,
    transform: Affine = postprocessing.IDENTITY_TRANSFORM,
    crs: str = "EPSG:4326",
    config: PipelineConfig | None = None,
) -> PipelineResult:
    config = config or PipelineConfig()
    reports: list[StepReport] = []

    (pre_vv_f, post_vv_f), rep = preprocessing.preprocess_pair(
        pre_vv, post_vv, window_size=config.speckle_window_size, enl=config.speckle_enl
    )
    reports.append(rep)

    pre_vh_f = post_vh_f = None
    if pre_vh is not None and post_vh is not None:
        (pre_vh_f, post_vh_f), rep = preprocessing.preprocess_pair(
            pre_vh, post_vh, window_size=config.speckle_window_size, enl=config.speckle_enl
        )
        reports.append(rep)

    detection, rep = change_detection.detect_change(
        pre_vv_f,
        post_vv_f,
        pre_vh_f,
        post_vh_f,
        threshold_multiplier=config.change_threshold_multiplier,
    )
    reports.append(rep)

    cleaned_mask, rep = postprocessing.cleanup_mask(
        detection["change_mask"],
        opening_size=config.cleanup_opening_size,
        min_size_px=config.cleanup_min_size_px,
    )
    reports.append(rep)

    blobs, rep = discrimination.classify_blobs(
        cleaned_mask,
        water_mask=water_mask,
        vegetation_mask=vegetation_mask,
        slope_mask=slope_mask,
        min_blob_pixels=config.discrimination_min_blob_px,
    )
    reports.append(rep)

    geojson, rep = postprocessing.to_geojson(
        cleaned_mask,
        blobs,
        transform=transform,
        crs=crs,
        pixel_area_sqm=config.pixel_area_sqm,
        include_classifications=config.include_classifications,
    )
    reports.append(rep)

    alert_list, rep = alerts_mod.generate_alerts(
        geojson, aoi_name=aoi_name, detected_at=datetime.now(timezone.utc)
    )
    reports.append(rep)

    counts = {"man_made": 0, "natural": 0, "uncertain": 0}
    for b in blobs:
        counts[b["classification"]] += 1

    stats = {
        "changed_pixel_fraction": float(np.mean(detection["change_mask"])),
        "total_blobs": len(blobs),
        "classification_counts": counts,
        "alerts_generated": len(alert_list),
        "otsu_threshold": detection["threshold"],
    }

    return PipelineResult(
        aoi_name=aoi_name,
        geojson=geojson,
        alerts=alert_list,
        blobs=blobs,
        audit_trail=[r.to_dict() for r in reports],
        stats=stats,
    )
