"""Tests for Phase 4 vision effectiveness experiment integration."""


async def test_phase4_script_runs_in_mock_mode(monkeypatch):
    import sys

    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")
    for mod in (
        "app.main",
        "app.agent_loop",
        "app.config",
        "app.prompts",
        "app.gateway",
        "app.rubric",
        "app.schemas",
    ):
        sys.modules.pop(mod, None)

    import experiments.phase4_vision_effectiveness as phase4

    # Use a mock trial so the experiment path resolves without needing real image assets.
    trial = type("T", (), {})()
    trial.id = "mock"
    trial.title = "Mock trial"
    trial.brief = "A quiet forest path at dawn."
    trial.reference_image = "data/images/grounding/forest_clearing/relevant.jpg"

    results = await phase4.run_experiment([trial])
    assert (
        results["trials"][0]["text_only"]["turns"] == 1
        or results["trials"][0]["text_only"]["turns"] == 3
    )
    assert results["trials"][0]["vision"]["turns"] >= 1
    assert "delta_overall" in results["trials"][0]
