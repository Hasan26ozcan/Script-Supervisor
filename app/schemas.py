"""Core data models for the Creative Harness.

Kept deliberately small and explicit — every field here is something
that shows up in the eval, the trace, or the DPO export later. No field
exists "just in case."
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return uuid4().hex[:12]


class RubricScore(BaseModel):
    """A single critic pass's scoring against the live rubric."""

    criterion: str
    score: float = Field(ge=0, le=10)
    rationale: str


class ReferenceImage(BaseModel):
    """A visual reference the VLM critic grounds its judgment against --
    a location scout photo, a mood board frame, or a still from a prior
    shot (for continuity). Path-based, not raw bytes, so traces stay small
    and inspectable on disk."""

    path: str
    caption: str = ""  # e.g. "location scout: warehouse interior, dusk"


class Critique(BaseModel):
    turn: int
    scores: list[RubricScore]
    overall: float
    revision_notes: str  # what the critic wants changed, fed back to the generator
    modality: Literal["text", "vision"] = "text"  # was this critique VLM-grounded?


class Draft(BaseModel):
    turn: int
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class TraceStep(BaseModel):
    draft: Draft
    critique: Critique | None = None  # None on the final accepted turn if we stop early


class RunTrace(BaseModel):
    """Full record of one correction-loop run. This is what gets logged,
    inspected, and later mined for training data."""

    run_id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now)
    input_brief: str
    reference_images: list[ReferenceImage] = Field(default_factory=list)
    steps: list[TraceStep] = Field(default_factory=list)
    stop_reason: Literal[
        "max_turns", "plateau", "threshold_met", "cost_threshold", "error"
    ] | None = None
    final_output: str | None = None
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0


class PreferencePair(BaseModel):
    """One human judgment: given two candidate outputs for the same brief,
    which one is better. This is the atomic unit that both (a) updates
    rubric weights and (b) becomes DPO training data later."""

    pair_id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now)
    brief: str
    prompt: str = Field(
        default="",
        description="The exact prompt used to generate the candidate outputs.",
    )
    candidate_a: str
    candidate_b: str
    winner: Literal["a", "b", "tie"]
    rater: str = "anonymous"
    notes: str = ""


class ComparisonPair(BaseModel):
    pair_id: str
    source: str
    brief: str
    candidate_a: str
    candidate_b: str
    reference_image: str | None = None


class MemoryValidationRecord(BaseModel):
    timestamp: str = Field(default_factory=_now)
    score_a: float
    score_b: float
    predicted_winner: Literal["a", "b", "tie"]
    expected_winner: Literal["a", "b", "tie"]
    margin: float
    stale: bool


class MemoryEntry(BaseModel):
    entry_id: str = Field(default_factory=_uid)
    source_pair_id: str
    source: str
    brief: str
    prompt: str
    candidate_a: str
    candidate_b: str
    expected_winner: Literal["a", "b", "tie"]
    status: Literal["active", "stale", "replaced"] = "active"
    created_at: str = Field(default_factory=_now)
    last_validated_at: str | None = None
    effectiveness_score: float = 0.0
    validation_history: list[MemoryValidationRecord] = Field(default_factory=list)
    replacement_suggestion: str | None = None
