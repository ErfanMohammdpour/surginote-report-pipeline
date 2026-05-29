from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient


def pytest_configure(config):
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / "tests" / "_pytest.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    os.environ["SN_DATABASE_URL"] = "sqlite:///./tests/_pytest.sqlite"
    os.environ["SN_SKIP_OBJECT_STORAGE"] = "true"
    os.environ["SN_SYNC_JOBS"] = "true"
    # Build engine after env is set, then create tables (TestClient alone may not run lifespan).
    from app.infrastructure.database.session import create_all

    create_all()


@pytest.fixture(scope="session")
def app_instance():
    from app.main import app

    return app


@pytest.fixture(scope="session")
def client(app_instance):
    with TestClient(app_instance, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="session")
def minimal_export_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    p = repo_root / "tests" / "_minimal_export.xlsx"

    raw_payload = {
        "phases": [{"id": "phase_9", "name": "Alpha", "startTime": 0.0, "endTime": 120.0, "startFrame": 0, "endFrame": 200}],
        "markers": [{"id": "m9", "type": "negative", "timestamp": 30.0, "title": "bad", "content": "oops"}],
        "scores": {},
        "metrics": {},
    }

    vid = [["Property", "Value"], ["Video Name", "unit.xlsx"], ["Export Version", "9.9"], ["Duration (seconds)", 120]]

    phases = pd.DataFrame(
        [
            {
                "Phase Name": "Alpha",
                "Short Name": "A",
                "Start Time": "00:00",
                "End Time": "02:00",
                "Duration": "02:00",
                "Start Frame": 0,
                "End Frame": 200,
                "Description": "window holds marker",
                "Is Custom": "No",
                "Phaco Method": None,
            }
        ]
    )

    skills = pd.DataFrame(
        [{"Phase Name": "Alpha", "Skill/Metric Name": "Skill A", "Score": 5, "Max Score": 5, "Visual Rating": ""}]
    )

    comments = pd.DataFrame(
        [{"#": "#1", "Video Time": "00:30", "Type": "Negative", "Title/Label": "bad", "Full Text/Description": "oops"}]
    )

    raw_rows = [
        ["Version", "Annotation ID", "Created By", "Annotation Data (JSON)", "Created At"],
        ["CURRENT", "1", "tester", json.dumps(raw_payload), "2026-01-01 00:00"],
    ]

    with pd.ExcelWriter(p, engine="openpyxl") as xl:
        pd.DataFrame(vid).to_excel(xl, sheet_name="Video Info", index=False, header=False)
        phases.to_excel(xl, sheet_name="Phases", index=False)
        skills.to_excel(xl, sheet_name="Skills & Ratings", index=False)
        comments.to_excel(xl, sheet_name="Comments & Notes", index=False)
        pd.DataFrame(raw_rows).to_excel(xl, sheet_name="Raw Data (Technical)", index=False, header=False)

    return p
