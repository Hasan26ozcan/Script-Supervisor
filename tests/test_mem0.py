from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from training.generate_fake_preferences import build_fake_preferences


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if Path("data").exists():
        for path in Path("data").rglob("*"):
            if path.is_file():
                path.unlink()
    yield


def test_mem0_api_endpoints_working(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    import app.main as main_module
    reload(main_module)
    client = TestClient(main_module.app)
    fake_pref = build_fake_preferences()[0]

    resp = client.post(
        "/compare",
        json={
            "brief": fake_pref.brief,
            "prompt": fake_pref.prompt,
            "candidate_a": fake_pref.candidate_a,
            "candidate_b": fake_pref.candidate_b,
            "winner": fake_pref.winner,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"

    mem0_resp = client.get("/mem0/entries")
    assert mem0_resp.status_code == 200
    entries = mem0_resp.json()
    assert len(entries) == 1
    assert entries[0]["source"] == "compare_api"

    validate_resp = client.post("/mem0/validate")
    assert validate_resp.status_code == 200
    summary = validate_resp.json()["summary"]
    assert "total" in summary
    assert summary["total"] == 1
