"""Core SAR change detection: log-ratio / change-vector-analysis + adaptive thresholding.

Why log-ratio instead of a plain difference: SAR speckle is multiplicative,
not additive, so `post - pre` has noise that scales with brightness and a
single global threshold can't separate signal from noise. `log(post / pre)`
turns the multiplicative noise into additive noise with roughly constant
variance, which is why it's the standard first step in SAR change-detection
literature (Bazi et al., Bruzzone & Prieto) and is what lets one global
Otsu threshold work reasonably well across the whole scene.

When both VV and VH polarizations are available we combine them with
Change Vector Analysis (CVA): treat (log-ratio_VV, log-ratio_VH) as a 2D
vector per pixel and threshold on its magnitude. This catches changes that
show up more strongly in cross-pol (VH) than co-pol (VV) — e.g. new
built structures often perturb the depolarized return more than a plain
single-pol log-ratio would show.
"""

from __future__ import annotations

import numpy as np
from skimage.filters import threshold_otsu

from app.core.audit import StepReport, run_step


def log_ratio(pre: np.ndarray, post: np.ndarray) -> np.ndarray:
    """Pixelwise log-ratio image: log(post / pre). Robust to multiplicative speckle."""
    eps = 1e-6
    ratio = (post + eps) / (pre + eps)
    return np.log(ratio)


def change_vector_magnitude(log_ratio_vv: np.ndarray, log_ratio_vh: np.ndarray) -> np.ndarray:
    """Euclidean magnitude of the (VV, VH) log-ratio change vector per pixel."""
    return np.sqrt(log_ratio_vv**2 + log_ratio_vh**2)


def adaptive_threshold(magnitude: np.ndarray) -> float:
    """Otsu's method: pick the threshold that best separates changed/unchanged
    populations in the magnitude image's histogram, with no manual tuning."""
    finite = magnitude[np.isfinite(magnitude)]
    if finite.size == 0 or np.allclose(finite.std(), 0.0):
        return float(np.max(magnitude)) if magnitude.size else 0.0
    return float(threshold_otsu(finite))


def detect_change(
    pre_vv: np.ndarray,
    post_vv: np.ndarray,
    pre_vh: np.ndarray | None = None,
    post_vh: np.ndarray | None = None,
    threshold_multiplier: float = 1.0,
) -> tuple[dict, StepReport]:
    """Run log-ratio (single-pol) or CVA (dual-pol) change detection with Otsu thresholding.

    Returns a dict with:
      - magnitude: float array, per-pixel change magnitude
      - threshold: float, the Otsu-derived cutoff actually used
      - change_mask: bool array, magnitude > threshold
    plus a StepReport recording the method and resulting change fraction.
    """
    dual_pol = pre_vh is not None and post_vh is not None

    def _fn():
        lr_vv = log_ratio(pre_vv, post_vv)
        if dual_pol:
            lr_vh = log_ratio(pre_vh, post_vh)
            magnitude = change_vector_magnitude(lr_vv, lr_vh)
            method = "change_vector_analysis_vv_vh"
        else:
            magnitude = np.abs(lr_vv)
            method = "log_ratio_single_pol"

        base_threshold = adaptive_threshold(magnitude)
        threshold = base_threshold * threshold_multiplier
        change_mask = magnitude > threshold

        changed_fraction = float(np.mean(change_mask))
        details = {
            "method": method,
            "otsu_threshold": base_threshold,
            "threshold_multiplier": threshold_multiplier,
            "effective_threshold": threshold,
            "changed_pixel_fraction": changed_fraction,
            "changed_pixel_count": int(np.sum(change_mask)),
            "total_pixels": int(change_mask.size),
        }
        warnings: list[str] = []
        if changed_fraction > 0.35:
            warnings.append(
                "over 35% of pixels flagged as changed — likely miscoregistration or "
                "a wide-area natural event (flood/snow); verify AOI alignment before trusting alerts"
            )
        result = {
            "magnitude": magnitude,
            "threshold": threshold,
            "change_mask": change_mask,
        }
        return result, details, warnings

    return run_step(
        "change_detection",
        "Computed SAR log-ratio / CVA change magnitude and Otsu-adaptive threshold",
        _fn,
    )
