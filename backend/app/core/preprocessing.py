"""SAR-specific preprocessing: speckle filtering and calibration helpers.

Sentinel-1 GRD scenes pulled from Earth Engine are already radiometrically
calibrated (sigma-nought) and terrain-corrected, so the only preprocessing
this module needs to own locally is speckle suppression — SAR's
multiplicative granular noise, which corrupts a naive pixel-difference or
log-ratio change map with false alarms if left in. We use the Lee filter
(the standard adaptive speckle filter used across SAR literature): it
preserves edges by blending the noisy pixel with the local mean in
proportion to local homogeneity, rather than blurring uniformly like a
plain mean filter would.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from app.core.audit import StepReport, run_step

# Sentinel-1 IW GRD nominal equivalent number of looks; controls how much
# the Lee filter trusts the local variance estimate vs. the local mean.
DEFAULT_ENL = 4.9


def lee_filter(image: np.ndarray, window_size: int = 7, enl: float = DEFAULT_ENL) -> np.ndarray:
    """Adaptive Lee speckle filter.

    image: linear-scale SAR intensity/amplitude array (NOT dB).
    window_size: odd integer, size of the local averaging window.
    enl: equivalent number of looks of the sensor, controls noise variance.
    """
    if window_size % 2 == 0:
        raise ValueError("window_size must be odd")

    img = image.astype(np.float64)
    mean = uniform_filter(img, size=window_size)
    mean_sq = uniform_filter(img * img, size=window_size)
    variance = np.maximum(mean_sq - mean * mean, 0.0)

    # Noise variance under the multiplicative speckle model.
    noise_var = (mean**2) / enl
    # Weight: how much of the local mean to trust vs. the raw pixel.
    with np.errstate(divide="ignore", invalid="ignore"):
        weight = variance / (variance + noise_var)
    weight = np.nan_to_num(weight, nan=0.0, posinf=1.0, neginf=0.0)
    weight = np.clip(weight, 0.0, 1.0)

    filtered = mean + weight * (img - mean)
    return filtered.astype(np.float64)


def to_decibels(linear_image: np.ndarray) -> np.ndarray:
    """Convert linear SAR intensity to dB (10*log10), clamping to avoid log(0)."""
    safe = np.clip(linear_image, 1e-6, None)
    return 10.0 * np.log10(safe)


def preprocess_pair(
    pre_image: np.ndarray,
    post_image: np.ndarray,
    window_size: int = 7,
    enl: float = DEFAULT_ENL,
) -> tuple[tuple[np.ndarray, np.ndarray], StepReport]:
    """Speckle-filter a coregistered pre/post SAR intensity pair.

    Returns the filtered (pre, post) arrays plus a StepReport describing
    what was applied — this is the first audited stage of the pipeline.
    """
    if pre_image.shape != post_image.shape:
        raise ValueError(
            f"pre/post image shape mismatch: {pre_image.shape} vs {post_image.shape} "
            "— images must be coregistered onto the same grid before change detection"
        )

    def _fn():
        pre_filtered = lee_filter(pre_image, window_size=window_size, enl=enl)
        post_filtered = lee_filter(post_image, window_size=window_size, enl=enl)
        details = {
            "window_size": window_size,
            "enl": enl,
            "shape": list(pre_image.shape),
            "pre_mean_before": float(np.mean(pre_image)),
            "pre_mean_after": float(np.mean(pre_filtered)),
            "post_mean_before": float(np.mean(post_image)),
            "post_mean_after": float(np.mean(post_filtered)),
        }
        warnings: list[str] = []
        if min(pre_image.shape) < window_size * 3:
            warnings.append(
                "image is small relative to the filter window; edge effects may be significant"
            )
        return (pre_filtered, post_filtered), details, warnings

    return run_step(
        "speckle_filter",
        "Applied adaptive Lee speckle filter to pre/post SAR intensity pair",
        _fn,
    )
