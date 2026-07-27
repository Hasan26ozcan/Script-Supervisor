import json
from pathlib import Path

from app.preference_store import PreferenceStore
from app.schemas import PreferencePair
from training.dpo_train import load_dpo_dataset, validate_dpo_record


def test_load_dpo_dataset_and_validate_records(tmp_path):
    dataset_path = tmp_path / "dpo_dataset.jsonl"
    records = [
        {"prompt": "Brief: test", "chosen": "A", "rejected": "B"},
        {"prompt": "Brief: test 2", "chosen": "C", "rejected": "D"},
    ]
    with dataset_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    loaded = load_dpo_dataset(dataset_path)
    assert len(loaded) == 2
    assert loaded[0]["prompt"] == "Brief: test"
    assert loaded[1]["chosen"] == "C"


def test_validate_dpo_record_rejects_invalid_data():
    bad_record = {"prompt": "", "chosen": "A", "rejected": "B"}
    try:
        validate_dpo_record(bad_record)
        assert False, "Expected ValueError for empty prompt"
    except ValueError as exc:
        assert "must be a non-empty string" in str(exc)
