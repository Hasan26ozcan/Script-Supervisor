"""Export DPO training data from collected preference pairs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.preference_store import PreferenceStore

DATA_DIR = Path("data")
EXPORT_PATH = DATA_DIR / "dpo_dataset.jsonl"


def export_dpo_dataset(store: PreferenceStore, export_path: Path) -> int:
    prefs = store.all()
    if not prefs:
        raise ValueError("No preference data available to export.")

    export_path = export_path.resolve()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with export_path.open("w", encoding="utf-8") as f:
        for pref in prefs:
            if pref.winner == "tie":
                continue
            prompt_text = pref.prompt.strip() or f"Brief: {pref.brief}\n\nShot list:\n"
            record: dict[str, Any] = {
                "prompt": prompt_text,
                "chosen": pref.candidate_a if pref.winner == "a" else pref.candidate_b,
                "rejected": pref.candidate_b if pref.winner == "a" else pref.candidate_a,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    store = PreferenceStore()
    count = export_dpo_dataset(store, EXPORT_PATH)
    print(f"Exported {count} DPO records to {EXPORT_PATH}")


if __name__ == "__main__":
    main()
