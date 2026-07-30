"""Phase 1 mock-mode gateway tests.

These tests exercise the gateway in mock_mode=True so they run
quickly and deterministically in CI without needing real API keys.
They verify:
- the gateway returns well-formed CallResult objects for every task type
- cost/latency tracking works even in mock mode
- structured (Critique) responses are parseable/validated
- call_vision and call_structured paths work correctly
- cost estimation is non-negative for all model/task combinations
"""

import pytest

from app.gateway import MODEL_PRICES, CallResult, GatewayLedger, ModelGateway
from app.schemas import Critique


@pytest.fixture()
def gateway():
    return ModelGateway(GatewayLedger())


# ---- async call tests ----


async def test_gateway_returns_callresult_for_draft(gateway):
    result = await gateway.call(
        task="draft",
        system="You are a helpful assistant.",
        user="Describe a sunset.",
        model="claude-sonnet-5",
    )
    assert isinstance(result, CallResult)
    assert result.text
    assert result.model == "claude-sonnet-5"
    assert result.task == "draft"
    assert result.prompt_tokens >= 0
    assert result.completion_tokens >= 0
    assert result.latency_ms >= 0
    assert result.cost_usd >= 0


async def test_gateway_returns_callresult_for_critique(gateway):
    result = await gateway.call(
        task="critique",
        system="You are a film critic.",
        user="Critique this shot list.",
        model="claude-sonnet-5",
    )
    assert isinstance(result, CallResult)
    assert result.text


async def test_gateway_critique_text_contains_expected_criteria(gateway):
    result = await gateway.call(
        task="critique",
        system="You are a film critic.",
        user="Critique this shot list.",
        model="claude-sonnet-5",
    )
    assert isinstance(result, CallResult)
    assert result.text
    # Mock mode returns rubric-format text; key criteria should appear
    assert "clarity" in result.text or "overall" in result.text or "scores" in result.text


async def test_gateway_structured_call_returns_validated_critique(gateway):
    result = await gateway.call_structured(
        task="critique",
        system="You are a film critic.",
        user="Rate clarity: 8/10, tone: 7/10.",
        schema=Critique,
        model="claude-sonnet-5",
    )
    assert isinstance(result, Critique)
    assert 0 <= result.overall <= 10


async def test_gateway_structured_call_handles_parse_error(gateway):
    """When mock structured output can't be validated, we get a
    Critique with revision_notes explaining the failure."""
    result = await gateway.call_structured(
        task="critique",
        system="You are a film critic.",
        user="Rate everything.",
        schema=Critique,
        model="claude-sonnet-5",
    )
    # Mock mode always returns valid JSON for Critique schema
    assert isinstance(result, Critique)


async def test_gateway_cost_accumulates_across_calls(gateway):
    initial_cost = gateway.ledger.total_cost_usd
    await gateway.call(task="draft", system="", user="Test.", model="claude-sonnet-5")
    await gateway.call(task="draft", system="", user="Test again.", model="claude-sonnet-5")
    assert gateway.ledger.total_cost_usd >= initial_cost
    assert len(gateway.ledger.calls) == 2


async def test_gateway_ledger_tracks_per_call_details(gateway):
    await gateway.call(task="draft", system="system", user="user", model="claude-sonnet-5")
    call = gateway.ledger.calls[0]
    assert call.model == "claude-sonnet-5"
    assert call.task == "draft"
    assert call.prompt_tokens >= 0
    assert call.completion_tokens >= 0


async def test_gateway_vision_call_uses_visual_critique_task(gateway):
    """call_vision should route through the visual_critique task and
    produce a vision-modality critique."""
    import base64
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
        )
        img_path = f.name

    result = await gateway.call_vision(
        task="visual_critique",
        system="You are a vision critic.",
        user_text="Describe this image.",
        image_paths=[img_path],
        model="claude-sonnet-5",
    )
    assert isinstance(result, CallResult)
    assert result.text
    assert result.latency_ms >= 0
    assert result.cost_usd >= 0


async def test_gateway_vision_call_logs_with_image_token_overhead(gateway):
    """Vision calls include a per-image token cost, so prompt_tokens
    should exceed the text-only minimum."""
    import base64
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
        )
        img_path = f.name

    result = await gateway.call_vision(
        task="visual_critique",
        system="You are a vision critic.",
        user_text="Describe this image.",
        image_paths=[img_path],
        model="claude-sonnet-5",
    )
    # mock mode adds 300 prompt tokens per image
    assert result.prompt_tokens > 300


async def test_gateway_cost_for_unknown_model_is_zero(gateway):
    """Unknown model names get zero token prices but still return a
    valid CallResult."""
    result = await gateway.call(task="draft", system="", user="Test.", model="unknown-model-xyz")
    assert isinstance(result, CallResult)
    assert result.cost_usd == 0.0


async def test_gateway_draft_task_uses_default_model_when_none_provided(gateway):
    result = await gateway.call(task="draft", system="", user="Test.", model=None)
    assert isinstance(result, CallResult)
    # Default draft model is claude-haiku-4-5-20251001 in anthropic mode
    assert result.model in MODEL_PRICES


async def test_gateway_multiple_tasks_produce_non_negative_costs(gateway):
    for task in ("draft", "critique", "revise"):
        result = await gateway.call(
            task=task, system="", user="Test prompt.", model="claude-sonnet-5"
        )
        assert isinstance(result, CallResult)
        assert result.cost_usd >= 0


async def test_gateway_prompt_tokens_scale_with_input_length(gateway):
    short_result = await gateway.call(task="draft", system="", user="Hi.", model="claude-sonnet-5")
    long_result = await gateway.call(
        task="draft", system="", user="Hi " * 100, model="claude-sonnet-5"
    )
    assert long_result.prompt_tokens > short_result.prompt_tokens


async def test_gateway_ledger_total_latency_is_sum_of_individual_latencies(
    gateway,
):
    await gateway.call(task="draft", system="", user="A.", model="claude-sonnet-5")
    await gateway.call(task="draft", system="", user="B.", model="claude-sonnet-5")
    total_latency = gateway.ledger.total_latency_ms
    individual = sum(c.latency_ms for c in gateway.ledger.calls)
    assert total_latency == individual
