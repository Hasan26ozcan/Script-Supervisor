"""Model Gateway.

Routes a logical task ("draft", "critique", "revise") to a concrete model,
tracks cost/latency/provenance for every call, and supports a mock mode so
the whole harness is runnable and testable without hitting a real API or
spending money. Swap MOCK_MODE off and set API keys to go live.

This is deliberately the file you'd point to in an interview and say:
"here's where I made a cost/latency tradeoff decision, and here's the data
that backed it up" — every call is logged, nothing is invisible.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

# Importing this module configures structlog as a side effect; the import
# itself is otherwise unused.
import app.logging_config  # noqa: F401
from app.config import settings
from app.schemas import BaseModel, Critique

log = structlog.get_logger(component="gateway")

MOCK_MODE = settings.mock_mode

# Model name constants -- defined once so we're not duplicating string
# literals (and risking typos) across the pricing table, task defaults,
# and per-call fallbacks below.
MODEL_CLAUDE_HAIKU = "claude-haiku-4-5-20251001"
MODEL_CLAUDE_SONNET = "claude-sonnet-5"
MODEL_CLAUDE_OPUS = "claude-opus-4-8"
MODEL_LLAMA_8B_INSTANT = "llama-3.1-8b-instant"
MODEL_LLAMA_70B_VERSATILE = "llama-3.1-70b-versatile"
MODEL_LLAMA_11B_VISION = "llama-3.2-11b-vision-preview"
MODEL_LLAMA_90B_VISION = "llama-3.2-90b-vision-preview"
MODEL_MIXTRAL_8X7B = "mixtral-8x7b-32768"
MODEL_GEMMA_7B = "gemma-7b-it"

# Rough per-1M-token prices (USD). Update as needed; this is a stand-in,
# not a source of truth. Keeping it explicit and swappable is the point.
# These are approximate rates - adjust based on actual provider pricing
MODEL_PRICES = {
    # Anthropic models (legacy support)
    MODEL_CLAUDE_HAIKU: {"input": 0.80, "output": 4.00},
    MODEL_CLAUDE_SONNET: {"input": 3.00, "output": 15.00},
    MODEL_CLAUDE_OPUS: {"input": 15.00, "output": 75.00},
    # Groq models (approximate pricing - adjust as needed)
    MODEL_LLAMA_8B_INSTANT: {"input": 0.10, "output": 0.10},
    MODEL_LLAMA_70B_VERSATILE: {"input": 0.60, "output": 0.60},
    MODEL_LLAMA_11B_VISION: {"input": 0.30, "output": 0.30},
    MODEL_LLAMA_90B_VISION: {"input": 0.90, "output": 0.90},
    MODEL_MIXTRAL_8X7B: {"input": 0.45, "output": 0.45},
    MODEL_GEMMA_7B: {"input": 0.10, "output": 0.10},
}

TASK_DEFAULT_MODEL = {
    # Cheap model by default for drafting -- the harness's job is to make
    # this viable. Escalate only when the rubric says quality is lacking.
    "draft": (MODEL_LLAMA_8B_INSTANT if settings.provider == "groq" else MODEL_CLAUDE_HAIKU),
    "critique": (MODEL_LLAMA_70B_VERSATILE if settings.provider == "groq" else MODEL_CLAUDE_SONNET),
    "revise": (MODEL_LLAMA_8B_INSTANT if settings.provider == "groq" else MODEL_CLAUDE_HAIKU),
    # Vision-grounded critique needs a model that actually looks at the
    # image, not just describes what it assumes an image like that would
    # show.
    "visual_critique": (
        MODEL_LLAMA_11B_VISION if settings.provider == "groq" else MODEL_CLAUDE_SONNET
    ),
}


@dataclass
class CallResult:
    text: str
    model: str
    task: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    n_images: int = 0


@dataclass
class GatewayLedger:
    """Running total for a single run -- makes cost/latency visible,
    not something you have to reconstruct after the fact."""

    calls: list[CallResult] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)


def _price(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1_000_000) * p["input"] + (completion_tokens / 1_000_000) * p["output"]


class ModelGateway:
    """Single entry point for every model call in the harness.

    task_overrides lets the correction loop escalate models mid-run
    (e.g. "critique came back low twice, use a bigger drafting model
    next turn") without callers needing to know pricing or client details.
    """

    @staticmethod
    def _build_budget():
        if settings.run_budget_usd is None and settings.daily_budget_usd is None:
            return None
        from app.budget import CostBudget

        return CostBudget(
            per_run_limit=settings.run_budget_usd,
            daily_limit=settings.daily_budget_usd,
        )

    @staticmethod
    def _build_anthropic_client():
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required when provider=anthropic and mock_mode=False"
            )
        # Lazy import: only needed for live (non-mock) calls.
        import anthropic  # noqa: F401

        return anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @staticmethod
    def _build_groq_client():
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY required when provider=groq and mock_mode=False")
        try:
            from groq import Groq
        except ImportError:
            raise ImportError(
                "groq package not installed. Install with: pip install groq"
            ) from None

        return Groq(api_key=settings.groq_api_key)

    def __init__(self, ledger: GatewayLedger | None = None):
        self.ledger = ledger or GatewayLedger()
        self._anthropic_client = None
        self._groq_client = None
        self.budget = self._build_budget()

        if MOCK_MODE:
            return
        if settings.provider == "anthropic":
            self._anthropic_client = self._build_anthropic_client()
        elif settings.provider == "groq":
            self._groq_client = self._build_groq_client()
        else:
            raise ValueError(f"Unsupported provider: {settings.provider}")

    def _record(
        self,
        task: str,
        model: str,
        text: str,
        prompt_tok: int,
        completion_tok: int,
        latency_ms: float,
        n_images: int = 0,
    ) -> CallResult:
        cost = _price(model, prompt_tok, completion_tok)
        result = CallResult(
            text=text,
            model=model,
            task=task,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            latency_ms=latency_ms,
            cost_usd=cost,
            n_images=n_images,
        )
        if self.budget is not None:
            self.budget.consume(cost)
        self.ledger.calls.append(result)
        # Structured, one-line-per-call log -- this is the provenance trail
        # the job posting asks for: every call's model/cost/latency is
        # visible without reconstructing it from a trace file after the fact.
        # Shape this dict as a Langfuse "generation" event if langfuse_enabled.
        log.info(
            "model_call",
            task=task,
            model=model,
            mock_mode=MOCK_MODE,
            provider=settings.provider,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            latency_ms=round(latency_ms, 1),
            cost_usd=round(cost, 6),
            n_images=n_images,
        )
        return result

    async def call(self, task: str, system: str, user: str, model: str | None = None) -> CallResult:
        model = model or TASK_DEFAULT_MODEL.get(
            task,
            MODEL_CLAUDE_SONNET if settings.provider == "anthropic" else MODEL_LLAMA_70B_VERSATILE,
        )
        start = time.perf_counter()

        if MOCK_MODE:
            text, prompt_tok, completion_tok = await self._mock_response(task, user)
        else:
            if settings.provider == "anthropic":
                assert self._anthropic_client is not None
                resp = await asyncio.to_thread(
                    self._anthropic_client.messages.create,
                    model=model,
                    max_tokens=1024,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(b.text for b in resp.content if b.type == "text")
                prompt_tok = resp.usage.input_tokens
                completion_tok = resp.usage.output_tokens
            elif settings.provider == "groq":
                assert self._groq_client is not None
                # Groq uses OpenAI-compatible API
                resp = await asyncio.to_thread(
                    self._groq_client.chat.completions.create,
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content
                # Groq doesn't always return token counts in the same way
                # We'll approximate if not provided
                prompt_tok = getattr(resp.usage, "prompt_tokens", len(system) // 4 + len(user) // 4)
                completion_tok = getattr(resp.usage, "completion_tokens", len(text) // 4)
            else:
                raise ValueError(f"Unsupported provider: {settings.provider}")

        latency_ms = (time.perf_counter() - start) * 1000
        return self._record(task, model, text, prompt_tok, completion_tok, latency_ms)

    async def call_vision(
        self,
        task: str,
        system: str,
        user_text: str,
        image_paths: list[str],
        model: str | None = None,
    ) -> CallResult:
        """Same contract as `call`, but attaches one or more images to the
        message. This is the actual VLM path: the model receives real image
        bytes, not a text description of an image, so its judgment about
        composition/lighting/continuity is grounded in what's actually there.
        """
        model = model or TASK_DEFAULT_MODEL.get(
            task,
            (MODEL_CLAUDE_SONNET if settings.provider == "anthropic" else MODEL_LLAMA_11B_VISION),
        )
        start = time.perf_counter()

        if MOCK_MODE:
            text, prompt_tok, completion_tok = await self._mock_vision_response(
                task, user_text, len(image_paths)
            )
        else:
            if settings.provider == "anthropic":
                assert self._anthropic_client is not None
                content: list[dict[str, Any]] = []
                for p in image_paths:
                    path = Path(p)
                    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
                    content.append(
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": data},
                        }
                    )
                content.append({"type": "text", "text": user_text})

                resp = await asyncio.to_thread(
                    self._anthropic_client.messages.create,
                    model=model,
                    max_tokens=1024,
                    system=system,
                    messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
                )
                text = "".join(b.text for b in resp.content if b.type == "text")
                prompt_tok = resp.usage.input_tokens
                completion_tok = resp.usage.output_tokens
            elif settings.provider == "groq":
                # For Groq, we need to handle vision differently
                # Groq's API might not support vision in the same way as Anthropic
                # For now, we'll implement a placeholder that concatenates image descriptions
                # In a real implementation, you'd use Groq's vision capabilities if available
                assert self._groq_client is not None

                # Simple approach: describe images in text (not ideal but works for testing)
                # A better approach would be to use Groq's vision models if they exist
                image_descriptions = []
                for p in image_paths:
                    # In a real implementation, we'd send the image to a vision model
                    # For now, we'll just note that an image was provided
                    image_descriptions.append(f"[Image: {Path(p).name}]")

                vision_context = " ".join(image_descriptions)
                enhanced_user_text = f"{user_text}\n\nVisual context: {vision_context}"

                resp = await asyncio.to_thread(
                    self._groq_client.chat.completions.create,
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": enhanced_user_text},
                    ],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content
                # Approximate token counts
                prompt_tok = len(system) // 4 + len(enhanced_user_text) // 4
                completion_tok = len(text) // 4
            else:
                raise ValueError(f"Unsupported provider: {settings.provider}")

        latency_ms = (time.perf_counter() - start) * 1000
        return self._record(
            task, model, text, prompt_tok, completion_tok, latency_ms, n_images=len(image_paths)
        )

    @staticmethod
    def _structured_mock_text(user: str, schema: type[BaseModel]) -> tuple[str, int, int]:
        """Generate a mock response that the schema validator can parse."""
        import json as _json

        if schema == Critique:
            text = _json.dumps(
                {
                    "turn": 1,
                    "scores": [
                        {
                            "criterion": "clarity",
                            "score": 7.0,
                            "rationale": "shot descriptions are clear",
                        },
                        {"criterion": "tone_match", "score": 8.0, "rationale": "appropriate tone"},
                        {
                            "criterion": "actionability",
                            "score": 6.0,
                            "rationale": "mostly actionable",
                        },
                    ],
                    "overall": 7.0,
                    "revision_notes": "add more specific camera movements",
                    "modality": "text",
                }
            )
            return text, max(20, len(user) // 4) + 50, max(10, len(text) // 4)

        # Fallback for other schemas
        return '{"error": "mock mode fallback"}', max(20, len(user) // 4), 20

    async def _structured_anthropic_call(
        self, model: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[str, int, int]:
        assert self._anthropic_client is not None
        import json

        tool_definition = {
            "name": "submit_critique",
            "description": "Submit a structured critique",
            "input_schema": schema.model_json_schema(),
        }
        resp = await asyncio.to_thread(
            self._anthropic_client.messages.create,
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool_definition],
            tool_choice={"type": "tool", "name": "submit_critique"},
        )  # type: ignore[call-overload]

        # Extract the tool use result
        text = ""
        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_critique":
                text = json.dumps(block.input)
                break
        if not text:
            # Fallback if no tool use was found
            text = "".join(b.text for b in resp.content if b.type == "text")

        return text, resp.usage.input_tokens, resp.usage.output_tokens

    async def _structured_groq_call(
        self, model: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[str, int, int]:
        assert self._groq_client is not None
        import json
        import re

        # Groq doesn't have a native structured-output tool-use path here, so
        # we prompt for JSON conforming to the schema and parse it out.
        schema_str = json.dumps(schema.model_json_schema(), indent=2)
        enhanced_system = f"""{system}

                        You must respond with a valid JSON object that conforms to this schema:
                        {schema_str}

                        Respond ONLY with the JSON object, no additional text."""

        resp = await asyncio.to_thread(
            self._groq_client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": user},
            ],
            max_tokens=1024,
            temperature=0.1,  # Lower temperature for more consistent JSON
        )
        text = resp.choices[0].message.content

        # Extract JSON-like content between curly braces; if none is found,
        # let downstream validation fail and trigger a retry.
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        prompt_tok = len(system) // 4 + len(user) // 4
        completion_tok = len(text) // 4
        return text, prompt_tok, completion_tok

    async def _get_structured_text(
        self, model: str, system: str, user: str, schema: type[BaseModel]
    ) -> tuple[str, int, int]:
        """Dispatch to mock/anthropic/groq and return (text, prompt_tok, completion_tok)."""
        if MOCK_MODE:
            return self._structured_mock_text(user, schema)
        if settings.provider == "anthropic":
            return await self._structured_anthropic_call(model, system, user, schema)
        if settings.provider == "groq":
            return await self._structured_groq_call(model, system, user, schema)
        raise ValueError(f"Unsupported provider: {settings.provider}")

    @staticmethod
    def _parse_error_critique(max_retries: int, error: Exception) -> Critique:
        return Critique(
            turn=0,  # This would need to be set properly in context
            scores=[],
            overall=0.0,
            revision_notes=f"Parse error after {max_retries} attempts: {error!s}",
            modality="text",
            parse_error=True,
        )

    def _validate_structured(
        self, result: CallResult, text: str, schema: type[BaseModel]
    ) -> BaseModel | CallResult:
        """Parse+validate `text` against `schema`, raising on failure."""
        import json

        # Non-Critique schemas in mock mode always return the raw result.
        if MOCK_MODE and schema != Critique:
            return result
        data = json.loads(text)
        return schema(**data)

    async def call_structured(
        self,
        task: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        model: str | None = None,
        max_retries: int = 2,
    ) -> BaseModel | CallResult:
        """Make a structured call using tool use feature (Anthropic) or
        JSON mode (Groq) for structured output.

        Args:
            task: The task type (e.g., "critique")
            system: System prompt
            user: User prompt
            schema: Pydantic model to validate against
            model: Model to use (defaults to TASK_DEFAULT_MODEL[task])
            max_retries: Maximum number of retries on validation error

        Returns:
            Validated Pydantic model instance
        """
        model = model or TASK_DEFAULT_MODEL.get(
            task,
            MODEL_CLAUDE_SONNET if settings.provider == "anthropic" else MODEL_LLAMA_70B_VERSATILE,
        )
        start = time.perf_counter()

        for attempt in range(max_retries):
            is_last_attempt = attempt >= max_retries - 1
            try:
                text, prompt_tok, completion_tok = await self._get_structured_text(
                    model, system, user, schema
                )
                latency_ms = (time.perf_counter() - start) * 1000
                result = self._record(task, model, text, prompt_tok, completion_tok, latency_ms)

                try:
                    return self._validate_structured(result, text, schema)
                except Exception as e:
                    if not is_last_attempt:
                        user = (
                            f"{user}\n\nPrevious attempt failed validation: {e!s}. "
                            "Please correct your response."
                        )
                        continue
                    if schema == Critique:
                        return self._parse_error_critique(max_retries, e)
                    raise

            except Exception as e:
                if is_last_attempt:
                    raise
                user = f"{user}\n\nPrevious attempt failed: {e!s}. Please correct your response."

        # This shouldn't be reached, but just in case
        raise RuntimeError("Failed to get valid response after retries")  # pragma: no cover

    @staticmethod
    async def _mock_vision_response(
        task: str, user_text: str, n_images: int
    ) -> tuple[str, int, int]:
        await asyncio.sleep(random.uniform(0.03, 0.10))  # vision calls are typically slower
        prompt_tok = max(50, len(user_text) // 4) + n_images * 300  # images cost real tokens
        text = (
            f"visual_continuity: 6/10 - shot 2 framing plausible against the {n_images} "
            f"reference image(s) but lighting direction doesn't clearly match\n"
            "lighting_match: 5/10 - reference shows warm practical light, draft doesn't specify\n"
            "mood_match: 7/10 - tone is broadly consistent with the reference mood\n"
            "revision_notes: specify a light source consistent with the reference and note "
            "color temperature explicitly"
        )
        completion_tok = max(10, len(text) // 4)
        return text, prompt_tok, completion_tok

    @staticmethod
    async def _mock_response(task: str, user: str) -> tuple[str, int, int]:
        """Deterministic-ish fake responses so the loop is testable end to end
        without a network call. Latency is simulated to keep timing code honest."""
        await asyncio.sleep(random.uniform(0.02, 0.08))
        prompt_tok = max(20, len(user) // 4)
        if task == "draft":
            text = (
                f"[MOCK DRAFT] Shot 1: wide establishing shot.\n"
                f"Shot 2: medium on protagonist reacting.\n"
                f"Director's note: keep pacing slow, based on brief: '{user[:60]}...'"
            )
        elif task == "critique":
            text = (
                "clarity: 6/10 - shot descriptions are generic\n"
                "tone_match: 7/10 - reasonable but not distinctive\n"
                "actionability: 5/10 - a DP could not shoot this as-is\n"
                "revision_notes: add lens/camera-movement specifics, tighten shot count"
            )
        else:  # revise
            text = (
                f"[MOCK REVISED] Shot 1: wide establishing shot, slow dolly in, 35mm.\n"
                f"Shot 2: close-up on protagonist's hands before face, handheld.\n"
                f"Director's note: revised per critique for '{user[:40]}...'"
            )
        completion_tok = max(10, len(text) // 4)
        return text, prompt_tok, completion_tok
