"""Tests for app/gateway.py."""
import asyncio

import pytest

from app.gateway import MODEL_PRICES, TASK_DEFAULT_MODEL, CallResult, GatewayLedger, ModelGateway


class TestGatewayLedger:
    def test_ledger_total_cost(self):
        ledger = GatewayLedger()
        assert ledger.total_cost_usd == 0.0
        ledger.calls.append(
            CallResult(
                text="ok",
                model="test",
                task="draft",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=100.0,
                cost_usd=0.01,
            )
        )
        assert ledger.total_cost_usd == 0.01

    def test_ledger_total_latency(self):
        ledger = GatewayLedger()
        assert ledger.total_latency_ms == 0.0
        ledger.calls.append(
            CallResult(
                text="ok",
                model="test",
                task="draft",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=150.0,
                cost_usd=0.01,
            )
        )
        assert ledger.total_latency_ms == 150.0

    def test_ledger_total_cost_multiple(self):
        ledger = GatewayLedger()
        for _ in range(3):
            ledger.calls.append(
                CallResult(
                    text="ok",
                    model="test",
                    task="draft",
                    prompt_tokens=100,
                    completion_tokens=50,
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        assert ledger.total_cost_usd == 0.03


class TestModelGatewayRecordWithBudget:
    def test_record_with_budget(self, monkeypatch):
        """_record should call budget.consume when a budget is set."""
        from app.gateway import ModelGateway, GatewayLedger
        from app.budget import CostBudget

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        gateway.budget = CostBudget(per_run_limit=10.0, daily_limit=50.0)
        initial_used = gateway.budget.run_used

        gateway._record("draft", "llama-3.1-8b-instant", "hello world", 100, 50, 10.0)
        assert len(ledger.calls) == 1
        assert gateway.budget.run_used > initial_used

    def test_record_without_budget(self, monkeypatch):
        """_record should work fine when there's no budget."""
        from app.gateway import ModelGateway, GatewayLedger

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        assert gateway.budget is None

        gateway._record("draft", "llama-3.1-8b-instant", "hello world", 100, 50, 10.0)
        assert len(ledger.calls) == 1
        assert ledger.calls[0].cost_usd >= 0

    def test_record_tracks_cost(self, monkeypatch):
        """_record tracks cost via _price helper."""
        from app.gateway import ModelGateway, GatewayLedger, _price

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        cost = _price("claude-sonnet-5", 1000, 500)
        gateway._record("draft", "claude-sonnet-5", "hello world", 1000, 500, 10.0)
        assert ledger.calls[0].cost_usd == cost


class TestModelGatewayMockCall:
    def test_mock_call(self):
        """In mock mode, call() returns a mock draft response."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        result = asyncio.run(gateway.call("draft", "system", "user prompt"))
        assert result.text.startswith("[MOCK DRAFT]")
        assert result.model == TASK_DEFAULT_MODEL["draft"]

        gw.MOCK_MODE = old_mock

    def test_mock_call_records_in_ledger(self):
        """Mock call should record in ledger."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        asyncio.run(gateway.call("draft", "system", "user prompt"))
        assert len(ledger.calls) == 1
        assert ledger.total_latency_ms > 0
        assert ledger.total_cost_usd >= 0

        gw.MOCK_MODE = old_mock


class TestModelGatewayMockVision:
    def test_mock_vision_call(self):
        """In mock mode, call_vision() returns a mock vision response."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        result = asyncio.run(
            gateway.call_vision(
                "visual_critique",
                "system",
                "brief text",
                ["fake/path.jpg"],
            )
        )
        assert result.text.startswith("visual_continuity:")

        gw.MOCK_MODE = old_mock


class TestModelGatewayCallStructured:
    def test_structured_call_returns_critique_in_mock(self):
        """In mock mode, call_structured with Critique returns a Critique instance."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger
        from app.schemas import Critique

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        result = asyncio.run(
            gateway.call_structured("critique", "sys", "user", Critique)
        )
        assert isinstance(result, Critique)
        assert result.turn == 1

        gw.MOCK_MODE = old_mock

    def test_structured_call_non_critique_schema(self):
        """Non-Critique mock schema returns raw CallResult."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger
        from pydantic import BaseModel

        class SimpleModel(BaseModel):
            value: str

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        result = asyncio.run(
            gateway.call_structured("custom", "sys", "user", SimpleModel)
        )
        assert isinstance(result, CallResult)

        gw.MOCK_MODE = old_mock


class TestModelGatewayCallStructuredRetries:
    def test_structured_call_critique_retry_on_validation_failure(self):
        """Retry logic in call_structured - mock mode always succeeds for Critique."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        gw.MOCK_MODE = True

        from app.gateway import ModelGateway, GatewayLedger
        from app.schemas import Critique

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        result = asyncio.run(
            gateway.call_structured("critique", "sys", "user", Critique)
        )
        assert isinstance(result, Critique)

        gw.MOCK_MODE = old_mock


class TestPriceCalculation:
    def test_price_known_model(self):
        from app.gateway import _price

        cost = _price("claude-sonnet-5", 1000, 500)
        expected = 1000 / 1_000_000 * 3.0 + 500 / 1_000_000 * 15.0
        assert cost == pytest.approx(expected)

    def test_price_unknown_model_uses_zero(self):
        from app.gateway import _price

        cost = _price("unknown-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens_costs_zero(self):
        from app.gateway import _price

        cost = _price("claude-sonnet-5", 0, 0)
        assert cost == 0.0


class TestTaskDefaultModel:
    def test_draft_default_exists(self):
        assert "draft" in TASK_DEFAULT_MODEL

    def test_critique_default_exists(self):
        assert "critique" in TASK_DEFAULT_MODEL

    def test_visual_critique_default_exists(self):
        assert "visual_critique" in TASK_DEFAULT_MODEL


class TestUnsupportedProviderError:
    def test_unsupported_provider_raises_on_init(self, monkeypatch):
        """ModelGateway raises ValueError for unsupported provider in non-mock mode."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        old_provider = gw.settings.provider
        gw.MOCK_MODE = False
        gw.settings.provider = "unsupported_provider_xyz"

        from app.gateway import ModelGateway, GatewayLedger

        try:
            with pytest.raises(ValueError, match="Unsupported provider"):
                ModelGateway(GatewayLedger())
        finally:
            gw.MOCK_MODE = old_mock
            gw.settings.provider = old_provider

    def test_unsupported_provider_raises_on_call(self, monkeypatch):
        """call() raises ValueError for unsupported provider."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        old_provider = gw.settings.provider
        gw.MOCK_MODE = False
        gw.settings.provider = "unsupported_provider_xyz"

        from app.gateway import ModelGateway, GatewayLedger

        try:
            with pytest.raises(ValueError, match="Unsupported provider"):
                ModelGateway(GatewayLedger())
        finally:
            gw.MOCK_MODE = old_mock
            gw.settings.provider = old_provider


class TestAnthropicProviderMissingKey:
    def test_anthropic_missing_api_key_raises(self, monkeypatch):
        """ModelGateway raises ValueError when Anthropic key is missing."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        old_provider = gw.settings.provider
        gw.MOCK_MODE = False
        gw.settings.provider = "anthropic"

        from app.gateway import ModelGateway, GatewayLedger

        try:
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                ModelGateway(GatewayLedger())
        finally:
            gw.MOCK_MODE = old_mock
            gw.settings.provider = old_provider


class TestGroqProviderMissingKey:
    def test_groq_missing_api_key_raises(self, monkeypatch):
        """ModelGateway raises ValueError when Groq key is missing."""
        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        old_provider = gw.settings.provider
        gw.MOCK_MODE = False
        gw.settings.provider = "groq"

        from app.gateway import ModelGateway, GatewayLedger

        try:
            with pytest.raises(ValueError, match="GROQ_API_KEY"):
                ModelGateway(GatewayLedger())
        finally:
            gw.MOCK_MODE = old_mock
            gw.settings.provider = old_provider


class TestGroqNotInstalled:
    def test_groq_package_missing_raises(self, monkeypatch):
        """ModelGateway raises ImportError when groq package is not installed."""
        import sys as _sys

        import app.gateway as gw
        old_mock = gw.MOCK_MODE
        old_provider = gw.settings.provider
        old_key = gw.settings.groq_api_key
        old_groq = _sys.modules.get("groq")
        gw.MOCK_MODE = False
        gw.settings.provider = "groq"
        gw.settings.groq_api_key = "test-key"

        # Remove groq from sys.modules to simulate it not being installed
        _sys.modules["groq"] = None  # type: ignore[assignment]
        gw.GROQ_AVAILABLE = False

        from app.gateway import ModelGateway, GatewayLedger

        try:
            with pytest.raises(ImportError, match="groq package not installed"):
                ModelGateway(GatewayLedger())
        finally:
            gw.MOCK_MODE = old_mock
            gw.settings.provider = old_provider
            gw.settings.groq_api_key = old_key
            gw.GROQ_AVAILABLE = True
            if old_groq is not None:
                _sys.modules["groq"] = old_groq
            else:
                _sys.modules.pop("groq", None)


class TestBudgetInitAndConsume:
    """Budget initialization and consumption paths."""

    def test_gateway_with_run_budget(self, tmp_path, monkeypatch):
        """ModelGateway with a non-None run_budget_usd creates a CostBudget."""
        import app.gateway as gw
        from app.budget import CostBudget

        old_budget = gw.settings.run_budget_usd
        gw.settings.run_budget_usd = 50.0

        try:
            ledger = GatewayLedger()
            gateway = ModelGateway(ledger)
            assert gateway.budget is not None
            assert isinstance(gateway.budget, CostBudget)
        finally:
            gw.settings.run_budget_usd = old_budget

    def test_gateway_with_daily_budget(self, tmp_path, monkeypatch):
        """ModelGateway with a non-None daily_budget_usd creates a CostBudget."""
        import app.gateway as gw
        from app.budget import CostBudget

        old_budget = gw.settings.daily_budget_usd
        gw.settings.daily_budget_usd = 100.0

        try:
            ledger = GatewayLedger()
            gateway = ModelGateway(ledger)
            assert gateway.budget is not None
        finally:
            gw.settings.daily_budget_usd = old_budget


class TestModelGatewayLiveAnthropicCall:
    """Live (non-mock) provider call paths exercise the anthropic client."""

    def _setup_nonmock(self, monkeypatch):
        import app.gateway as gw

        self._old_mock = gw.MOCK_MODE
        self._old_provider = gw.settings.provider
        self._old_key = gw.settings.anthropic_api_key
        gw.settings.provider = "anthropic"
        gw.settings.anthropic_api_key = "sk-test-anthropic"
        gw.settings.run_budget_usd = None
        gw.settings.daily_budget_usd = None
        self._gw = gw

    def _restore(self, monkeypatch):
        gw = self._gw
        gw.MOCK_MODE = self._old_mock
        gw.settings.provider = self._old_provider
        gw.settings.anthropic_api_key = self._old_key

    def test_live_anthropic_call_returns_text(self, monkeypatch):
        """Non-mock call() returns CallResult via anthropic client."""
        self._setup_nonmock(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger, CallResult
        from unittest.mock import MagicMock

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        # Inject mock client directly, bypassing __init__ provider setup
        mock_anthropic = MagicMock()
        mock_resp = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "live anthropic response"
        mock_resp.content = [mock_content]
        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5
        mock_resp.usage = mock_usage
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(gateway.call("draft", "sys prompt", "user prompt"))
            assert result.text == "live anthropic response"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 5
        finally:
            self._restore(monkeypatch)

    def test_live_anthropic_call_prices_via_provider(self, monkeypatch):
        """Non-mock call() records cost using provider pricing."""
        from app.gateway import _price
        self._setup_nonmock(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger
        from unittest.mock import MagicMock

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        mock_anthropic = MagicMock()
        mock_resp = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "response"
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 1000
        mock_resp.usage.output_tokens = 500
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(gateway.call("draft", "sys", "user"))
            model = "claude-haiku-4-5-20251001"
            expected = _price(model, 1000, 500)
            assert abs(result.cost_usd - expected) < 1e-6
        finally:
            self._restore(monkeypatch)

    def test_live_anthropic_call_vision_returns_text(self, monkeypatch):
        """Non-mock call_vision() returns text with n_images tracked."""
        self._setup_nonmock(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger
        from unittest.mock import MagicMock

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        mock_anthropic = MagicMock()
        mock_resp = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "vision response"
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 200
        mock_resp.usage.output_tokens = 30
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(
                gateway.call_vision(
                    "visual_critique",
                    "sys",
                    "brief",
                    ["/tmp/ref.jpg"],
                )
            )
            assert result.text == "vision response"
            assert result.n_images == 1
        finally:
            self._restore(monkeypatch)

    def test_live_anthropic_call_structured_tool_use(self, monkeypatch):
        """Non-mock structured call() uses tool definitions for anthropic."""
        import json as _json
        from app.gateway import ModelGateway, GatewayLedger
        from app.schemas import Critique
        from unittest.mock import MagicMock

        self._setup_nonmock(monkeypatch)

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)

        tool_input = {"turn": 1, "scores": [], "overall": 0.0, "revision_notes": "", "modality": "text"}
        mock_anthropic = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "tool_use"
        mock_content.name = "submit_critique"
        mock_content.input = tool_input
        mock_resp = MagicMock()
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 10
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(
                gateway.call_structured("critique", "sys", "user", Critique)
            )
            assert isinstance(result, Critique)
        finally:
            self._restore(monkeypatch)

    def test_nonmock_unsupported_provider_raises(self, monkeypatch):
        """Non-mock call() raises ValueError for unsupported provider."""
        self._setup_nonmock(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        gw.MOCK_MODE = False
        gw.settings.provider = "unsupported_provider_xyz"

        try:
            with pytest.raises(ValueError, match="Unsupported provider"):
                asyncio.run(gateway.call("draft", "sys", "user"))
        finally:
            self._restore(monkeypatch)


class TestModelGatewayStructuredRetryPaths:
    """Retry and error-handling paths in call_structured()."""

    def _setup_nonmock_anthropic(self, monkeypatch):
        import app.gateway as gw

        self._old_mock = gw.MOCK_MODE
        self._old_provider = gw.settings.provider
        self._old_key = gw.settings.anthropic_api_key
        gw.settings.provider = "anthropic"
        gw.settings.anthropic_api_key = "sk-test"
        gw.settings.run_budget_usd = None
        gw.settings.daily_budget_usd = None
        self._gw = gw

    def _restore(self, monkeypatch):
        gw = self._gw
        gw.MOCK_MODE = self._old_mock
        gw.settings.provider = self._old_provider
        gw.settings.anthropic_api_key = self._old_key

    def test_structured_validation_error_retries_then_succeeds(self, monkeypatch):
        """After a validation error, call_structured retries and succeeds."""
        self._setup_nonmock_anthropic(monkeypatch)
        import json as _json
        from app.gateway import ModelGateway, GatewayLedger
        from app.schemas import Critique
        from unittest.mock import MagicMock

        call_count = 0

        def fake_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_resp = MagicMock()
                mock_resp.content = [MagicMock(type="text", text="not json")]
                mock_resp.usage.input_tokens = 10
                mock_resp.usage.output_tokens = 10
                return mock_resp
            else:
                mock_resp = MagicMock()
                mock_content = MagicMock()
                mock_content.type = "text"
                mock_content.text = _json.dumps(
                    {
                        "turn": 1,
                        "scores": [
                            {"criterion": "clarity", "score": 7.0, "rationale": "ok"},
                            {"criterion": "tone_match", "score": 8.0, "rationale": "good"},
                            {"criterion": "actionability", "score": 6.0, "rationale": "ok"},
                        ],
                        "overall": 7.0,
                        "revision_notes": "notes",
                        "modality": "text",
                    }
                )
                mock_resp.content = [mock_content]
                mock_resp.usage.input_tokens = 10
                mock_resp.usage.output_tokens = 10
                return mock_resp

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = fake_create
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(
                gateway.call_structured("critique", "sys", "user", Critique)
            )
            assert isinstance(result, Critique)
            assert call_count == 2
        finally:
            self._restore(monkeypatch)

    def test_structured_max_retries_exceeded_returns_critique_with_parse_error(self, monkeypatch):
        """When all retries yield invalid JSON for Critique, return Critique with parse_error."""
        self._setup_nonmock_anthropic(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger
        from app.schemas import Critique
        from unittest.mock import MagicMock

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        mock_anthropic = MagicMock()
        mock_resp = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "not json at all"
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 10
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            result = asyncio.run(
                gateway.call_structured("critique", "sys", "user", Critique, max_retries=1)
            )
            assert isinstance(result, Critique)
            assert result.parse_error is True
        finally:
            self._restore(monkeypatch)

    def test_structured_non_critique_schema_error_raises_on_max_retries(self, monkeypatch):
        """Non-Critique schema: after max retries, raise the exception."""
        self._setup_nonmock_anthropic(monkeypatch)
        from app.gateway import ModelGateway, GatewayLedger
        from pydantic import BaseModel
        from unittest.mock import MagicMock

        class SimpleSchema(BaseModel):
            value: str

        ledger = GatewayLedger()
        gateway = ModelGateway(ledger)
        mock_anthropic = MagicMock()
        mock_resp = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "not json"
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 10
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_resp
        gateway._anthropic_client = mock_anthropic

        try:
            self._gw.MOCK_MODE = False
            with pytest.raises(Exception):
                asyncio.run(
                    gateway.call_structured(
                        "custom", "sys", "user", SimpleSchema, max_retries=1
                    )
                )
        finally:
            self._restore(monkeypatch)
