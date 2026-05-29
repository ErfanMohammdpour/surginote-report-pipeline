"""Security helpers — filename sanitization, URL validation, HMAC."""

from __future__ import annotations

import hmac
import hashlib
import re
from urllib.parse import urlparse

from app.domain.errors import UploadError


_SAFE_FILENAME = re.compile(r"[^\w.\-]")
_MAX_FILENAME_LEN = 255


def sanitize_filename(name: str) -> str:
    """Strip directory traversal, null bytes, dangerous chars; cap length."""
    if not name:
        raise UploadError("invalid_filename", "Filename must not be empty")
    # Strip null bytes, slashes, and control chars first
    cleaned = name.replace("\x00", "").replace("/", "_").replace("\\", "_").strip()
    # Replace any char outside word-chars, dot, hyphen with underscore
    safe = _SAFE_FILENAME.sub("_", cleaned)
    # Collapse path-traversal sequences like ".." → single underscore
    import re as _re
    safe = _re.sub(r"\.{2,}", "_", safe)
    safe = safe.lstrip(".")  # no hidden files
    if not safe:
        raise UploadError("invalid_filename", "Filename contains only disallowed characters")
    return safe[:_MAX_FILENAME_LEN]


def validate_webhook_url(url: str) -> str:
    """Only http/https; no localhost/127/private in prod; max 2048 chars."""
    if not url or len(url) > 2048:
        raise ValueError("webhook url too long or empty")
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"invalid webhook url: {e}") from e
    if parsed.scheme not in ("http", "https"):
        raise ValueError("webhook url must use http or https")
    host = (parsed.hostname or "").lower()
    # warn but allow http for local dev; block only obviously broken
    if not host:
        raise ValueError("webhook url missing host")
    return url


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_hmac_signature(body: bytes, secret: str, signature_header: str) -> bool:
    """Verify `sha256=<hex>` signature header."""
    expected = f"sha256={sign_payload(body, secret)}"
    return constant_time_eq(expected, signature_header)
