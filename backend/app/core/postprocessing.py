"""Morphological cleanup + georeferenced vectorization.

Two responsibilities, kept in one module because they're both "turn a raw
pixel mask into something worth alerting on":

1. `cleanup_mask` — remove the salt-and-pepper leftovers of residual
   speckle (binary opening) and any blob too small to plausibly be a real
   feature (skimage's `remove_small_objects`), *before* discrimination
   scores blobs. This is the primary lever for "minimum false alarms":
   most spurious single-pixel/few-pixel change is noise, not signal.
2. `to_geojson` — trace the classified blobs into real-world polygons
   using the raster's affine transform, so output lands in actual
   lon/lat (or projected) coordinates as a GeoJSON FeatureCollection —
   the deliverable format the problem statement asks for.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from affine import Affine
from rasterio.features import shapes as rio_shapes
from shapely.geometry import shape as shapely_shape, mapping

from app.core.audit import StepReport, run_step

IDENTITY_TRANSFORM = Affine.identity()


def cleanup_mask(
    change_mask: np.ndarray,
    opening_size: int = 3,
    min_size_px: int = 8,
) -> tuple[np.ndarray, StepReport]:
    from skimage.morphology import opening, remove_small_objects

    def _fn():
        before_count = int(np.sum(change_mask))
        footprint = np.ones((opening_size, opening_size), dtype=bool)
        opened = opening(change_mask, footprint) if opening_size > 1 else change_mask
        # remove_small_objects' max_size is inclusive ("<= max_size" removed),
        # so subtract 1 to match the old min_size ("< min_size" removed) semantics.
        cleaned = remove_small_objects(opened, max_size=max(min_size_px - 1, 0))
        after_count = int(np.sum(cleaned))
        details = {
            "opening_size": opening_size,
            "min_size_px": min_size_px,
            "changed_pixels_before": before_count,
            "changed_pixels_after": after_count,
            "pixels_removed_as_noise": before_count - after_count,
        }
        warnings: list[str] = []
        if before_count > 0 and after_count == 0:
            warnings.append(
                "cleanup removed every candidate change pixel — thresholds/window sizes "
                "may be too aggressive for this scene"
            )
        return cleaned, details, warnings

    return run_step(
        "morphological_cleanup",
        "Removed speckle-scale noise via binary opening + small-object removal",
        _fn,
    )


def to_geojson(
    cleaned_mask: np.ndarray,
    blobs: list[dict[str, Any]],
    transform: Affine = IDENTITY_TRANSFORM,
    crs: str = "EPSG:4326",
    pixel_area_sqm: float | None = None,
    include_classifications: tuple[str, ...] = ("man_made",),
) -> tuple[dict[str, Any], StepReport]:
    """Vectorize the labeled change blobs into a georeferenced GeoJSON FeatureCollection.

    `blobs` is the discrimination-stage output (each has a `label` matching
    a connected-component id, plus confidence/classification/reasons).
    Only blobs whose classification is in `include_classifications` are
    emitted as features — by default this is where "ignore natural
    changes" actually takes effect on the final deliverable, not just in
    scoring.
    """
    from skimage.measure import label as relabel

    def _fn():
        labeled = relabel(cleaned_mask, connectivity=2)
        blob_by_label = {b["label"]: b for b in blobs}

        features = []
        skipped_by_classification: dict[str, int] = {}
        for geom, value in rio_shapes(
            labeled.astype(np.int32), mask=cleaned_mask, transform=transform
        ):
            label_id = int(value)
            blob = blob_by_label.get(label_id)
            if blob is None:
                continue
            if blob["classification"] not in include_classifications:
                skipped_by_classification[blob["classification"]] = (
                    skipped_by_classification.get(blob["classification"], 0) + 1
                )
                continue

            poly = shapely_shape(geom)
            area_sqm = (
                float(blob["area_px"]) * pixel_area_sqm
                if pixel_area_sqm is not None
                else None
            )
            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "change_id": label_id,
                        "classification": blob["classification"],
                        "confidence": round(blob["confidence"], 3),
                        "area_px": blob["area_px"],
                        "area_sqm": area_sqm,
                        "reasons": blob["reasons"],
                    },
                }
            )

        feature_collection = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": crs}},
            "features": features,
        }

        details = {
            "features_emitted": len(features),
            "included_classifications": list(include_classifications),
            "skipped_by_classification": skipped_by_classification,
            "crs": crs,
        }
        warnings: list[str] = []
        if not features:
            warnings.append("no blobs matched the included classifications — output GeoJSON is empty")

        return feature_collection, details, warnings

    return run_step(
        "vectorize_to_geojson",
        "Traced classified change blobs into georeferenced polygons",
        _fn,
    )
