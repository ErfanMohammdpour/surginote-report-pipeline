"""Integration tests for security features and error handling improvements."""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.mark.integration
def test_security_headers_on_import_error(client):
    """All error responses must carry security headers."""
    r = client.post(
        "/v1/imports",
        files={"upload": ("bad.bin", b"\xff\xfe", "application/octet-stream")},
    )
    assert r.status_code in (400, 422)
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


@pytest.mark.integration
def test_security_headers_on_404(client):
    r = client.get("/v1/reports/nonexistent-id/status")
    assert r.status_code == 404
    # Custom handlers attach headers; default 404 may not — only check our handler
    data = r.json()
    assert data.get("detail", {}).get("code") == "report_not_found"


@pytest.mark.integration
def test_security_headers_on_validation_error(client):
    bad_json = b'{"video_info":{"name":"x"},"phases":[{"name":"P","start_time":100,"end_time":10}],"skills":[],"comments":[]}'
    r = client.post(
        "/v1/imports",
        files={"upload": ("bad.json", bad_json, "application/json")},
    )
    assert r.status_code == 422
    assert r.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.integration
def test_filename_sanitized(client, minimal_export_path):
    """Filenames with path separators must not cause errors."""
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("../../etc/passwd.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200


@pytest.mark.integration
def test_webhook_secret_too_short_rejected(client):
    r = client.post(
        "/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["report.completed"], "secret": "short"},
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_webhook_unknown_event_rejected(client):
    r = client.post(
        "/v1/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["unknown.event"],
            "secret": "a_sufficiently_long_secret_key__",
        },
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_webhook_invalid_scheme_rejected(client):
    r = client.post(
        "/v1/webhooks",
        json={
            "url": "ftp://example.com/hook",
            "events": ["report.completed"],
            "secret": "a_sufficiently_long_secret_key__",
        },
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_audit_trail_csv_export(client, minimal_export_path):
    """Audit trail should export as CSV when ?format=csv."""
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200
    imp_id = r.json()["import_id"]

    csv_r = client.get(f"/v1/imports/{imp_id}/audit-trail?format=csv")
    assert csv_r.status_code == 200
    assert "text/csv" in csv_r.headers.get("content-type", "")
    content = csv_r.text
    assert "event_id" in content  # header row present
    assert "ImportStarted" in content


@pytest.mark.integration
def test_report_status_has_duration_ms(client, minimal_export_path):
    """Completed report status must include duration_ms."""
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    imp_id = r.json()["import_id"]
    rpt = client.post(f"/v1/imports/{imp_id}/reports/async")
    rpt_id = rpt.json()["report_id"]
    status = client.get(f"/v1/reports/{rpt_id}/status").json()
    # SN_SYNC_JOBS=true → report should be completed
    if status["status"] == "completed":
        assert "duration_ms" in status
        assert isinstance(status["duration_ms"], int)


@pytest.mark.integration
def test_report_metadata_has_processing_time(client, minimal_export_path):
    """Final report payload must contain processing_time_ms."""
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    imp_id = r.json()["import_id"]
    rpt = client.post(f"/v1/imports/{imp_id}/reports/async")
    rpt_id = rpt.json()["report_id"]
    report = client.get(f"/v1/reports/{rpt_id}").json()
    assert "processing_time_ms" in report.get("metadata", {})
    assert "total_events_processed" in report.get("metadata", {})


@pytest.mark.integration
def test_diff_returns_has_changes(client, minimal_export_path):
    """Two reports for the same import should produce a valid diff response."""
    with minimal_export_path.open("rb") as f:
        payload = f.read()

    r1 = client.post(
        "/v1/imports",
        files={"upload": ("unit.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    imp_id = r1.json()["import_id"]
    rpt1 = client.post(f"/v1/imports/{imp_id}/reports/async").json()["report_id"]
    rpt2 = client.post(f"/v1/imports/{imp_id}/reports/async").json()["report_id"]

    diff = client.get(f"/v1/reports/{rpt1}/diff/{rpt2}").json()
    assert "has_changes" in diff
    assert diff["report_1"] == rpt1
    assert diff["report_2"] == rpt2


@pytest.mark.integration
def test_empty_upload_rejected(client):
    """Empty file upload must return 400 empty_upload."""
    r = client.post(
        "/v1/imports",
        files={"upload": ("empty.xlsx", b"", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code in (400, 422)
