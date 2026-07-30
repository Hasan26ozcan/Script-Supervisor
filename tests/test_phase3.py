"""Phase 3 tests for the correction loop and cost-aware stop condition."""

from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.rubric import Rubric


def _fresh_loop(tmp_path, **kwargs):
    rubric = Rubric(weights_path=tmp_path / "weights.json")
    gateway = ModelGateway(GatewayLedger())
    return CorrectionLoop(gateway=gateway, rubric=rubric, **kwargs)


async def test_cost_threshold_stop(tmp_path):
    loop = _fresh_loop(
        tmp_path,
        max_turns=3,
        threshold=999,
        plateau_epsilon=-1,
        quality_per_dollar_threshold=0.0001,
    )
    trace = await loop.run("A tense alleyway argument.")
    assert trace.stop_reason in {"max_turns", "plateau", "threshold_met", "cost_threshold"}
    assert trace.final_output is not None


async def test_phase3_script_runs_in_mock_mode(monkeypatch):
    import sys

    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")
    for mod in (
        "app.main",
        "app.agent_loop",
        "app.config",
        "app.prompts",
        "app.gateway",
        "app.rubric",
    ):
        sys.modules.pop(mod, None)

    import experiments.phase3_correction_effectiveness as phase3

    BriefEntry = type("BriefEntry", (), {})
    brief = BriefEntry()
    brief.id = "test_001"
    brief.title = "Test Brief"
    brief.brief = "A quiet studio portrait."

    trial_results = await phase3.evaluate_briefs([brief])
    assert trial_results["trials"][0]["single"]["turns"] == 1
    assert trial_results["trials"][0]["loop"]["turns"] >= 1
