"""Correction Loop: draft -> critique -> revise, with an honest stop condition.

The interesting engineering question here isn't "call the model in a loop" --
it's *when to stop*, and whether correction is actually improving anything
or just producing longer, more confident-sounding output. This module logs
enough (`RunTrace`) to answer that question later with data, not vibes.
"""
from __future__ import annotations

from typing import Literal

from app.gateway import GatewayLedger, ModelGateway
from app.rubric import Rubric
from app.schemas import Critique, Draft, ReferenceImage, RunTrace, TraceStep

DRAFT_SYSTEM = (
    "You are a shot-list generator for film/TV pre-production. Given a scene "
    "brief, produce a numbered shot list and a one-line director's note. Be "
    "specific: lens choices, camera movement, framing. If given revision "
    "notes, address them directly rather than restating the previous draft."
)

CRITIQUE_SYSTEM = (
    "You are a script supervisor reviewing a shot list against a brief. "
    "Score each criterion 0-10 with a one-line rationale, in the exact "
    "format 'criterion: score/10 - rationale', one per line. Criteria: "
    "clarity, tone_match, actionability. End with a line "
    "'revision_notes: ...' giving the single most useful change to make."
)

# The VLM path: the critic actually looks at reference image(s) --
# location scout photos, mood boards, or a prior shot's still frame -- and
# grounds its judgment in what's visually there, not a text description of
# what an image like that "would probably" look like.
VISION_CRITIQUE_SYSTEM = (
    "You are a script supervisor reviewing a shot list against a brief AND "
    "one or more reference images (location scout photos, mood board frames, "
    "or continuity stills). Judge whether the shot list's implied visuals "
    "(lighting, framing, mood, spatial continuity) actually match what's in "
    "the reference image(s) -- not just whether the text sounds plausible. "
    "Score each criterion 0-10 with a one-line rationale, in the exact "
    "format 'criterion: score/10 - rationale', one per line. Criteria: "
    "visual_continuity, lighting_match, mood_match. End with a line "
    "'revision_notes: ...' giving the single most useful change to make, "
    "referencing something specific and visible in the reference image(s)."
)


class CorrectionLoop:
    def __init__(
        self,
        gateway: ModelGateway | None = None,
        rubric: Rubric | None = None,
        max_turns: int = 3,
        plateau_epsilon: float = 0.3,
        threshold: float = 8.0,
    ):
        self.gateway = gateway or ModelGateway(GatewayLedger())
        self.rubric = rubric or Rubric()
        self.max_turns = max_turns
        self.plateau_epsilon = plateau_epsilon
        self.threshold = threshold

    def run(self, brief: str, reference_images: list[ReferenceImage] | None = None) -> RunTrace:
        reference_images = reference_images or []
        trace = RunTrace(input_brief=brief, reference_images=reference_images)
        prev_overall: float | None = None
        revision_notes = ""
        use_vision = len(reference_images) > 0

        for turn in range(1, self.max_turns + 1):
            draft_prompt = brief if turn == 1 else f"{brief}\n\nRevision notes: {revision_notes}"
            task = "draft" if turn == 1 else "revise"
            draft_call = self.gateway.call(task, DRAFT_SYSTEM, draft_prompt)
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
                critique_call = self.gateway.call_vision(
                    "visual_critique",
                    VISION_CRITIQUE_SYSTEM,
                    vision_prompt,
                    [ri.path for ri in reference_images],
                )
                modality = "vision"
            else:
                critique_call = self.gateway.call(
                    "critique", CRITIQUE_SYSTEM, f"Brief: {brief}\n\nShot list:\n{draft.content}"
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
            if prev_overall is not None and abs(overall - prev_overall) < self.plateau_epsilon:
                trace.stop_reason = "plateau"
                break
            prev_overall = overall
        else:
            trace.stop_reason = "max_turns"

        trace.final_output = trace.steps[-1].draft.content
        trace.total_cost_usd = self.gateway.ledger.total_cost_usd
        trace.total_latency_ms = self.gateway.ledger.total_latency_ms
        return trace
