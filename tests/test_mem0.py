"""Tests for Mem0 endpoints in the FastAPI app."""
import asyncio
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


def test_mem0_validate_entry_active_non_stale(monkeypatch, tmp_path):
    """When margin is above stale threshold and predicted==expected, entry stays active."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    import app.main as main_module

    main_module.mem0_manager.store.entries.clear()

    # Ensure the data directory exists for the store to save.
    Path("data").mkdir(parents=True, exist_ok=True)

    from app.schemas import ComparisonPair

    pair = ComparisonPair(
        pair_id="test-1",
        source="test",
        brief="A test brief.",
        candidate_a="Shot A description with cut reveal establish.",
        candidate_b="Shot B description.",
    )
    main_module.mem0_manager.ingest_comparison_pair(pair, expected_winner="a")

    # Patch the gateway to return a critique that strongly matches the expected winner.
    async def fake_call(*args, **kwargs):
        from app.gateway import CallResult

        # Strongly favour candidate_a so the prediction matches expected_winner.
        text_a = (
            "clarity: 9/10 - very clear\n"
            "actionability: 8/10 - highly actionable\n"
        )
        text_b = "clarity: 2/10 - unclear\nactionability: 1/10 - not actionable\n"
        return CallResult(text=text_a, model="test", prompt_tokens=10, completion_tokens=10, latency_ms=1.0, cost_usd=0.0)

    monkeypatch.setattr(main_module.mem0_manager.gateway, "call", fake_call)

    # Set stale margin very high so margin > threshold
    old_margin = main_module.settings.mem0_stale_margin
    main_module.settings.mem0_stale_margin = 0.0

    try:
        records = asyncio.run(main_module.mem0_manager.validate_all())
        assert len(records) == 1
        record = records[0]
        assert not record.stale
    finally:
        main_module.settings.mem0_stale_margin = old_margin


def test_mem0_refresh_stale_creates_fresh_entries(monkeypatch, tmp_path):
    """refresh_stale() should create new active MemoryEntry objects replacing stale ones."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    import app.main as main_module

    main_module.mem0_manager.store.entries.clear()

    # Ensure the data directory exists for the store to save.
    Path("data").mkdir(parents=True, exist_ok=True)

    from app.schemas import ComparisonPair

    pair = ComparisonPair(
        pair_id="stale-1",
        source="test",
        brief="A stale brief.",
        candidate_a="Shot A.",
        candidate_b="Shot B.",
    )
    main_module.mem0_manager.ingest_comparison_pair(pair, expected_winner="a")

    # Mark the entry as stale directly.
    entry = list(main_module.mem0_manager.store.entries.values())[0]
    entry.status = "stale"
    main_module.mem0_manager.store.save()

    refreshed = main_module.mem0_manager.refresh_stale()
    assert len(refreshed) > 0
    for ref in refreshed:
        assert ref.status == "active"
