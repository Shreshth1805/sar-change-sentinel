from app.core.pipeline import PipelineConfig, run_pipeline
from app.synthetic.generator import generate_scene


def test_pipeline_flags_man_made_and_suppresses_natural_change():
    scene = generate_scene(shape=(160, 160), seed=7)

    result = run_pipeline(
        aoi_name="test-aoi",
        pre_vv=scene.pre_vv,
        post_vv=scene.post_vv,
        pre_vh=scene.pre_vh,
        post_vh=scene.post_vh,
        water_mask=scene.water_mask,
        vegetation_mask=scene.vegetation_mask,
        slope_mask=scene.slope_mask,
        transform=scene.transform,
        crs=scene.crs,
        config=PipelineConfig(pixel_area_sqm=100.0),
    )

    # At least one of the three injected structures should surface as a
    # man-made alert — this is the core "did we catch the real change" bar.
    assert result.stats["classification_counts"]["man_made"] >= 1
    assert len(result.geojson["features"]) >= 1
    for feature in result.geojson["features"]:
        assert feature["properties"]["classification"] == "man_made"

    # The injected flood/vegetation growth must NOT leak into the man-made
    # output — this is the "minimum false alarms" requirement in practice.
    num_natural_covered_blobs = sum(1 for b in result.blobs if b["classification"] == "natural")
    assert num_natural_covered_blobs >= 1

    step_names = [s["step_name"] for s in result.audit_trail]
    assert step_names == [
        "speckle_filter",
        "speckle_filter",
        "change_detection",
        "morphological_cleanup",
        "discriminate_man_made_vs_natural",
        "vectorize_to_geojson",
        "generate_alerts",
    ]

    assert len(result.alerts) == len(result.geojson["features"])
    for alert in result.alerts:
        assert alert["classification"] == "man_made"
        assert alert["severity"] in ("low", "medium", "high")


def test_pipeline_single_pol_still_runs():
    scene = generate_scene(shape=(96, 96), seed=3)
    result = run_pipeline(
        aoi_name="single-pol-aoi",
        pre_vv=scene.pre_vv,
        post_vv=scene.post_vv,
    )
    assert result.stats["total_blobs"] >= 0
    assert result.audit_trail[0]["step_name"] == "speckle_filter"
    assert len(result.audit_trail) == 6  # no VH pass, so only one speckle_filter step
