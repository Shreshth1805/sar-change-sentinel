from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.schemas import GeeJobRequest, SyntheticJobRequest
from app.api.serialization import result_to_api
from app.core import gee_client
from app.core.pipeline import PipelineConfig, run_pipeline
from app.services.job_store import job_store
from app.synthetic.generator import generate_scene

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/synthetic")
def create_synthetic_job(body: SyntheticJobRequest):
    """Run the full pipeline on a generated demo scene — no GEE account needed.
    Runs synchronously; synthetic scenes at demo resolution complete in well
    under a second."""
    job = job_store.create(body.aoi_name, "synthetic", body.model_dump())
    job_store.mark_running(job.job_id)
    try:
        scene = generate_scene(shape=(body.height, body.width), seed=body.seed)
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
    return {"job_id": job.job_id, "status": "completed", **result_to_api(result)}


@router.post("/gee")
def create_gee_job(body: GeeJobRequest):
    """Run the pipeline on real Sentinel-1 imagery for an AOI via Google Earth
    Engine. Requires `earthengine authenticate` to have been run once on this
    machine — see GET /api/gee/status to check first."""
    job = job_store.create(body.aoi_name, "gee", body.model_dump(mode="json"))
    job_store.mark_running(job.job_id)
    try:
        pre_composite = gee_client.get_sentinel1_composite(
            body.aoi_geojson, body.pre_start, body.pre_end
        )
        post_composite = gee_client.get_sentinel1_composite(
            body.aoi_geojson, body.post_start, body.post_end
        )
        pre_arr, transform, crs = gee_client.image_to_numpy(pre_composite, body.aoi_geojson, scale=body.scale_m)
        post_arr, _, _ = gee_client.image_to_numpy(post_composite, body.aoi_geojson, scale=body.scale_m)

        pre_vv, pre_vh = pre_arr[..., 0], pre_arr[..., 1]
        post_vv, post_vh = post_arr[..., 0], post_arr[..., 1]

        masks = gee_client.get_ancillary_masks(body.aoi_geojson, body.post_end)
        water_arr, _, _ = gee_client.image_to_numpy(masks["water"], body.aoi_geojson, scale=body.scale_m)
        veg_arr, _, _ = gee_client.image_to_numpy(masks["vegetation"], body.aoi_geojson, scale=body.scale_m)
        slope_arr, _, _ = gee_client.image_to_numpy(masks["slope"], body.aoi_geojson, scale=body.scale_m)

        config = PipelineConfig(
            pixel_area_sqm=body.scale_m * body.scale_m,
            include_classifications=tuple(body.include_classifications),
        )
        result = run_pipeline(
            aoi_name=job.aoi_name,
            pre_vv=pre_vv,
            post_vv=post_vv,
            pre_vh=pre_vh,
            post_vh=post_vh,
            water_mask=np.asarray(water_arr, dtype=bool).reshape(pre_vv.shape),
            vegetation_mask=np.asarray(veg_arr, dtype=bool).reshape(pre_vv.shape),
            slope_mask=np.asarray(slope_arr, dtype=bool).reshape(pre_vv.shape),
            transform=transform,
            crs=crs,
            config=config,
        )
    except gee_client.GeeNotAuthenticatedError as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except Exception as exc:
        job_store.mark_failed(job.job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_store.mark_completed(job.job_id, result)
    return {"job_id": job.job_id, "status": "completed", **result_to_api(result)}


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
