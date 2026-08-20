"""AOI tiling: cover an area bigger than one safe single-request tile by
splitting it into a grid of smaller AOIs, running the ordinary single-tile
pipeline on each, and merging the results into one combined view.

This is deliberately the boring, honest version of "scale to huge areas":
no background job queue, no live progress stream — one synchronous request
that runs N tiles in sequence and returns everything at once, capped at a
tile count that keeps total runtime bounded. A real production system
would run tiles as independent parallel jobs behind a queue (exactly the
architecture `docs/PITCH.md` describes), but that's a genuinely different
piece of infrastructure, not a tweak to this pipeline.

A single tile failing (e.g. no Sentinel-1 scenes in that specific slice of
the grid) does not abort the whole region — it's recorded and the rest of
the grid still runs, consistent with "no silent data loss": every tile's
outcome is reported, not swallowed.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.core.pipeline import PipelineResult


@dataclass
class TileSpec:
    index: int
    row: int
    col: int
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def geojson(self) -> dict[str, Any]:
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [self.min_lon, self.min_lat],
                    [self.max_lon, self.min_lat],
                    [self.max_lon, self.max_lat],
                    [self.min_lon, self.max_lat],
                    [self.min_lon, self.min_lat],
                ]
            ],
        }


@dataclass
class TileGrid:
    tiles: list[TileSpec]
    rows: int
    cols: int
    requested_tiles: int  # how many tiles the raw AOI would have needed, before capping


def build_tile_grid(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    tile_km: float,
    max_tiles: int,
) -> TileGrid:
    """Split a bounding box into a grid of ~tile_km x tile_km cells.

    If the full grid would exceed `max_tiles`, the grid is shrunk (kept
    square-ish, centered on the original bbox) rather than silently
    processing an unbounded number of tiles — `requested_tiles` on the
    result still reports the uncapped count so callers can tell the user
    "we covered N of M tiles" instead of pretending the whole area was
    processed.
    """
    if tile_km <= 0:
        raise ValueError("tile_km must be positive")

    deg_per_km_lat = 1.0 / 111.32
    center_lat = (min_lat + max_lat) / 2
    deg_per_km_lon = 1.0 / (111.32 * max(math.cos(math.radians(center_lat)), 1e-6))

    tile_h_deg = tile_km * deg_per_km_lat
    tile_w_deg = tile_km * deg_per_km_lon

    full_rows = max(1, math.ceil((max_lat - min_lat) / tile_h_deg))
    full_cols = max(1, math.ceil((max_lon - min_lon) / tile_w_deg))
    requested = full_rows * full_cols

    rows, cols = full_rows, full_cols
    if requested > max_tiles:
        scale = math.sqrt(max_tiles / requested)
        rows = max(1, math.floor(full_rows * scale))
        cols = max(1, math.floor(full_cols * scale))

    # Center the (possibly shrunk) grid on the original bbox's center.
    grid_h = rows * tile_h_deg
    grid_w = cols * tile_w_deg
    center_lon = (min_lon + max_lon) / 2
    grid_min_lat = center_lat - grid_h / 2
    grid_min_lon = center_lon - grid_w / 2

    tiles: list[TileSpec] = []
    idx = 0
    for r in range(rows):
        for c in range(cols):
            t_min_lat = grid_min_lat + r * tile_h_deg
            t_min_lon = grid_min_lon + c * tile_w_deg
            tiles.append(
                TileSpec(
                    index=idx,
                    row=r,
                    col=c,
                    min_lon=t_min_lon,
                    min_lat=t_min_lat,
                    max_lon=t_min_lon + tile_w_deg,
                    max_lat=t_min_lat + tile_h_deg,
                )
            )
            idx += 1

    return TileGrid(tiles=tiles, rows=rows, cols=cols, requested_tiles=requested)


def run_region(
    aoi_name: str,
    grid: TileGrid,
    tile_km: float,
    bounds: tuple[float, float, float, float],
    run_tile: Callable[[TileSpec], PipelineResult],
) -> tuple[PipelineResult, dict[str, Any]]:
    """Run `run_tile` on every tile in `grid`, merging successful results
    into one PipelineResult (so it flows through the exact same API
    serialization as a single-tile job) plus a `region_meta` dict describing
    the grid and per-tile outcomes for anything that wants the detail.
    """
    start = time.perf_counter()

    features: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []
    counts = {"man_made": 0, "natural": 0, "uncertain": 0}
    changed_frac_sum = 0.0
    otsu_sum = 0.0
    pixel_area_sqm: float | None = None
    ok_count = 0
    tile_outcomes: list[dict[str, Any]] = []

    for tile in grid.tiles:
        try:
            result = run_tile(tile)
        except Exception as exc:
            tile_outcomes.append(
                {
                    "tile_index": tile.index,
                    "row": tile.row,
                    "col": tile.col,
                    "bounds": [tile.min_lon, tile.min_lat, tile.max_lon, tile.max_lat],
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        ok_count += 1
        for feature in result.geojson.get("features", []):
            feature = dict(feature)
            props = dict(feature["properties"])
            props["change_id"] = f"{tile.index}-{props['change_id']}"
            props["tile_index"] = tile.index
            feature["properties"] = props
            features.append(feature)
        for alert in result.alerts:
            alert = dict(alert)
            alert["alert_id"] = f"{tile.index}-{alert['alert_id']}"
            alert["tile_index"] = tile.index
            alerts.append(alert)
        for blob in result.blobs:
            blob = dict(blob)
            blob["tile_index"] = tile.index
            blobs.append(blob)

        for key in counts:
            counts[key] += result.stats["classification_counts"][key]
        changed_frac_sum += result.stats["changed_pixel_fraction"]
        otsu_sum += result.stats["otsu_threshold"]
        if pixel_area_sqm is None:
            pixel_area_sqm = result.stats.get("pixel_area_sqm")

        tile_outcomes.append(
            {
                "tile_index": tile.index,
                "row": tile.row,
                "col": tile.col,
                "bounds": [tile.min_lon, tile.min_lat, tile.max_lon, tile.max_lat],
                "status": "ok",
                "stats": result.stats,
            }
        )

    duration_ms = (time.perf_counter() - start) * 1000
    failed_count = len(grid.tiles) - ok_count

    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features,
    }

    stats = {
        "changed_pixel_fraction": (changed_frac_sum / ok_count) if ok_count else 0.0,
        "total_blobs": len(blobs),
        "classification_counts": counts,
        "alerts_generated": len(alerts),
        "otsu_threshold": (otsu_sum / ok_count) if ok_count else 0.0,
        "pixel_area_sqm": pixel_area_sqm,
    }

    warnings = [f"tile {o['tile_index']} (row {o['row']}, col {o['col']}) failed: {o['error']}" for o in tile_outcomes if o["status"] == "failed"]
    if grid.requested_tiles > len(grid.tiles):
        warnings.append(
            f"AOI needed {grid.requested_tiles} tiles at {tile_km}km each but only "
            f"{len(grid.tiles)} were processed (capped) — a centered subset of the full area is shown, not all of it"
        )

    audit_trail = [
        {
            "step_name": "tile_region",
            "description": f"Split the AOI into a {grid.rows}x{grid.cols} grid of {tile_km}km tiles and ran the full pipeline on each",
            "duration_ms": round(duration_ms, 2),
            "details": {
                "grid_rows": grid.rows,
                "grid_cols": grid.cols,
                "tile_km": tile_km,
                "requested_tiles": grid.requested_tiles,
                "processed_tiles": len(grid.tiles),
                "successful_tiles": ok_count,
                "failed_tiles": failed_count,
            },
            "warnings": warnings,
        }
    ]

    result = PipelineResult(
        aoi_name=aoi_name,
        geojson=geojson,
        alerts=alerts,
        blobs=blobs,
        audit_trail=audit_trail,
        stats=stats,
    )

    region_meta = {
        "grid_rows": grid.rows,
        "grid_cols": grid.cols,
        "tile_km": tile_km,
        "requested_tiles": grid.requested_tiles,
        "processed_tiles": len(grid.tiles),
        "successful_tiles": ok_count,
        "failed_tiles": failed_count,
        "bounds": list(bounds),
        "tiles": tile_outcomes,
    }

    return result, region_meta
