"""Mem0-style compression pair effectiveness tracking and replacement."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

from app.config import settings
from app.gateway import ModelGateway
from app.prompts import get_prompt
from app.rubric import Rubric
from app.schemas import ComparisonPair, MemoryEntry, MemoryValidationRecord


class Mem0Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(settings.mem0_state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                entry = MemoryEntry(**data)
                self.entries[entry.entry_id] = entry

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            for entry in self.entries.values():
                f.write(entry.model_dump_json() + "\n")

    def add_entry(
        self, pair: ComparisonPair, expected_winner: Literal["a", "b", "tie"]
    ) -> MemoryEntry:
        entry = MemoryEntry(
            source_pair_id=pair.pair_id,
            source=pair.source,
            brief=pair.brief,
            prompt=(f"Brief: {pair.brief}\n\nShot list:\n"),
            candidate_a=pair.candidate_a,
            candidate_b=pair.candidate_b,
            expected_winner=expected_winner,
            effectiveness_score=1.0,
        )
        self.entries[entry.entry_id] = entry
        self.save()
        return entry

    def mark_stale(self, entry_id: str, replacement: str | None = None) -> None:
        entry = self.entries[entry_id]
        entry.status = "stale"
        entry.replacement_suggestion = replacement
        self.save()

    def replace_entry(self, entry_id: str, new_entry: MemoryEntry) -> None:
        old = self.entries[entry_id]
        old.status = "replaced"
        self.entries[new_entry.entry_id] = new_entry
        self.save()

    async def validate_entry(
        self, entry_id: str, rubric: Rubric, gateway: ModelGateway
    ) -> MemoryValidationRecord:
        entry = self.entries[entry_id]
        critique_system = get_prompt("critique")
        prompt_a = f"Brief: {entry.brief}\n\nShot list:\n{entry.candidate_a}"
        prompt_b = f"Brief: {entry.brief}\n\nShot list:\n{entry.candidate_b}"
        call_a = await gateway.call("critique", critique_system, prompt_a)
        call_b = await gateway.call("critique", critique_system, prompt_b)
        scores_a, _ = rubric.parse_critique_text(call_a.text)
        scores_b, _ = rubric.parse_critique_text(call_b.text)
        score_a = rubric.weighted_overall(scores_a)
        score_b = rubric.weighted_overall(scores_b)
        predicted = "a" if score_a > score_b else "b" if score_b > score_a else "tie"
        margin = abs(score_a - score_b)
        stale = predicted != entry.expected_winner or margin < settings.mem0_stale_margin
        record = MemoryValidationRecord(
            score_a=score_a,
            score_b=score_b,
            predicted_winner=predicted,  # type: ignore[arg-type]
            expected_winner=entry.expected_winner,
            margin=margin,
            stale=stale,
        )
        entry.validation_history.append(record)
        entry.last_validated_at = record.timestamp
        if stale:
            entry.effectiveness_score = margin * 0.5
            entry.status = "stale"
            entry.replacement_suggestion = (
                "Re-evaluate this compression pair; replace with a new comparison example "
                "reflecting current model behavior."
            )
        else:
            entry.effectiveness_score = margin
            entry.status = "active"
        self.save()
        return record

    def find_stale_entries(self) -> list[MemoryEntry]:
        return [entry for entry in self.entries.values() if entry.status == "stale"]


class Mem0Manager:
    def __init__(
        self,
        store: Mem0Store | None = None,
        rubric: Rubric | None = None,
        gateway: ModelGateway | None = None,
    ):
        self.store = store or Mem0Store()
        self.rubric = rubric or Rubric()
        self.gateway = gateway or ModelGateway()

    def ingest_comparison_pair(
        self, pair: ComparisonPair, expected_winner: Literal["a", "b", "tie"]
    ) -> MemoryEntry:
        return self.store.add_entry(pair, expected_winner)

    async def validate_all(self) -> list[MemoryValidationRecord]:
        records = await asyncio.gather(
            *(
                self.store.validate_entry(entry_id, self.rubric, self.gateway)
                for entry_id in list(self.store.entries)
            )
        )
        return list(records)

    def refresh_stale(self) -> list[MemoryEntry]:
        stale = self.store.find_stale_entries()
        fresh_entries: list[MemoryEntry] = []
        for entry in stale:
            new_entry = MemoryEntry(
                source_pair_id=entry.source_pair_id,
                source=entry.source,
                brief=entry.brief,
                prompt=entry.prompt,
                candidate_a=entry.candidate_a,
                candidate_b=entry.candidate_b,
                expected_winner=entry.expected_winner,
                status="active",
                effectiveness_score=entry.effectiveness_score,
            )
            self.store.replace_entry(entry.entry_id, new_entry)
            fresh_entries.append(new_entry)
        return fresh_entries
