from __future__ import annotations


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

    d = client.get(f"/v1/cases/{case_id}")
    assert d.status_code == 200
    payload = d.json()
    assert payload["skills"][0]["skill_name"] == "Skill A"

    g = client.post(f"/v1/cases/{case_id}/reports/generate")
    assert g.status_code == 200
    envelope = g.json()
    flags = envelope["report"]["sections"]["contradictions"]["flags"]
    assert any(f["linkage"] == "phase_window" for f in flags)

    lr = client.get(f"/v1/cases/{case_id}/reports/latest")
    assert lr.status_code == 200
