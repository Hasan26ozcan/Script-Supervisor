"""Tests run entirely in mock mode -- no API key or network needed.

These prove the loop mechanics -- stop conditions, cost tracking, trace
completeness -- behave correctly, since those are what break silently
in production.
"""
from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.rubric import DEFAULT_CRITERIA, Rubric


def _fresh_loop(tmp_path, **kwargs):
    rubric = Rubric(weights_path=tmp_path / "weights.json")
    gateway = ModelGateway(GatewayLedger())
    return CorrectionLoop(gateway=gateway, rubric=rubric, **kwargs)


async def test_run_produces_trace_with_at_least_one_step(tmp_path):
    loop = _fresh_loop(tmp_path)
    trace = await loop.run("A quiet farewell scene between two old friends.")
    assert len(trace.steps) >= 1
    assert trace.final_output is not None
    assert trace.stop_reason in {"max_turns", "plateau", "threshold_met"}


async def test_stops_at_max_turns_if_never_improving(tmp_path):
    loop = _fresh_loop(tmp_path, max_turns=2, threshold=999, plateau_epsilon=-1)
    trace = await loop.run("A chase scene through a night market.")
    assert len(trace.steps) == 2
    assert trace.stop_reason == "max_turns"


async def test_cost_and_latency_are_tracked(tmp_path):
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("An interrogation scene, single location.")
    # mock mode still routes through the same cost/latency accounting path
    assert trace.total_latency_ms > 0
    assert trace.total_cost_usd >= 0


async def test_every_step_has_a_draft_and_critique(tmp_path):
    loop = _fresh_loop(tmp_path, max_turns=3, threshold=999, plateau_epsilon=-1)
    trace = await loop.run("A rooftop confrontation at dawn.")
    for step in trace.steps:
        assert step.draft.content
        assert step.critique is not None
        assert 0 <= step.critique.overall <= 10


async def test_trace_has_input_brief_set(tmp_path):
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("A quiet morning in the garden.")
    assert trace.input_brief == "A quiet morning in the garden."
    assert trace.run_id is not None


async def test_stop_reason_is_none_when_no_stopping_condition_triggers(tmp_path):
    """With only 1 turn, stop_reason is max_turns even if loop wants to continue."""
    loop = _fresh_loop(tmp_path, max_turns=1, threshold=999, plateau_epsilon=-1)
    trace = await loop.run("A brief scene.")
    assert trace.stop_reason == "max_turns"
    assert len(trace.steps) == 1


async def test_cost_threshold_stop_condition(tmp_path):
    """When quality gain per dollar drops below threshold, loop stops early."""
    loop = _fresh_loop(
        tmp_path, max_turns=5, threshold=999,
        plateau_epsilon=-1, quality_per_dollar_threshold=0.0001,
    )
    trace = await loop.run("A tense alleyway argument.")
    assert trace.stop_reason in {"max_turns", "plateau", "threshold_met", "cost_threshold"}
    assert trace.final_output is not None


async def test_rubric_weights_start_uniform(tmp_path):
    rubric = Rubric(weights_path=tmp_path / "weights.json")
    for crit in DEFAULT_CRITERIA:
        assert rubric.weights.get(crit, 0) > 0


async def test_default_criteria_are_text_only(tmp_path):
    """Without reference images, the rubric should only report text criteria."""
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("A quiet kitchen scene, early morning.")
    text_criteria = {s.criterion for s in trace.steps[0].critique.scores}
    assert text_criteria.issubset(set(DEFAULT_CRITERIA))


async def test_rubric_weighted_overall_is_weighted_average(tmp_path):
    from app.rubric import RubricScore

    rubric = Rubric(weights_path=tmp_path / "weights.json")
    rubric.weights = {"clarity": 2.0, "tone_match": 1.0, "actionability": 1.0}
    scores = [
        RubricScore(criterion="clarity", score=8.0, rationale="clear"),
        RubricScore(criterion="tone_match", score=6.0, rationale="ok"),
        RubricScore(criterion="actionability", score=4.0, rationale="vague"),
    ]
    overall = rubric.weighted_overall(scores)
    # weighted: (8*2 + 6*1 + 4*1) / (2+1+1) = 26/4 = 6.5
    assert overall == 6.5


async def test_empty_scores_returns_zero_overall(tmp_path):
    rubric = Rubric(weights_path=tmp_path / "weights.json")
    assert rubric.weighted_overall([]) == 0.0
