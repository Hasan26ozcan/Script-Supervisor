"""Correction Loop: draft -> critique -> revise, with an honest stop condition.

The interesting engineering question here isn't "call the model in a loop" --
it's *when to stop*, and whether correction is actually improving anything
or just producing longer, more confident-sounding output. This module logs
enough (`RunTrace`) to answer that question later with data, not vibes.
"""
from __future__ import annotations

import asyncio
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
            quality_per_dollar_threshold if quality_per_dollar_threshold is not None else settings.cost_efficiency_threshold
        )

    async def run(self, brief: str, reference_images: list[ReferenceImage] | None = None) -> RunTrace:
        reference_images = reference_images or []
        trace = RunTrace(input_brief=brief, reference_images=reference_images)
        prev_overall: float | None = None
        revision_notes = ""
        use_vision = len(reference_images) > 0

        for turn in range(1, self.max_turns + 1):
            # Get prompts from the registry
            draft_prompt = brief if turn == 1 else f"{brief}\n\nRevision notes: {revision_notes}"
            task = "draft" if turn == 1 else "revise"

            # Get prompts from registry
            draft_system = get_prompt("draft")
            critique_system = get_prompt("critique")
            try:
                vision_critique_system = get_prompt("vision_critique")
            except FileNotFoundError:
                # Fallback to regular critique if vision_critique not available
                vision_critique_system = get_prompt("critique")

            draft_model = self.model_overrides.get(task) or self.router.select_model(task, trace.steps)
            draft_call = await self.gateway.call(task, draft_system, draft_prompt, model=draft_model)
            draft = Draft(
                turn=turn,
                content=draft_call.text,
                model=draft_call.model,
                prompt_tokens=draft_call.prompt_tokens,
                completion_tokens=draft_call.completion_tokens,
                latency_ms=draft_call.latency_ms,
            )

            modality: Literal["text", "vision"]
            if use_vision:
                captions = "; ".join(
                    f"[{i+1}] {ri.caption or 'no caption'}" for i, ri in enumerate(reference_images)
                )
                vision_prompt = (
                    f"Brief: {brief}\n\nReference images: {captions}\n\n"
                    f"Shot list:\n{draft.content}"
                )
                critique_model = self.model_overrides.get("visual_critique") or self.router.select_model(
                    "visual_critique", trace.steps
                )
                critique_call = await self.gateway.call_vision(
                    "visual_critique",
                    vision_critique_system,
                    vision_prompt,
                    [ri.path for ri in reference_images],
                    model=critique_model,
                )
                modality = "vision"
            else:
                critique_model = self.model_overrides.get("critique") or self.router.select_model(
                    "critique", trace.steps
                )
                critique_call = await self.gateway.call(
                    "critique",
                    critique_system,
                    f"Brief: {brief}\n\nShot list:\n{draft.content}",
                    model=critique_model,
                )
                modality = "text"

            scores, revision_notes = self.rubric.parse_critique_text(critique_call.text)
            overall = self.rubric.weighted_overall(scores)
            critique = Critique(
                turn=turn,
                scores=scores,
                overall=overall,
                revision_notes=revision_notes,
                modality=modality,
            )

            trace.steps.append(TraceStep(draft=draft, critique=critique))

            if overall >= self.threshold:
                trace.stop_reason = "threshold_met"
                break

            if prev_overall is not None:
                # Cost-aware early stop: ask whether the last marginal quality
                # gain was worth the expense of another full turn. The point is
                # not to avoid every extra turn, but to stop when the gain is
                # too small relative to the cost.
                delta = overall - prev_overall
                if self.quality_per_dollar_threshold and self.quality_per_dollar_threshold > 0:
                    last_turn_cost = self.gateway.ledger.total_cost_usd - prev_total_cost
                    if last_turn_cost > 0:
                        quality_per_dollar = delta / last_turn_cost
                        if quality_per_dollar < self.quality_per_dollar_threshold:
                            trace.stop_reason = "cost_threshold"
                            break
                if abs(delta) < self.plateau_epsilon:
                    trace.stop_reason = "plateau"
                    break
            prev_overall = overall
            prev_total_cost = self.gateway.ledger.total_cost_usd
        else:
            trace.stop_reason = "max_turns"

        trace.final_output = trace.steps[-1].draft.content
        trace.total_cost_usd = self.gateway.ledger.total_cost_usd
        trace.total_latency_ms = self.gateway.ledger.total_latency_ms
        return trace