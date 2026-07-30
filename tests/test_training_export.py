import json

from app.preference_store import PreferenceStore
from app.schemas import PreferencePair
from training.export_dpo_dataset import export_dpo_dataset


def test_export_dpo_dataset_writes_records(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'prefs.db'}"
    with PreferenceStore(database_url=database_url) as store:
        store.add(
            PreferencePair(
                brief="A moody alley chase.",
                prompt="Brief: A moody alley chase.\n\nShot list:\n1. low angle",
                candidate_a="A1",
                candidate_b="B1",
                winner="a",
            )
        )
    store.add(
        PreferencePair(
            brief="A daylit studio.",
            prompt="",
            candidate_a="A2",
            candidate_b="B2",
            winner="b",
        )
    )

    output_path = tmp_path / "dpo_dataset.jsonl"
    count = export_dpo_dataset(store, output_path)

    assert count == 2
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["prompt"].startswith("Brief: A moody alley chase.")
    assert first["chosen"] == "A1"
    assert first["rejected"] == "B1"
    second = json.loads(lines[1])
    assert second["prompt"].startswith("Brief: A daylit studio.")
    assert second["chosen"] == "B2"
    assert second["rejected"] == "A2"
