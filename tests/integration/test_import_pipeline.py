from __future__ import annotations

import uuid


def test_idempotent_import_replay(client, minimal_export_path):
    key = str(uuid.uuid4())
    with minimal_export_path.open("rb") as f:
        body = f.read()
    headers = {"X-Idempotency-Key": key}
    r1 = client.post(
        "/v1/imports",
        headers=headers,
        files={"upload": ("unit.xlsx", body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r1.status_code == 200, r1.text
    cid1 = r1.json()["case_id"]
    imp1 = r1.json()["import_id"]

    r2 = client.post(
        "/v1/imports",
        headers=headers,
        files={"upload": ("unit.xlsx", body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r2.status_code == 200
    assert r2.headers.get("x-idempotent-replay") == "true"
    assert r2.json()["case_id"] == cid1
    assert r2.json()["import_id"] == imp1


def test_audit_trail_after_import(client, minimal_export_path):
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    imp = r.json()["import_id"]
    trail = client.get(f"/v1/imports/{imp}/audit-trail")
    assert trail.status_code == 200
    types = {e["event_type"] for e in trail.json()["events"]}
    assert "ImportStarted" in types
    assert "ValidationCompleted" in types


def test_async_report_pipeline(client, minimal_export_path):
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    imp = r.json()["import_id"]
    start = client.post(f"/v1/imports/{imp}/reports/async")
    assert start.status_code == 200
    rid = start.json()["report_id"]
    status = client.get(f"/v1/reports/{rid}/status")
    assert status.status_code == 200
    assert status.json()["progress_percent"] == 100
    report = client.get(f"/v1/reports/{rid}")
    assert report.status_code == 200
    assert report.json()["schema_version"] == "2.0"
