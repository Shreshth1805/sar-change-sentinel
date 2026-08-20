from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from shapely.geometry import shape as shapely_shape

from app.api.schemas import GeeJobRequest, GeeRegionJobRequest, SyntheticJobRequest, SyntheticRegionJobRequest
from app.api.serialization import result_to_api
from app.core import gee_client, region
from app.core.pipeline import PipelineConfig, run_pipeline
from app.services.job_store import job_store
from app.synthetic.generator import generate_scene

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Synthetic tiles are cheap (~1s each locally); GEE tiles each make several
# real network calls to Earth Engine (~10-20s), so a much smaller cap keeps
# a region job's total runtime bounded to something a synchronous HTTP
# request can reasonably wait out.
MAX_SYNTHETIC_REGION_TILES = 25
MAX_GEE_REGION_TILES = 9


@router.post("/synthetic")
def create_synthetic_job(body: SyntheticJobRequest):
    """Run the full pipeline on a generated demo scene — no GEE account needed.
    Runs synchronously; synthetic scenes at demo resolution complete in well
    under a second."""
    job = job_store.create(body.aoi_name, "synthetic", body.model_dump())
    job_store.mark_running(job.job_id)
    try:
        scene = generate_scene(
            shape=(body.height, body.width),
            seed=body.seed,
            origin_lon=body.origin_lon,
            origin_lat=body.origin_lat,
            num_structures=body.num_structures,
        )
        config = PipelineConfig(
            pixel_area_sqm=100.0,  # 10m x 10m Sentinel-1-like pixels
            include_classifications=tuple(body.include_classifications),
        )
        result = run_pipeline(
            aoi_name=job.aoi_name,
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
    except Exception as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_store.mark_completed(job.job_id, result)
    return {
        "job_id": job.job_id,
        "status": "completed",
        "aoi_center": [body.origin_lon, body.origin_lat],
        **result_to_api(result),
    }


@router.post("/gee")
def create_gee_job(body: GeeJobRequest):
    """Run the pipeline on real Sentinel-1 imagery for an AOI via Google Earth
    Engine. Requires `earthengine authenticate` to have been run once on this
    machine — see GET /api/gee/status to check first."""
    job = job_store.create(body.aoi_name, "gee", body.model_dump(mode="json"))
    job_store.mark_running(job.job_id)
    try:
        bands, transform, crs = gee_client.fetch_pipeline_inputs(
            body.aoi_geojson,
            body.pre_start,
            body.pre_end,
            body.post_start,
            body.post_end,
            scale=body.scale_m,
            project=body.gee_project,
        )

        config = PipelineConfig(
            pixel_area_sqm=body.scale_m * body.scale_m,
            include_classifications=tuple(body.include_classifications),
        )
        result = run_pipeline(
            aoi_name=job.aoi_name,
            pre_vv=bands["pre_VV"],
            post_vv=bands["post_VV"],
            pre_vh=bands["pre_VH"],
            post_vh=bands["post_VH"],
            water_mask=bands["water"].astype(bool),
            vegetation_mask=bands["vegetation"].astype(bool),
            slope_mask=bands["slope"].astype(bool),
            transform=transform,
            crs=crs,
            config=config,
        )
    except gee_client.GeeNotAuthenticatedError as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except gee_client.NoScenesFoundError as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_store.mark_completed(job.job_id, result)
    aoi_centroid = shapely_shape(body.aoi_geojson).centroid
    return {
        "job_id": job.job_id,
        "status": "completed",
        "aoi_center": [aoi_centroid.x, aoi_centroid.y],
        **result_to_api(result),
    }


@router.post("/synthetic/region")
def create_synthetic_region_job(body: SyntheticRegionJobRequest):
    """Cover an area larger than one safe tile by splitting it into a grid
    of synthetic scenes and merging the results. No GEE account needed."""
    job = job_store.create(body.aoi_name, "synthetic", body.model_dump())
    job_store.mark_running(job.job_id)
    try:
        min_lon, min_lat, max_lon, max_lat = shapely_shape(body.aoi_geojson).bounds
        grid = region.build_tile_grid(min_lon, min_lat, max_lon, max_lat, body.tile_km, MAX_SYNTHETIC_REGION_TILES)
        tile_px = max(64, round(body.tile_km * 1000 / 10))
        num_structures = min(12, max(2, round(body.tile_km)))

        def run_tile(tile: region.TileSpec):
            scene = generate_scene(
                shape=(tile_px, tile_px),
                seed=(body.base_seed or 0) + tile.index,
                origin_lon=tile.min_lon,
                origin_lat=tile.max_lat,
                num_structures=num_structures,
            )
            config = PipelineConfig(
                pixel_area_sqm=100.0,
                include_classifications=tuple(body.include_classifications),
            )
            return run_pipeline(
                aoi_name=f"{body.aoi_name} [tile {tile.index}]",
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

        result, region_meta = region.run_region(
            aoi_name=body.aoi_name,
            grid=grid,
            tile_km=body.tile_km,
            bounds=(min_lon, min_lat, max_lon, max_lat),
            run_tile=run_tile,
        )
    except Exception as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_store.mark_completed(job.job_id, result, region_meta)
    return {
        "job_id": job.job_id,
        "status": "completed",
        "region": region_meta,
        **result_to_api(result),
    }


@router.post("/gee/region")
def create_gee_region_job(body: GeeRegionJobRequest):
    """Cover an area larger than one safe tile by splitting it into a grid
    of real Sentinel-1 AOIs and merging the results. Requires Earth Engine
    auth — checked once upfront so a bad/missing project fails fast instead
    of failing identically on every tile in the grid."""
    job = job_store.create(body.aoi_name, "gee", body.model_dump(mode="json"))
    job_store.mark_running(job.job_id)
    try:
        gee_client.ensure_initialized(project=body.gee_project)
    except gee_client.GeeNotAuthenticatedError as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=428, detail=str(exc)) from exc

    try:
        min_lon, min_lat, max_lon, max_lat = shapely_shape(body.aoi_geojson).bounds
        grid = region.build_tile_grid(min_lon, min_lat, max_lon, max_lat, body.tile_km, MAX_GEE_REGION_TILES)

        def run_tile(tile: region.TileSpec):
            bands, transform, crs = gee_client.fetch_pipeline_inputs(
                tile.geojson,
                body.pre_start,
                body.pre_end,
                body.post_start,
                body.post_end,
                scale=body.scale_m,
                project=body.gee_project,
            )
            config = PipelineConfig(
                pixel_area_sqm=body.scale_m * body.scale_m,
                include_classifications=tuple(body.include_classifications),
            )
            return run_pipeline(
                aoi_name=f"{body.aoi_name} [tile {tile.index}]",
                pre_vv=bands["pre_VV"],
                post_vv=bands["post_VV"],
                pre_vh=bands["pre_VH"],
                post_vh=bands["post_VH"],
                water_mask=bands["water"].astype(bool),
                vegetation_mask=bands["vegetation"].astype(bool),
                slope_mask=bands["slope"].astype(bool),
                transform=transform,
                crs=crs,
                config=config,
            )

        result, region_meta = region.run_region(
            aoi_name=body.aoi_name,
            grid=grid,
            tile_km=body.tile_km,
            bounds=(min_lon, min_lat, max_lon, max_lat),
            run_tile=run_tile,
        )
    except Exception as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_store.mark_completed(job.job_id, result, region_meta)
    return {
        "job_id": job.job_id,
        "status": "completed",
        "region": region_meta,
        **result_to_api(result),
    }


@router.get("")
def list_jobs():
    return [
        {
            "job_id": j.job_id,
            "aoi_name": j.aoi_name,
            "data_source": j.data_source,
            "status": j.status,
            "created_at": j.created_at.isoformat(),
            "stats": j.result.stats if j.result else None,
            "error": j.error,
        }
        for j in job_store.list_jobs()
    ]


@router.get("/{job_id}")
def get_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    payload = {
        "job_id": job.job_id,
        "aoi_name": job.aoi_name,
        "data_source": job.data_source,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "error": job.error,
    }
    if job.result is not None:
        payload.update(result_to_api(job.result))
    if job.region_meta is not None:
        payload["region"] = job.region_meta
    return payload


@router.get("/{job_id}/geojson")
def download_geojson(job_id: str):
    job = job_store.get(job_id)
    if job is None or job.result is None:
        raise HTTPException(status_code=404, detail="job not found or not completed")
    filename = f"{job.aoi_name.replace(' ', '_')}_changes.geojson"
    return JSONResponse(
        content=job.result.geojson,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
