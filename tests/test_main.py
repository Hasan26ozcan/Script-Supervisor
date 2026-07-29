"""Tests for the FastAPI endpoints, using TestClient against a fresh app
instance per test. Each test chdir's into an isolated tmp_path so
tests don't share (and corrupt) each other's on-disk state.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")

    # Ensure routing config exists for Phase 7 support in tests.
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "routing_rules.yaml").write_text(
        "- task: draft\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.5\n  escalate_to: llama-3.1-70b-versatile\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )

    # Ensure data/traces exists so the endpoint can write traces.
    (tmp_path / "data" / "traces").mkdir(parents=True, exist_ok=True)

    from app.main import app

    return TestClient(app)


def test_run_endpoint_returns_full_trace(client):
    resp = client.post("/run", json={"brief": "A tense elevator ride.", "max_turns": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["input_brief"] == "A tense elevator ride."
    assert len(body["steps"]) >= 1
    assert body["stop_reason"] in {"max_turns", "plateau", "threshold_met"}
    assert body["final_output"]


def test_run_endpoint_persists_trace_retrievable_by_id(client):
    run_resp = client.post("/run", json={"brief": "A quiet library scene.", "max_turns": 1})
    run_id = run_resp.json()["run_id"]

    fetch_resp = client.get(f"/traces/{run_id}")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["run_id"] == run_id


def test_get_trace_404_for_unknown_id(client):
    resp = client.get("/traces/does-not-exist")
    assert resp.status_code == 404


def test_compare_endpoint_records_preference_and_updates_weights(client):
    resp = client.post(
        "/compare",
        json={
            "brief": "A rainy rooftop chase.",
            "candidate_a": "Shot 1: wide, rain visible, telephoto compression.",
            "candidate_b": "Shot 1: characters run around.",
            "winner": "a",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "recorded"
    assert "updated_weights" in body


def test_rubric_endpoint_reflects_criteria(client):
    resp = client.get("/rubric")
    assert resp.status_code == 200
    body = resp.json()
    assert "clarity" in body["criteria"]
    assert "visual_continuity" in body["criteria"]


def test_rubric_history_endpoint_returns_history(client):
    resp = client.get("/rubric/history")
    assert resp.status_code == 200
    body = resp.json()
    assert "weight_history" in body
    assert isinstance(body["weight_history"], list)


def test_comparison_pairs_endpoint_returns_list(client, tmp_path):
    pairs_dir = tmp_path / "data" / "comparisons"
    pairs_dir.mkdir(parents=True, exist_ok=True)
    (pairs_dir / "phase5_pairs.jsonl").write_text(
        (
            '{"pair_id": "test-1", "source": "phase5", "brief": "A scene.", '
            '"candidate_a": "A1", "candidate_b": "B1"}\n'
        ),
        encoding="utf-8",
    )
    resp = client.get("/comparison-pairs")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["pair_id"] == "test-1"


def test_compare_ui_endpoint_returns_html(client):
    ui_path = Path("app/templates/compare.html")
    ui_path.parent.mkdir(parents=True, exist_ok=True)
    ui_path.write_text("<html></html>", encoding="utf-8")
    resp = client.get("/compare-ui")
    assert resp.status_code == 200
    assert "html" in resp.text.lower()


def test_run_endpoint_with_reference_images(client, tmp_path):
    import base64

    img_path = tmp_path / "ref.png"
    img_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
    )
    resp = client.post(
        "/run",
        json={
            "brief": "A dim warehouse standoff.",
            "max_turns": 1,
            "reference_images": [{"path": str(img_path), "caption": "warehouse dusk light"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["steps"][0]["critique"]["modality"] == "vision"
