import numpy as np

from app.core.discrimination import classify_blobs


def _canvas():
    return np.zeros((100, 100), dtype=bool)


def test_compact_blob_scores_toward_man_made():
    mask = _canvas()
    mask[40:50, 40:50] = True  # 10x10 compact square

    blobs, report = classify_blobs(mask)
    assert len(blobs) == 1
    assert blobs[0]["classification"] in ("man_made", "uncertain")
    assert blobs[0]["confidence"] >= 0.5


def test_water_overlap_pushes_toward_natural():
    mask = _canvas()
    mask[10:40, 10:40] = True  # large irregular-ish region
    water = _canvas()
    water[10:40, 10:40] = True  # fully overlapping water

    blobs, report = classify_blobs(mask, water_mask=water)
    assert blobs[0]["classification"] == "natural"
    assert any("water" in r for r in blobs[0]["reasons"])


def test_vegetation_overlap_pushes_toward_natural():
    mask = _canvas()
    mask[5:35, 5:35] = True
    veg = _canvas()
    veg[5:35, 5:35] = True

    blobs, report = classify_blobs(mask, vegetation_mask=veg)
    assert blobs[0]["classification"] == "natural"


def test_small_blobs_dropped_below_min_size():
    mask = _canvas()
    mask[0, 0] = True  # single pixel
    mask[50:60, 50:60] = True  # real blob

    blobs, report = classify_blobs(mask, min_blob_pixels=8)
    assert len(blobs) == 1
    assert report.details["dropped_below_min_size"] == 1


def test_compact_man_made_beats_irregular_natural_in_same_scene():
    mask = _canvas()
    mask[10:20, 10:20] = True  # compact square: man-made-like

    rows, cols = np.indices((100, 100))
    center = (70, 70)
    dist = np.sqrt((rows - center[0]) ** 2 + (cols - center[1]) ** 2)
    angle = np.arctan2(rows - center[0], cols - center[1])
    irregular = dist < (15 + 6 * np.sin(angle * 3))
    mask |= irregular

    water = _canvas()
    water[irregular] = True

    blobs, report = classify_blobs(mask, water_mask=water)
    by_class = {b["classification"] for b in blobs}
    assert "man_made" in by_class or "uncertain" in by_class
    assert "natural" in by_class
