"""Enqueue ARQ jobs from API layer."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


async def enqueue_report_pipeline(app_state: Any, report_id: str) -> str | None:
    pool = getattr(app_state, "arq_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "job_queue_unavailable", "message": "Redis/ARQ pool not connected"},
        )
    job = await pool.enqueue_job("report_pipeline", report_id, _job_id=f"report:{report_id}")
    return job.job_id if job else None
