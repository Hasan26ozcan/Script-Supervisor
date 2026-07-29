"""Phase 10 DPO training wrapper for the Creative Harness.

This script is intentionally safe to run in mock/dry-run mode so the repo
can be validated without a GPU or the full TRL training stack installed.
If a real training environment is available, it can also invoke TRL's
`DPOTrainer` path.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from training.export_dpo_dataset import export_dpo_dataset

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt2"


def load_dpo_dataset(dataset_path: Path) -> list[dict[str, str]]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"DPO dataset not found: {dataset_path}")

    records: list[dict[str, str]] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            validate_dpo_record(record)
            records.append(record)
    if not records:
        raise ValueError("DPO dataset contains no valid records.")
    return records


def validate_dpo_record(record: dict[str, Any]) -> None:
    missing_keys = [k for k in ("prompt", "chosen", "rejected") if k not in record]
    if missing_keys:
        raise ValueError(f"DPO record missing required fields: {missing_keys}")
    for key in ("prompt", "chosen", "rejected"):
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError(f"DPO record field '{key}' must be a non-empty string")


def summarize_dataset(records: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "prompt_length_avg": sum(len(r["prompt"]) for r in records) / len(records),
        "chosen_length_avg": sum(len(r["chosen"]) for r in records) / len(records),
        "rejected_length_avg": sum(len(r["rejected"]) for r in records) / len(records),
    }


def mock_train(records: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_dataset(records)
    summary_path = output_dir / "mock_training_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info("Mock DPO training complete.")
    logger.info("Summary written to %s", summary_path)
    print(f"Mock DPO training completed for {summary['record_count']} records.")


def real_dpo_train(
    records: list[dict[str, str]],
    model_name: str,
    output_dir: Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_train_samples: int | None,
) -> None:
    try:
        from datasets import Dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise RuntimeError(
            "Real DPO training requires the training extras. Install with `pip install -e '.[training]'` "
            "and ensure `trl`, `transformers`, and `datasets` are available."
        ) from exc

    if max_train_samples is not None:
        records = records[:max_train_samples]

    dataset = Dataset.from_list(records)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    def tokenize(example: dict[str, str]) -> dict[str, Any]:
        prompt_tokens = tokenizer(example["prompt"], truncation=True, padding="longest")
        chosen_tokens = tokenizer(example["chosen"], truncation=True, padding="longest")
        rejected_tokens = tokenizer(example["rejected"], truncation=True, padding="longest")
        return {
            "input_ids": prompt_tokens["input_ids"],
            "attention_mask": prompt_tokens["attention_mask"],
            "chosen_input_ids": chosen_tokens["input_ids"],
            "rejected_input_ids": rejected_tokens["input_ids"],
        }

    tokenized = dataset.map(tokenize, batched=False)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    config = DPOConfig(
        model_name=model_name,
        learning_rate=learning_rate,
        batch_size=batch_size,
        epochs=epochs,
        output_dir=str(output_dir),
    )
    trainer = DPOTrainer(model=model, dataset=tokenized, config=config)
    trainer.train()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Real DPO training finished and checkpoints saved to %s", output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 10 DPO training wrapper.")
    parser.add_argument("--dataset", type=Path, default=Path("data/dpo_dataset.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/dpo_output"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--mock", action="store_true", help="Run a safe dry-run without requiring the full training stack.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the dataset and print a training summary without training.")
    parser.add_argument("--skip-export", action="store_true", help="Skip exporting the dataset before training.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.skip_export:
        from app.preference_store import PreferenceStore
        store = PreferenceStore()
        export_dpo_dataset(store, args.dataset)

    records = load_dpo_dataset(args.dataset)
    summary = summarize_dataset(records)
    print("DPO dataset summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    if args.dry_run or args.mock:
        mock_train(records, args.output_dir)
        return 0

    real_dpo_train(
        records=records,
        model_name=args.model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_train_samples=args.max_train_samples,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
