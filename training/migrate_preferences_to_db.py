"""Migration helper: import legacy JSONL preference data into the SQL database."""
from __future__ import annotations

from pathlib import Path

from app.preference_store import PreferenceStore


def main() -> None:
    data_dir = Path("data")
    jsonl_path = data_dir / "preferences.jsonl"

    with PreferenceStore() as store:
        count = store.migrate_from_jsonl(jsonl_path)
    print(f"Migrated {count} preference records into the SQL database.")


if __name__ == "__main__":
    main()
