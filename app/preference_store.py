"""Stores pairwise human preference judgments (JSONL, append-only).

This is the bridge between "live rubric" (phase 2) and "post-training"
(phase 4): the same file that updates rubric weights today becomes the
DPO training data later. One data collection effort, two uses -- that
reuse is the actual design decision worth defending in an interview,
not the fact that a JSONL file exists.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.schemas import PreferencePair


class PreferenceStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(settings.preferences_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, pref: PreferencePair) -> None:
        with self.path.open("a") as f:
            f.write(pref.model_dump_json() + "\n")

    def all(self) -> list[PreferencePair]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(PreferencePair(**json.loads(line)))
        return out
