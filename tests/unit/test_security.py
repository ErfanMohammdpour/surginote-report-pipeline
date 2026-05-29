"""Unit tests for app.domain.security."""

from __future__ import annotations

import pytest

from app.domain.security import (
    sanitize_filename,
    sign_payload,
    validate_webhook_url,
    verify_hmac_signature,
)
from app.domain.errors import UploadError


@pytest.mark.unit
class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("report.xlsx") == "report.xlsx"

    def test_strips_path_traversal(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_strips_null_bytes(self):
        result = sanitize_filename("file\x00name.xlsx")
        assert "\x00" not in result

    def test_strips_leading_dots(self):
        result = sanitize_filename(".hidden.txt")
        assert not result.startswith(".")

    def test_replaces_spaces(self):
        result = sanitize_filename("my file name.xlsx")
        assert " " not in result

    def test_caps_at_255(self):
        long_name = "a" * 300 + ".xlsx"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_empty_raises(self):
        with pytest.raises(UploadError):
            sanitize_filename("")

    def test_only_dots_sanitized(self):
        # "..." is collapsed to "_" which is safe
        result = sanitize_filename("...")
        assert result == "_"
        assert ".." not in result


@pytest.mark.unit
class TestValidateWebhookUrl:
    def test_valid_https(self):
        assert validate_webhook_url("https://example.com/hook") == "https://example.com/hook"

    def test_valid_http(self):
        assert validate_webhook_url("http://dev.local/hook") == "http://dev.local/hook"

    def test_ftp_raises(self):
        with pytest.raises(ValueError, match="http or https"):
            validate_webhook_url("ftp://example.com/hook")

    def test_empty_raises(self):
        with pytest.raises((ValueError, Exception)):
            validate_webhook_url("")

    def test_too_long_raises(self):
        long_url = "https://example.com/" + "a" * 2200
        with pytest.raises((ValueError, Exception)):
            validate_webhook_url(long_url)


@pytest.mark.unit
class TestHMAC:
    _SECRET = "super-secret-key"
    _BODY = b'{"event":"report.completed"}'

    def test_sign_and_verify_success(self):
        sig = f"sha256={sign_payload(self._BODY, self._SECRET)}"
        assert verify_hmac_signature(self._BODY, self._SECRET, sig)

    def test_wrong_secret_fails(self):
        sig = f"sha256={sign_payload(self._BODY, 'wrong-secret')}"
        assert not verify_hmac_signature(self._BODY, self._SECRET, sig)

    def test_tampered_body_fails(self):
        sig = f"sha256={sign_payload(self._BODY, self._SECRET)}"
        assert not verify_hmac_signature(b"tampered", self._SECRET, sig)

    def test_missing_prefix_fails(self):
        raw = sign_payload(self._BODY, self._SECRET)
        assert not verify_hmac_signature(self._BODY, self._SECRET, raw)
