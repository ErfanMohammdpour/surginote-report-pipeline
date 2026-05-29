"""Post-report webhook + alert dispatch."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.application.webhooks import deliver_webhook
from app.config import settings
from app.infrastructure.database.models import AsyncReportORM, WebhookORM

logger = logging.getLogger(__name__)


def notify_report_event(session: Session, event: str, report: AsyncReportORM) -> None:
    payload = {
        "report_id": report.id,
        "import_id": report.import_id,
        "status": report.status,
        "download_url": f"/v1/reports/{report.id}",
    }
    hooks = session.query(WebhookORM).all()
    for h in hooks:
        if event not in (h.events or []):
            continue
        ok = deliver_webhook(url=h.url, secret=h.secret, event=event, data=payload)
        if not ok:
            logger.warning("webhook delivery failed url=%s event=%s report=%s", h.url, event, report.id)

    if event == "report.failed" and settings.alert_webhook_url:
        deliver_webhook(
            url=settings.alert_webhook_url,
            secret=settings.webhook_signing_key or "alert",
            event=event,
            data=payload,
        )


def finalize_report(session: Session, report_id: str) -> AsyncReportORM | None:
    report = session.get(AsyncReportORM, report_id)
    if report is None:
        return None
    session.refresh(report)
    if report.status == "completed":
        notify_report_event(session, "report.completed", report)
    elif report.status == "failed":
        notify_report_event(session, "report.failed", report)
    return report
