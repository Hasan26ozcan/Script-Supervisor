# Training / Phase 9

## Purpose

This folder contains the Phase 9 DPO data-preparation and dry-run scripts.
The goal is to convert human preference judgments into a format suitable for
TRL's DPOTrainer, then verify the export path before any expensive GPU work.

## Scripts

- `export_dpo_dataset.py`
  - Reads `data/preferences.jsonl`
  - Writes `data/dpo_dataset.jsonl`
  - Output format is `{prompt, chosen, rejected}` per line.

- `run_dpo.py`
  - Wrapper around the export script for a quick dry run.

- `generate_fake_preferences.py`
  - Generates 20 illustrative fake human preference judgments in `data/preferences.jsonl`.

## Getting started

1. Ensure preferences exist:
   - `data/preferences.jsonl` should contain one or more `PreferencePair` records.
2. Run the export:
   ```bash
   HARNESS_MOCK_MODE=1 .venv/Scripts/python.exe training/export_dpo_dataset.py
   ```
3. Validate the export:
   - `data/dpo_dataset.jsonl` should exist and contain one JSON object per line.

## Notes

- `PreferencePair.prompt` is required because a DPO record must reconstruct the exact prompt used to generate each candidate.
- This repo includes a Phase 10 DPO training wrapper in `training/dpo_train.py`.
- Use `--mock --dry-run` to validate your data format and environment without requiring the full training stack.
- Phase 11 adds architecture hardening: `app/db.py` for PostgreSQL-backed preferences, `app/budget.py` for explicit cost limits, `training/migrate_preferences_to_db.py` for JSONL -> PostgreSQL migration, and sample fake data generation.
