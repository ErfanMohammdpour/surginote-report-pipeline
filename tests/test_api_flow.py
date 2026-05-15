from __future__ import annotations


from app.config import settings as app_settings


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_import_then_report_contains_flags(client, minimal_export_path):
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports",
            files={
                "upload": (
                    "unit.xlsx",
                    f.read(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert r.status_code == 200, r.text
    case_id = r.json()["case_id"]
    assert r.json().get("default_report_locale") == "en"

    d = client.get(f"/v1/cases/{case_id}")
    assert d.status_code == 200
    payload = d.json()
    assert payload["skills"][0]["skill_name"] == "Skill A"

    g_en = client.post(f"/v1/cases/{case_id}/reports/generate?persist=true")
    assert g_en.status_code == 200
    envelope = g_en.json()
    assert envelope["report"]["meta"]["schema_version"] == "1.3.0"
    assert envelope["report"]["meta"]["report_locale"] == "en"

    flags = envelope["report"]["sections"]["contradictions"]["flags"]
    assert any(f["linkage"] == "phase_window" for f in flags)

    g_fa = client.post(f"/v1/cases/{case_id}/reports/generate?locale=fa&persist=true")
    assert g_fa.status_code == 200
    fa_rep = g_fa.json()["report"]
    assert fa_rep["meta"]["report_locale"] == "fa"
    assert "فاز" in fa_rep["sections"]["score_analysis"]["score_narrative"]
    assert any("ویدیو" in lim for lim in fa_rep["quality"]["limitations"])

    bad = client.post(f"/v1/cases/{case_id}/reports/generate?locale=de")
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "invalid_locale"

    lr = client.get(f"/v1/cases/{case_id}/reports/latest")
    assert lr.status_code == 200


def test_import_locale_invalid(client, minimal_export_path):
    with minimal_export_path.open("rb") as f:
        r = client.post(
            "/v1/imports?locale=invalid",
            files={
                "upload": (
                    "unit.xlsx",
                    f.read(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_locale"


def test_narratives_generate_from_report_accepts_raw_report_json(client, monkeypatch):
    """Body is the report object only (no wrapper); parsing must succeed before Gemini is called."""
    monkeypatch.setattr(app_settings, "gemini_api_key", None)

    report = {"meta": {"schema_version": "1.3.0"}, "sections": {}}
    r = client.post(
        "/v1/narratives/generate-from-report",
        params={"locale": "en", "include_provider_raw": "false"},
        json=report,
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "gemini_api_key_missing"
