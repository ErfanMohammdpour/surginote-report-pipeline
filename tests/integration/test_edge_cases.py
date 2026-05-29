from __future__ import annotations

import json
import uuid

import pytest


@pytest.mark.integration
def test_json_import(client, tmp_path):
    canonical = {
        "video_info": {"name": "json_case"},
        "phases": [{"name": "P1", "start_time": 0, "end_time": 60}],
        "skills": [{"name": "S1", "phase_name": "P1", "score": 3.0, "max_score": 5.0}],
        "comments": [],
    }
    p = tmp_path / "case.json"
    p.write_text(json.dumps(canonical), encoding="utf-8")
    r = client.post(
        "/v1/imports",
        files={"upload": ("case.json", p.read_bytes(), "application/json")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["format"] == "json"


@pytest.mark.integration
def test_async_report_rejects_incomplete_import(client):
    bad_json = b'{"video_info":{"name":"x"},"phases":[{"name":"P","start_time":100,"end_time":10}],"skills":[],"comments":[]}'
    r = client.post(
        "/v1/imports",
        files={"upload": ("bad.json", bad_json, "application/json")},
    )
    assert r.status_code == 422
    imp = r.json().get("import_id")  # may not be in error body
    # fetch latest failed import via audit if needed — use direct import_id from events
    from app.infrastructure.database.models import ImportORM
    from app.infrastructure.database.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(ImportORM).filter(ImportORM.status == "failed").order_by(ImportORM.created_at.desc()).first()
        assert row is not None
        imp = row.id
    finally:
        db.close()

    start = client.post(f"/v1/imports/{imp}/reports/async")
    assert start.status_code == 409
    assert start.json()["detail"]["code"] == "import_not_completed"


@pytest.mark.integration
def test_idempotency_replay_failed_validation(client, minimal_export_path):
    key = str(uuid.uuid4())
    bad_json = b'{"video_info":{"name":"x"},"phases":[{"name":"P","start_time":100,"end_time":10}],"skills":[],"comments":[]}'
    headers = {"X-Idempotency-Key": key}
    r1 = client.post(
        "/v1/imports",
        headers=headers,
        files={"upload": ("bad.json", bad_json, "application/json")},
    )
    assert r1.status_code == 422
    r2 = client.post(
        "/v1/imports",
        headers=headers,
        files={"upload": ("bad.json", bad_json, "application/json")},
    )
    assert r2.status_code == 422
    assert r2.headers.get("x-idempotent-replay") == "true"


@pytest.mark.integration
def test_audit_trail_total_count(client, minimal_export_path):
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={"upload": ("unit.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    imp = r.json()["import_id"]
    trail = client.get(f"/v1/imports/{imp}/audit-trail")
    data = trail.json()
    assert data["total_events"] >= len(data["events"])


@pytest.mark.unit
def test_override_thresholds_severity_filter():
    from app.application.rules.engine import evaluate_rules, load_rules_config

    canonical = {
        "video_info": {"name": "t"},
        "phases": [{"name": "Alpha", "start_time": 0.0, "end_time": 120.0}],
        "skills": [{"name": "Skill A", "phase_name": "Alpha", "score": 1.0, "max_score": 5.0}],
        "comments": [],
    }
    cfg = load_rules_config()
    cfg["override_thresholds"] = {"contradiction_severity_min": "warning"}
    hits = evaluate_rules(canonical, config=cfg)
    assert not any(h.severity == "info" for h in hits)


@pytest.mark.integration
def test_readyz(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
