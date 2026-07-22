"""Model Gateway.

Routes a logical task ("draft", "critique", "revise") to a concrete model,
tracks cost/latency/provenance for every call, and supports a mock mode so
the whole harness is runnable and testable without hitting a real API or
spending money. Swap MOCK_MODE off and set ANTHROPIC_API_KEY to go live.

This is deliberately the file you'd point to in an interview and say:
"here's where I made a cost/latency tradeoff decision, and here's the data
that backed it up" — every call is logged, nothing is invisible.
"""
from __future__ import annotations

import base64
import mimetypes
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

import app.logging_config  # noqa: F401 -- configures structlog on import, side effect intentional
from app.config import settings

log = structlog.get_logger(component="gateway")

MOCK_MODE = settings.mock_mode

# Rough per-1M-token prices (USD). Update as needed; this is a stand-in,
# not a source of truth. Keeping it explicit and swappable is the point.
MODEL_PRICES = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 15.00, "output": 75.00},
}

TASK_DEFAULT_MODEL = {
    # Cheap model by default for drafting -- the harness's job is to make
    # this viable. Escalate only when the rubric says quality is lacking.
    "draft": "claude-haiku-4-5-20251001",
    "critique": "claude-sonnet-5",
    "revise": "claude-haiku-4-5-20251001",
    # Vision-grounded critique needs a model that actually looks at the
    # image, not just describes what it assumes an image like that would
    # show -- Haiku can do vision too, but Sonnet is the safer default
    # for a critic whose judgment we're about to feed into rubric weights.
    "visual_critique": "claude-sonnet-5",
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

    def __init__(self, ledger: GatewayLedger | None = None):
        self.ledger = ledger or GatewayLedger()
        self._client = None
        if not MOCK_MODE:
            import anthropic  # local import so mock mode never needs the package installed

            # api_key=None lets the SDK fall back to the standard
            # ANTHROPIC_API_KEY env var if HARNESS_ANTHROPIC_API_KEY isn't set.
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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
        )
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
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            latency_ms=round(latency_ms, 1),
            cost_usd=round(cost, 6),
            n_images=n_images,
        )
        return result

    def call(self, task: str, system: str, user: str, model: str | None = None) -> CallResult:
        model = model or TASK_DEFAULT_MODEL.get(task, "claude-sonnet-5")
        start = time.perf_counter()

        if MOCK_MODE:
            text, prompt_tok, completion_tok = self._mock_response(task, user)
        else:
            resp = self._client.messages.create(
                model=model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            prompt_tok = resp.usage.input_tokens
            completion_tok = resp.usage.output_tokens

        latency_ms = (time.perf_counter() - start) * 1000
        return self._record(task, model, text, prompt_tok, completion_tok, latency_ms)

    def call_vision(
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
        model = model or TASK_DEFAULT_MODEL.get(task, "claude-sonnet-5")
        start = time.perf_counter()

        if MOCK_MODE:
            text, prompt_tok, completion_tok = self._mock_vision_response(
                task, user_text, len(image_paths)
            )
        else:
            content: list[dict] = []
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

            resp = self._client.messages.create(
                model=model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            prompt_tok = resp.usage.input_tokens
            completion_tok = resp.usage.output_tokens

        latency_ms = (time.perf_counter() - start) * 1000
        return self._record(
            task, model, text, prompt_tok, completion_tok, latency_ms, n_images=len(image_paths)
        )

    @staticmethod
    def _mock_vision_response(task: str, user_text: str, n_images: int) -> tuple[str, int, int]:
        time.sleep(random.uniform(0.03, 0.10))  # vision calls are typically slower
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
    def _mock_response(task: str, user: str) -> tuple[str, int, int]:
        """Deterministic-ish fake responses so the loop is testable end to end
        without a network call. Latency is simulated to keep timing code honest."""
        time.sleep(random.uniform(0.02, 0.08))
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
