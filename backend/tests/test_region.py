from app.core import region
from app.core.pipeline import PipelineConfig, run_pipeline
from app.synthetic.generator import generate_scene


def test_build_tile_grid_single_tile_for_small_bbox():
    grid = region.build_tile_grid(77.0, 28.0, 77.02, 28.02, tile_km=6.0, max_tiles=25)
    assert grid.rows == 1
    assert grid.cols == 1
    assert grid.requested_tiles == 1
    assert len(grid.tiles) == 1


def test_build_tile_grid_caps_large_area():
    # ~1 degree square (~110km) at 6km tiles would need a huge grid; must be capped.
    grid = region.build_tile_grid(77.0, 28.0, 78.0, 29.0, tile_km=6.0, max_tiles=9)
    assert grid.requested_tiles > 9
    assert len(grid.tiles) <= 9
    assert grid.rows * grid.cols == len(grid.tiles)


def test_build_tile_grid_tiles_cover_expected_extent():
    grid = region.build_tile_grid(77.0, 28.0, 77.1, 28.1, tile_km=6.0, max_tiles=25)
    lons = [t.min_lon for t in grid.tiles] + [t.max_lon for t in grid.tiles]
    lats = [t.min_lat for t in grid.tiles] + [t.max_lat for t in grid.tiles]
    # grid should be roughly centered on the requested bbox, not off in a corner
    bbox_center_lon, bbox_center_lat = 77.05, 28.05
    grid_center_lon = (min(lons) + max(lons)) / 2
    grid_center_lat = (min(lats) + max(lats)) / 2
    assert abs(grid_center_lon - bbox_center_lon) < 0.02
    assert abs(grid_center_lat - bbox_center_lat) < 0.02


def test_run_region_merges_tile_results():
    grid = region.build_tile_grid(77.0, 28.0, 77.02, 28.02, tile_km=2.0, max_tiles=9)
    assert len(grid.tiles) >= 2  # a 2x1 or similar small grid

    def run_tile(tile: region.TileSpec):
        scene = generate_scene(
            shape=(120, 120), seed=100 + tile.index, origin_lon=tile.min_lon, origin_lat=tile.max_lat
        )
        config = PipelineConfig(pixel_area_sqm=100.0)
        return run_pipeline(
            aoi_name=f"tile-{tile.index}",
            pre_vv=scene.pre_vv,
            post_vv=scene.post_vv,
            pre_vh=scene.pre_vh,
            post_vh=scene.post_vh,
            water_mask=scene.water_mask,
            vegetation_mask=scene.vegetation_mask,
            slope_mask=scene.slope_mask,
            transform=scene.transform,
            crs=scene.crs,
            config=config,
        )

    result, meta = region.run_region(
        aoi_name="test-region", grid=grid, tile_km=2.0, bounds=(77.0, 28.0, 77.02, 28.02), run_tile=run_tile
    )

    assert meta["processed_tiles"] == len(grid.tiles)
    assert meta["successful_tiles"] == len(grid.tiles)
    assert meta["failed_tiles"] == 0
    assert len(meta["tiles"]) == len(grid.tiles)

    # change_ids and alert_ids must be namespaced per tile to stay unique across the merge
    change_ids = [f["properties"]["change_id"] for f in result.geojson["features"]]
    assert len(change_ids) == len(set(change_ids))
    alert_ids = [a["alert_id"] for a in result.alerts]
    assert len(alert_ids) == len(set(alert_ids))

    assert result.stats["total_blobs"] == len(result.blobs)
    assert result.audit_trail[0]["step_name"] == "tile_region"
    assert result.audit_trail[0]["details"]["processed_tiles"] == len(grid.tiles)


def test_run_region_records_tile_failures_without_aborting():
    grid = region.build_tile_grid(77.0, 28.0, 77.02, 28.02, tile_km=2.0, max_tiles=9)
    assert len(grid.tiles) >= 2

    def flaky_run_tile(tile: region.TileSpec):
        if tile.index == 0:
            raise ValueError("simulated tile failure")
        scene = generate_scene(shape=(120, 120), seed=1, origin_lon=tile.min_lon, origin_lat=tile.max_lat)
        return run_pipeline(
            aoi_name=f"tile-{tile.index}",
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

    result, meta = region.run_region(
        aoi_name="test-region",
        grid=grid,
        tile_km=2.0,
        bounds=(77.0, 28.0, 77.02, 28.02),
        run_tile=flaky_run_tile,
    )

    assert meta["failed_tiles"] == 1
    assert meta["successful_tiles"] == len(grid.tiles) - 1
    failed = [t for t in meta["tiles"] if t["status"] == "failed"]
    assert len(failed) == 1
    assert "simulated tile failure" in failed[0]["error"]
    assert any("tile 0" in w for w in result.audit_trail[0]["warnings"])
