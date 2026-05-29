"""ARQ worker — multi-stage report pipeline with exponential backoff."""

from __future__ import annotations

import asyncio
import logging

from arq.connections import RedisSettings

from app.application.report_jobs import STAGES, run_stage
from app.application.report_notifications import finalize_report
from app.config import settings
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
_BACKOFF_BASE = 2  # 2^0=1s, 2^1=2s, 2^2=4s


async def report_stage(ctx, report_id: str, stage_name: str) -> dict:
    db = SessionLocal()
    try:
        return run_stage(db, report_id, stage_name)
    finally:
        db.close()


async def report_pipeline(ctx, report_id: str) -> None:
    """Run all 4 stages with exponential backoff retries.
    A failed stage is recorded but does NOT block subsequent independent stages.
    """
    db = SessionLocal()
    failed_stages: list[str] = []
    try:
        for name, _ in STAGES:
            succeeded = False
            for attempt in range(MAX_ATTEMPTS):
                result = run_stage(db, report_id, name)
                status = result.get("status")
                if status == "success":
                    succeeded = True
                    break
                if status == "failed":
                    # terminal failure for this stage
                    logger.error(
                        "stage %s permanently failed for report %s after %d attempts: %s",
                        name,
                        report_id,
                        attempt + 1,
                        result.get("error"),
                    )
                    break
                # "retry" → exponential backoff before next attempt
                delay = _BACKOFF_BASE ** attempt
                logger.warning(
                    "stage %s attempt %d failed for report %s, retrying in %ds",
                    name,
                    attempt + 1,
                    report_id,
                    delay,
                )
                await asyncio.sleep(delay)

            if not succeeded:
                failed_stages.append(name)
                # continue to next stage (don't abort entire pipeline)

        finalize_report(db, report_id)
        if failed_stages:
            logger.warning("report %s completed with failed stages: %s", report_id, failed_stages)

    except Exception:  # noqa: BLE001
        logger.exception("unexpected error in pipeline for report %s", report_id)
        finalize_report(db, report_id)
    finally:
        db.close()


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


class WorkerSettings:
    functions = [report_stage, report_pipeline]
    redis_settings = _redis_settings()
    max_tries = 3
    job_timeout = 300
