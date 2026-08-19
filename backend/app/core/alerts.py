"""Turn confirmed man-made-change polygons into alert records.

Kept deliberately simple: an alert is just a structured record (severity,
area, location, confidence, reasons) derived from the GeoJSON features.
Wiring these to an actual notification channel (email/webhook/SMS) is an
integration concern for a specific deployment, not the detection pipeline
— `generate_alerts` returns plain dicts the API layer can serve, persist,
or forward.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.audit import StepReport, run_step

# Area cutoffs (sqm) used only when pixel_area_sqm was available upstream;
# otherwise severity falls back to confidence alone.
SEVERITY_AREA_HIGH_SQM = 2000.0
SEVERITY_AREA_MEDIUM_SQM = 300.0


def _severity(confidence: float, area_sqm: float | None) -> str:
    if area_sqm is not None:
        if area_sqm >= SEVERITY_AREA_HIGH_SQM and confidence >= 0.7:
            return "high"
        if area_sqm >= SEVERITY_AREA_MEDIUM_SQM or confidence >= 0.75:
            return "medium"
        return "low"
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def generate_alerts(
    geojson: dict[str, Any],
    aoi_name: str,
    detected_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], StepReport]:
    detected_at = detected_at or datetime.now(timezone.utc)

    def _fn():
        alerts = []
        for feature in geojson.get("features", []):
            props = feature["properties"]
            severity = _severity(props["confidence"], props.get("area_sqm"))
            centroid = _centroid_of(feature["geometry"])
            alerts.append(
                {
                    "alert_id": f"{aoi_name}-{props['change_id']}-{int(detected_at.timestamp())}",
                    "aoi_name": aoi_name,
                    "detected_at": detected_at.isoformat(),
                    "severity": severity,
                    "classification": props["classification"],
                    "confidence": props["confidence"],
                    "area_sqm": props.get("area_sqm"),
                    "centroid": centroid,
                    "reasons": props["reasons"],
                    "geometry": feature["geometry"],
                }
            )

        severity_counts: dict[str, int] = {}
        for a in alerts:
            severity_counts[a["severity"]] = severity_counts.get(a["severity"], 0) + 1

        details = {
            "aoi_name": aoi_name,
            "alert_count": len(alerts),
            "severity_counts": severity_counts,
        }
        warnings: list[str] = []
        return alerts, details, warnings

    return run_step(
        "generate_alerts",
        "Converted confirmed man-made change polygons into alert records",
        _fn,
    )


def _centroid_of(geometry: dict[str, Any]) -> list[float]:
    from shapely.geometry import shape

    c = shape(geometry).centroid
    return [c.x, c.y]
