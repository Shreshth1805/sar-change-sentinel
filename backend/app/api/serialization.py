"""Strip non-JSON-serializable fields (numpy pixel-coord arrays) from pipeline
internals before they cross the API boundary. Keeps the JSON contract
`types.ts` mirrors on the frontend explicit in one place.
"""

from __future__ import annotations

from typing import Any

from app.core.pipeline import PipelineResult


def blob_to_api(blob: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": blob["label"],
        "area_px": blob["area_px"],
        "bbox": blob["bbox"],
        "centroid": blob["centroid"],
        "shape_features": blob["shape_features"],
        "confidence": blob["confidence"],
        "classification": blob["classification"],
        "reasons": blob["reasons"],
    }


def result_to_api(result: PipelineResult) -> dict[str, Any]:
    return {
        "aoi_name": result.aoi_name,
        "geojson": result.geojson,
        "alerts": result.alerts,
        "blobs": [blob_to_api(b) for b in result.blobs],
        "audit_trail": result.audit_trail,
        "stats": result.stats,
    }
