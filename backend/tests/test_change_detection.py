import numpy as np

from app.core.change_detection import adaptive_threshold, detect_change, log_ratio


def test_log_ratio_zero_for_identical_images():
    img = np.full((10, 10), 0.2)
    lr = log_ratio(img, img)
    assert np.allclose(lr, 0.0, atol=1e-6)


def test_log_ratio_positive_when_post_brighter():
    pre = np.full((5, 5), 0.1)
    post = np.full((5, 5), 0.5)
    lr = log_ratio(pre, post)
    assert np.all(lr > 0)


def test_adaptive_threshold_separates_bimodal_distribution():
    rng = np.random.default_rng(0)
    low = rng.normal(0.1, 0.02, size=5000)
    high = rng.normal(1.0, 0.05, size=500)
    combined = np.concatenate([low, high])
    t = adaptive_threshold(combined)
    assert 0.1 < t < 1.0


def test_detect_change_flags_injected_bright_patch():
    rng = np.random.default_rng(1)
    shape = (64, 64)
    pre = 0.15 + 0.01 * rng.standard_normal(shape)
    post = pre.copy()
    post[20:30, 20:30] = 0.9  # injected strong change

    result, report = detect_change(pre, post)
    mask = result["change_mask"]

    assert mask[24, 24]  # center of injected patch flagged
    assert not mask[5, 5]  # untouched background not flagged
    assert report.step_name == "change_detection"
    assert 0.0 < report.details["changed_pixel_fraction"] < 0.5


def test_detect_change_dual_pol_uses_cva():
    rng = np.random.default_rng(2)
    shape = (32, 32)
    pre_vv = 0.15 + 0.01 * rng.standard_normal(shape)
    post_vv = pre_vv.copy()
    pre_vh = 0.05 + 0.005 * rng.standard_normal(shape)
    post_vh = pre_vh.copy()
    post_vv[10:15, 10:15] = 0.6
    post_vh[10:15, 10:15] = 0.35

    result, report = detect_change(pre_vv, post_vv, pre_vh, post_vh)
    assert report.details["method"] == "change_vector_analysis_vv_vh"
    assert result["change_mask"][12, 12]
