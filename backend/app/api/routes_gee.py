from __future__ import annotations

from fastapi import APIRouter, Query

from app.core import gee_client

router = APIRouter(prefix="/api/gee", tags=["gee"])


@router.get("/status")
def gee_status(project: str | None = Query(default=None)):
    try:
        gee_client.ensure_initialized(project=project)
        return {"authenticated": True, "message": "Earth Engine is authenticated and ready."}
    except gee_client.GeeNotAuthenticatedError as exc:
        return {"authenticated": False, "message": str(exc)}
