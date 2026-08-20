"""In-memory job store — single-process, no persistence, same pattern as
AutoClean AI's `services/session_store.py`: every change-detection run gets
a `job_id`, and the frontend polls/fetches by id. Fine for a demo/single
backend instance; a real deployment would back this with a database and a
task queue for GEE jobs, which is a straightforward swap since nothing
outside this module knows the store is in-memory.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from app.core.pipeline import PipelineResult

JobStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class ChangeDetectionJob:
    job_id: str
    aoi_name: str
    data_source: Literal["gee", "synthetic"]
    status: JobStatus
    created_at: datetime
    request: dict[str, Any]
    result: PipelineResult | None = None
    error: str | None = None
    completed_at: datetime | None = None
    region_meta: dict[str, Any] | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ChangeDetectionJob] = {}

    def create(self, aoi_name: str, data_source: Literal["gee", "synthetic"], request: dict[str, Any]) -> ChangeDetectionJob:
        job = ChangeDetectionJob(
            job_id=str(uuid.uuid4()),
            aoi_name=aoi_name,
            data_source=data_source,
            status="pending",
            created_at=datetime.now(timezone.utc),
            request=request,
        )
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> ChangeDetectionJob | None:
        return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        self._jobs[job_id].status = "running"

    def mark_completed(self, job_id: str, result: PipelineResult, region_meta: dict[str, Any] | None = None) -> None:
        job = self._jobs[job_id]
        job.status = "completed"
        job.result = result
        job.region_meta = region_meta
        job.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, job_id: str, error: str) -> None:
        job = self._jobs[job_id]
        job.status = "failed"
        job.error = error
        job.completed_at = datetime.now(timezone.utc)

    def list_jobs(self) -> list[ChangeDetectionJob]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def list_alerts(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for job in self._jobs.values():
            if job.result is not None:
                alerts.extend(job.result.alerts)
        return sorted(alerts, key=lambda a: a["detected_at"], reverse=True)


job_store = JobStore()
