"""Phase 9: Run a dry DPO export dry-run using mock mode and TRL-style schema."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.preference_store import PreferenceStore
from training.export_dpo_dataset import export_dpo_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DPO dataset for Phase 9.")
    parser.add_argument("--output", type=Path, default=Path("data/dpo_dataset.jsonl"))
    args = parser.parse_args()

    store = PreferenceStore()
    count = export_dpo_dataset(store, args.output)
    print(f"DPO export complete: {count} records written to {args.output}")


if __name__ == "__main__":
    main()
