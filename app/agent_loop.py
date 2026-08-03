"""Correction Loop: draft -> critique -> revise, with an honest stop condition.

The interesting engineering question here isn't "call the model in a loop" --
it's *when to stop*, and whether correction is actually improving anything
or just producing longer, more confident-sounding output. This module logs
enough (`RunTrace`) to answer that question later with data, not vibes.
"""

from __future__ import annotations

from typing import Literal

from app.config import settings
from app.gateway import GatewayLedger, ModelGateway
from app.prompts import get_prompt
from app.routing import AdaptiveRouter
from app.rubric import Rubric
from app.schemas import Critique, Draft, ReferenceImage, RunTrace, TraceStep

# Note: We no longer hardcode prompt strings here - they're loaded from the prompt registry
# DRAFT_SYSTEM, CRITIQUE_SYSTEM, and VISION_CRITIQUE_SYSTEM are kept for backward compatibility
# but are no longer used in the main flow


class CorrectionLoop:
    def __init__(
        self,
        gateway: ModelGateway | None = None,
        rubric: Rubric | None = None,
        router: AdaptiveRouter | None = None,
        model_overrides: dict[str, str] | None = None,
        max_turns: int = 3,
        plateau_epsilon: float = 0.3,
        threshold: float = 8.0,
        quality_per_dollar_threshold: float | None = None,
    ):
        self.gateway = gateway or ModelGateway(GatewayLedger())
        self.rubric = rubric or Rubric()
        self.router = router or AdaptiveRouter.load_from_file(settings.routing_rules_path)
        self.model_overrides = model_overrides or {}
        self.max_turns = max_turns
        self.plateau_epsilon = plateau_epsilon
        self.threshold = threshold
        self.quality_per_dollar_threshold = (
            quality_per_dollar_threshold
            if quality_per_dollar_threshold is not None
            else settings.cost_efficiency_threshold
        )

    async def _generate_draft(
        self, turn: int, brief: str, revision_notes: str, trace: RunTrace
    ) -> Draft:
        """Produce the draft (or revision) for a single turn."""
        draft_prompt = brief if turn == 1 else f"{brief}\n\nRevision notes: {revision_notes}"
        task = "draft" if turn == 1 else "revise"
        draft_system = get_prompt("draft")

        draft_model = self.model_overrides.get(task) or self.router.select_model(
            task, trace.steps
        )
        draft_call = await self.gateway.call(task, draft_system, draft_prompt, model=draft_model)
        return Draft(
            turn=turn,
            content=draft_call.text,
            model=draft_call.model,
            prompt_tokens=draft_call.prompt_tokens,
            completion_tokens=draft_call.completion_tokens,
            latency_ms=draft_call.latency_ms,
        )

    @staticmethod
    def _get_vision_critique_system() -> str:
        try:
            return get_prompt("vision_critique")
        except FileNotFoundError:
            # Fallback to regular critique if vision_critique not available
            return get_prompt("critique")

    async def _run_vision_critique(
        self,
        brief: str,
        draft: Draft,
        reference_images: list[ReferenceImage],
        trace: RunTrace,
    ):
        """Vision-grounded critique, using the reference images."""
        critique_model = self.model_overrides.get("visual_critique") or self.router.select_model(
            "visual_critique", trace.steps
        )
        captions = "; ".join(
            f"[{i + 1}] {ri.caption or 'no caption'}" for i, ri in enumerate(reference_images)
        )
        vision_prompt = (
            f"Brief: {brief}\n\nReference images: {captions}\n\nShot list:\n{draft.content}"
        )
        critique_call = await self.gateway.call_vision(
            "visual_critique",
            self._get_vision_critique_system(),
            vision_prompt,
            [ri.path for ri in reference_images],
            model=critique_model,
        )
        return critique_call, "vision"

    async def _run_text_critique(self, brief: str, draft: Draft, trace: RunTrace):
        """Plain text critique (no reference images, or vision skipped by router)."""
        critique_model = self.model_overrides.get("critique") or self.router.select_model(
            "critique", trace.steps
        )
        critique_call = await self.gateway.call(
            "critique",
            get_prompt("critique"),
            f"Brief: {brief}\n\nShot list:\n{draft.content}",
            model=critique_model,
        )
        return critique_call, "text"

    async def _generate_critique(
        self,
        brief: str,
        draft: Draft,
        reference_images: list[ReferenceImage],
        use_vision: bool,
        trace: RunTrace,
    ) -> Critique:
        modality: Literal["text", "vision"]
        if use_vision and self.router.should_use_vision(trace.steps):
            critique_call, modality = await self._run_vision_critique(
                brief, draft, reference_images, trace
            )
        else:
            critique_call, modality = await self._run_text_critique(brief, draft, trace)

        scores, revision_notes = self.rubric.parse_critique_text(critique_call.text)
        overall = self.rubric.weighted_overall(scores)
        return Critique(
            turn=draft.turn,
            scores=scores,
            overall=overall,
            revision_notes=revision_notes,
            modality=modality,
        )

    def _cost_aware_stop_reason(self, delta: float, prev_total_cost: float) -> str | None:
        """Whether the last turn's marginal quality gain was worth its cost."""
        if not (self.quality_per_dollar_threshold and self.quality_per_dollar_threshold > 0):
            return None
        last_turn_cost = self.gateway.ledger.total_cost_usd - prev_total_cost
        if last_turn_cost <= 0:
            return None
        quality_per_dollar = delta / last_turn_cost
        if quality_per_dollar < self.quality_per_dollar_threshold:
            return "cost_threshold"
        return None

    def _stop_reason(
        self, overall: float, prev_overall: float | None, prev_total_cost: float | None
    ) -> str | None:
        """Decide whether the loop should stop after this turn, and why."""
        if overall >= self.threshold:
            return "threshold_met"

        if prev_overall is None or prev_total_cost is None:
            return None

        # Cost-aware early stop: ask whether the last marginal quality
        # gain was worth the expense of another full turn. The point is
        # not to avoid every extra turn, but to stop when the gain is
        # too small relative to the cost.
        delta = overall - prev_overall
        cost_stop = self._cost_aware_stop_reason(delta, prev_total_cost)
        if cost_stop:
            return cost_stop
        if abs(delta) < self.plateau_epsilon:
            return "plateau"
        return None

    async def run(
        self,
        brief: str,
        reference_images: list[ReferenceImage] | None = None,
    ) -> RunTrace:
        reference_images = reference_images or []
        trace = RunTrace(input_brief=brief, reference_images=reference_images)
        prev_overall: float | None = None
        prev_total_cost: float | None = None
        revision_notes = ""
        use_vision = len(reference_images) > 0

        for turn in range(1, self.max_turns + 1):
            draft = await self._generate_draft(turn, brief, revision_notes, trace)
            critique = await self._generate_critique(
                brief, draft, reference_images, use_vision, trace
            )
            revision_notes = critique.revision_notes
            trace.steps.append(TraceStep(draft=draft, critique=critique))

            stop_reason = self._stop_reason(critique.overall, prev_overall, prev_total_cost)
            if stop_reason:
                trace.stop_reason = stop_reason
                break

            prev_overall = critique.overall
            prev_total_cost = self.gateway.ledger.total_cost_usd
        else:
            trace.stop_reason = "max_turns"

        trace.final_output = trace.steps[-1].draft.content
        trace.total_cost_usd = self.gateway.ledger.total_cost_usd
        trace.total_latency_ms = self.gateway.ledger.total_latency_ms
        return trace
