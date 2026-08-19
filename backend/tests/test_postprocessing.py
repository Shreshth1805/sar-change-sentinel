import numpy as np
from affine import Affine

from app.core.discrimination import classify_blobs
from app.core.postprocessing import cleanup_mask, to_geojson


def test_cleanup_removes_isolated_noise_pixels():
    mask = np.zeros((50, 50), dtype=bool)
    mask[5, 5] = True  # isolated speckle-scale noise
    mask[20:30, 20:30] = True  # real 10x10 blob

    cleaned, report = cleanup_mask(mask, opening_size=3, min_size_px=8)
    assert not cleaned[5, 5]
    assert cleaned[25, 25]
    assert report.details["pixels_removed_as_noise"] >= 1


def test_to_geojson_only_emits_included_classifications():
    mask = np.zeros((50, 50), dtype=bool)
    mask[5:15, 5:15] = True  # compact -> likely man_made
    mask[30:40, 30:40] = True
    water = np.zeros((50, 50), dtype=bool)
    water[30:40, 30:40] = True  # forces the second blob to "natural"

    blobs, _ = classify_blobs(mask, water_mask=water)
    transform = Affine.translation(77.0, 28.0) * Affine.scale(0.0001, -0.0001)

    geojson, report = to_geojson(mask, blobs, transform=transform, crs="EPSG:4326")

    classifications = {f["properties"]["classification"] for f in geojson["features"]}
    assert classifications == {"man_made"}
    assert geojson["type"] == "FeatureCollection"
    assert report.details["features_emitted"] == len(geojson["features"])


def test_to_geojson_includes_natural_when_requested():
    mask = np.zeros((50, 50), dtype=bool)
    mask[30:40, 30:40] = True
    water = np.zeros((50, 50), dtype=bool)
    water[30:40, 30:40] = True

    blobs, _ = classify_blobs(mask, water_mask=water)
    geojson, _ = to_geojson(mask, blobs, include_classifications=("man_made", "natural", "uncertain"))
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["properties"]["classification"] == "natural"
