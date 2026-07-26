"""Live Rubric.

Two honest problems this file is trying to solve:

1. "Good" for creative output is subjective -- a fixed rubric with fixed
   weights is a guess. We want the weights to move toward what humans
   actually prefer, not what we assumed up front.
2. We need a *number* to optimize against (the job posting literally says
   "make quality a number we can move"), while being upfront that the
   number is a proxy, not the truth.

Approach: criteria are scored by an LLM critic (0-10 each). Weights start
uniform. Every time we get a human pairwise preference (A beats B), we
nudge weights toward whichever criteria best explain that judgment, using
a simple logistic (Bradley-Terry-style) update. This is intentionally
simple -- the point of phase 2 is proving the *mechanism* works, not
building a research-grade preference model on day one.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, UTC
from pathlib import Path

from app.config import settings
from app.schemas import PreferencePair, RubricScore

DEFAULT_CRITERIA = ["clarity", "tone_match", "actionability"]

# Only scored when a run includes reference images and the critic goes
# through the vision path. Kept as a separate list rather than merged into
# DEFAULT_CRITERIA so a text-only run's rubric isn't diluted by criteria
# it never actually gets scored on.
VISUAL_CRITERIA = ["visual_continuity", "lighting_match", "mood_match"]


class Rubric:
    def __init__(self, criteria: list[str] | None = None, weights_path: str | Path | None = None):
        self.criteria = criteria or list(DEFAULT_CRITERIA) + list(VISUAL_CRITERIA)
        self.weights_path = (
            Path(weights_path) if weights_path else Path(settings.rubric_weights_path)
        )
        self.weight_history_path = (
            self.weights_path.parent / "rubric_weight_history.jsonl"
            if weights_path
            else Path(settings.rubric_weight_history_path)
        )
        self.weights: dict[str, float] = self._load_weights()
        self.weight_history: list[dict] = self._load_history()

    def _load_weights(self) -> dict[str, float]:
        if self.weights_path.exists():
            saved = json.loads(self.weights_path.read_text())
            # keep any new criteria at default weight if rubric evolved
            return {c: saved.get(c, 1.0) for c in self.criteria}
        return {c: 1.0 for c in self.criteria}

    def save_weights(self) -> None:
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        self.weights_path.write_text(json.dumps(self.weights, indent=2))

    def _load_history(self) -> list[dict]:
        if not self.weight_history_path.exists():
            return []
        out: list[dict] = []
        with self.weight_history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out

    def record_weight_snapshot(self, pref: PreferencePair | None = None) -> None:
        self.weight_history_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "pair_id": pref.pair_id if pref else None,
            "brief": pref.brief if pref else None,
            "winner": pref.winner if pref else None,
            "weights": self.weights.copy(),
        }
        with self.weight_history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self.weight_history.append(entry)

    def parse_critique_text(self, raw: str) -> tuple[list[RubricScore], str]:
        """Parses the (mock or real) critic response of the form:
        `criterion: score/10 - rationale` per line, plus a revision_notes line.
        Real usage would ask the model for structured JSON output instead --
        this simple parser is a stand-in for phase 0/1."""
        scores: list[RubricScore] = []
        revision_notes = ""
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, rest = line.partition(":")
            key = key.strip()
            if key == "revision_notes":
                revision_notes = rest.strip()
                continue
            if key not in self.criteria:
                continue
            try:
                score_part = rest.strip().split("-", 1)[0].strip()
                score_val = float(score_part.split("/")[0])
                rationale = rest.strip().split("-", 1)[1].strip() if "-" in rest else ""
            except (ValueError, IndexError):
                continue
            scores.append(RubricScore(criterion=key, score=score_val, rationale=rationale))
        return scores, revision_notes

    def weighted_overall(self, scores: list[RubricScore]) -> float:
        if not scores:
            return 0.0
        total_w = sum(self.weights.get(s.criterion, 1.0) for s in scores)
        if total_w == 0:
            return sum(s.score for s in scores) / len(scores)
        return sum(s.score * self.weights.get(s.criterion, 1.0) for s in scores) / total_w

    def update_from_preference(
        self,
        pref: PreferencePair,
        scores_a: list[RubricScore],
        scores_b: list[RubricScore],
        learning_rate: float = 0.15,
    ) -> None:
        """Nudge weights toward criteria that correctly predicted the human's
        preference, and away from criteria that got it backwards. This is a
        simplified per-criterion Bradley-Terry gradient step, not a full
        joint fit -- good enough to demonstrate the mechanism moves in the
        right direction; a proper joint logistic regression is the phase-2
        upgrade once there's enough preference data to fit one.
        """
        if pref.winner == "tie":
            return
        a_wins = pref.winner == "a"
        by_a = {s.criterion: s.score for s in scores_a}
        by_b = {s.criterion: s.score for s in scores_b}

        for crit in self.criteria:
            sa, sb = by_a.get(crit), by_b.get(crit)
            if sa is None or sb is None:
                continue
            diff = sa - sb  # positive => this criterion says A is better
            predicted_a_better = diff > 0
            correct = predicted_a_better == a_wins
            # sigmoid-scaled confidence based on how large the diff was
            confidence = 1 / (1 + math.exp(-abs(diff)))
            direction = 1 if correct else -1
            self.weights[crit] = max(
                0.05, self.weights[crit] + learning_rate * direction * confidence
            )
        self.save_weights()
        self.record_weight_snapshot(pref)
