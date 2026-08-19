"""Synthetic SAR-scene generator — lets the whole pipeline run and the demo
UI show real results without a Google Earth Engine account or a network
call. Not a mock of the algorithm (the pipeline never knows its input was
synthetic); it's a stand-in for the *data*, built to be adversarial in
exactly the way that matters: it injects both man-made-like changes
(compact bright rectangles = new structures) and natural-like changes
(sprawling water/vegetation growth) into the same scene, so a pipeline
that can't actually discriminate between them will visibly fail on it.

Also used directly by the test suite, since it produces deterministic
scenes (given a seed) with known ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from affine import Affine

# Sentinel-1 IW GRD nominal ground range pixel spacing in metres.
PIXEL_SIZE_M = 10.0
ENL = 4.9


@dataclass
class SyntheticScene:
    pre_vv: np.ndarray
    post_vv: np.ndarray
    pre_vh: np.ndarray
    post_vh: np.ndarray
    water_mask: np.ndarray
    vegetation_mask: np.ndarray
    slope_mask: np.ndarray
    transform: Affine
    crs: str
    ground_truth: list[dict] = field(default_factory=list)


def _speckle(base: np.ndarray, enl: float, rng: np.random.Generator) -> np.ndarray:
    """Apply multiplicative gamma-distributed speckle at the given ENL — the
    standard SAR intensity noise model (shape=ENL, mean=1)."""
    noise = rng.gamma(shape=enl, scale=1.0 / enl, size=base.shape)
    return base * noise


def _rect_mask(shape: tuple[int, int], r0: int, c0: int, h: int, w: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    mask[r0 : r0 + h, c0 : c0 + w] = True
    return mask


def _blob_mask(shape: tuple[int, int], center: tuple[int, int], radius: int, rng: np.random.Generator) -> np.ndarray:
    """An irregular organic blob (for water/vegetation), built from a noisy
    radius-per-angle polygon rather than a perfect circle, to keep shape
    features (compactness/solidity) realistically low."""
    rows, cols = np.indices(shape)
    dr, dc = rows - center[0], cols - center[1]
    dist = np.sqrt(dr**2 + dc**2)
    angle = np.arctan2(dr, dc)
    wobble = 1.0 + 0.35 * np.sin(angle * 3 + rng.uniform(0, 6.28)) + 0.15 * np.sin(angle * 7)
    return dist < radius * wobble


def generate_scene(
    shape: tuple[int, int] = (256, 256),
    seed: int | None = 42,
    origin_lon: float = 77.2090,
    origin_lat: float = 28.6139,
) -> SyntheticScene:
    """Generate a synthetic before/after Sentinel-1-like VV+VH scene pair
    centered near the given lon/lat (default: New Delhi), with injected
    man-made and natural changes and matching ancillary masks.
    """
    rng = np.random.default_rng(seed)
    h, w = shape

    # --- background terrain reflectivity (low-frequency texture) ---
    base_vv = 0.15 + 0.05 * rng.standard_normal(shape).clip(-1, 1)
    base_vv = np.clip(base_vv, 0.02, None)
    base_vh = base_vv * 0.35  # cross-pol is typically much dimmer than co-pol

    # --- static water body (river bend) ---
    water_mask = _blob_mask(shape, center=(int(h * 0.75), int(w * 0.25)), radius=min(h, w) * 0.14, rng=rng)
    base_vv[water_mask] = 0.02  # smooth water = very low backscatter
    base_vh[water_mask] = 0.01

    # --- static vegetation patch ---
    vegetation_mask = _blob_mask(shape, center=(int(h * 0.3), int(w * 0.7)), radius=min(h, w) * 0.22, rng=rng)
    base_vv[vegetation_mask] = np.clip(base_vv[vegetation_mask] * 1.4, 0.05, None)
    base_vh[vegetation_mask] = np.clip(base_vh[vegetation_mask] * 1.8, 0.02, None)

    # --- steep slope zone (independent of backscatter, purely ancillary) ---
    slope_mask = _blob_mask(shape, center=(int(h * 0.15), int(w * 0.15)), radius=min(h, w) * 0.12, rng=rng)

    pre_vv = _speckle(base_vv, ENL, rng)
    pre_vh = _speckle(base_vh, ENL, rng)

    post_base_vv = base_vv.copy()
    post_base_vh = base_vh.copy()
    ground_truth = []

    # --- inject man-made changes: compact bright rectangles (new structures) ---
    for i in range(3):
        rh, rw = rng.integers(6, 14), rng.integers(6, 14)
        r0 = rng.integers(10, h - rh - 10)
        c0 = rng.integers(10, w - rw - 10)
        if water_mask[r0 : r0 + rh, c0 : c0 + rw].any() or vegetation_mask[r0 : r0 + rh, c0 : c0 + rw].any():
            continue
        m = _rect_mask(shape, r0, c0, rh, rw)
        post_base_vv[m] = 0.55 + 0.1 * rng.random()
        post_base_vh[m] = 0.30 + 0.08 * rng.random()
        ground_truth.append(
            {"type": "man_made", "bbox": [int(r0), int(c0), int(rh), int(rw)], "label": f"new_structure_{i}"}
        )

    # --- inject natural change: flood expansion of the water body ---
    flood_mask = _blob_mask(shape, center=(int(h * 0.75), int(w * 0.25)), radius=min(h, w) * 0.20, rng=rng)
    flood_only = flood_mask & ~water_mask
    post_base_vv[flood_only] = 0.02
    post_base_vh[flood_only] = 0.01
    ground_truth.append({"type": "natural_flood", "pixels": int(flood_only.sum())})

    # --- inject natural change: vegetation growth/seasonal shift ---
    veg_growth = _blob_mask(
        shape, center=(int(h * 0.3), int(w * 0.7)), radius=min(h, w) * 0.29, rng=rng
    ) & ~vegetation_mask
    post_base_vv[veg_growth] = np.clip(post_base_vv[veg_growth] * 1.4, 0.05, None)
    post_base_vh[veg_growth] = np.clip(post_base_vh[veg_growth] * 1.8, 0.02, None)
    ground_truth.append({"type": "natural_vegetation", "pixels": int(veg_growth.sum())})

    post_vv = _speckle(post_base_vv, ENL, rng)
    post_vh = _speckle(post_base_vh, ENL, rng)

    # Post-hoc vegetation mask reflects the grown extent (as an NDVI-derived
    # mask from a post-date optical pass would show).
    vegetation_mask_post = vegetation_mask | veg_growth
    water_mask_post = water_mask | flood_only

    # Roughly 10m pixels, north-up, anchored at the given lon/lat.
    deg_per_m = 1.0 / 111_320.0
    px_deg = PIXEL_SIZE_M * deg_per_m
    transform = Affine.translation(origin_lon, origin_lat) * Affine.scale(px_deg, -px_deg)

    return SyntheticScene(
        pre_vv=pre_vv,
        post_vv=post_vv,
        pre_vh=pre_vh,
        post_vh=post_vh,
        water_mask=water_mask_post,
        vegetation_mask=vegetation_mask_post,
        slope_mask=slope_mask,
        transform=transform,
        crs="EPSG:4326",
        ground_truth=ground_truth,
    )
