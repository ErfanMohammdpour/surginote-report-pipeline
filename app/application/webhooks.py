"""Webhook dispatch with HMAC + retries."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver_webhook(*, url: str, secret: str, event: str, data: dict[str, Any]) -> bool:
    payload = {"event": event, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "data": data}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = _sign(raw, secret)
    headers = {"Content-Type": "application/json", "X-SurgiNote-Signature": f"sha256={sig}"}

    max_retries = settings.webhook_max_retries
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(url, content=raw, headers=headers)
            if r.status_code < 500:
                return r.status_code < 400
        except httpx.HTTPError as e:
            logger.warning("webhook attempt %s failed: %s", attempt + 1, e)
        time.sleep(2**attempt)
    return False
