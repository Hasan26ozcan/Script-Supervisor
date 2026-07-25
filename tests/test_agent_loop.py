"""Tests run entirely in mock mode -- no API key or network needed.

These aren't meant to prove the harness produces *good* creative output
(that requires real model calls + real human judgment, phase 1/2 work).
They prove the loop mechanics -- stop conditions, cost tracking, trace
completeness -- behave correctly, since those are what break silently
in production.
"""
from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.rubric import Rubric


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
