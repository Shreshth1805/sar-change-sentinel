from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.job_store import job_store

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(severity: str | None = Query(default=None)):
    alerts = job_store.list_alerts()
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    return alerts
