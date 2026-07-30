"""Tests for Mem0 endpoints in the FastAPI app."""
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
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    import app.main as main_module

    # Reset the Mem0Manager store so this test starts clean,
    # regardless of what other tests (e.g. test_main.py) may have left.
    main_module.mem0_manager.store.entries.clear()

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


def test_mem0_stale_endpoint(monkeypatch, tmp_path):
    """GET /mem0/stale should return a list (possibly empty) of stale entries."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    import app.main as main_module

    main_module.mem0_manager.store.entries.clear()
    client = TestClient(main_module.app)
    resp = client.get("/mem0/stale")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_mem0_refresh_endpoint(monkeypatch, tmp_path):
    """POST /mem0/refresh should return refreshed entries list."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    import app.main as main_module

    main_module.mem0_manager.store.entries.clear()
    client = TestClient(main_module.app)
    resp = client.post("/mem0/refresh")
    assert resp.status_code == 200
    assert "refreshed" in resp.json()
