# Training — DPO Data Preparation & Fine-Tuning

This directory contains the Phase 9/10 pipeline for converting human preference
judgments into DPO (Direct Preference Optimization) training data, and for
optionally running a real DPO fine-tune on a GPU.

> **GPU note:** The training extras (`[training]`) pull in `torch`,
> `transformers`, `trl`, and `peft` — a multi-GB stack. They are **optional**
> and not installed by the core `pip install` for the API server. Install them
> only when you are ready to train.

---

## What's in This Directory

| Script | Purpose |
|---|---|
| `export_dpo_dataset.py` | Reads `data/preferences.jsonl`, writes `data/dpo_dataset.jsonl` in `{prompt, chosen, rejected}` format |
| `dpo_train.py` | Training wrapper — dry-run (mock) by default, real DPO train with TRL |
| `run_dpo.py` | Thin CLI wrapper around `export_dpo_dataset.py` for quick runs |
| `generate_fake_preferences.py` | Generates 20 illustrative fake human preference judgments |
| `migrate_preferences_to_db.py` | Migrates `data/preferences.jsonl` into `data/preferences.db` |

---

## Dependencies

### Core (always required)

These are part of the main `[dev]` extras and are always installed:

```
fastapi, pydantic, pydantic-settings, sqlalchemy, structlog
```

### Training extras (Phase 9/10 only)

Install with:

```bash
python -m pip install -e ".[training]"
```

This pulls in:

| Package | Version | Purpose |
|---|---|---|
| `trl` | >=1.0 | DPOTrainer, SFTTrainer, etc. (v1.0 consolidates all trainers) |
| `peft` | >=0.13 | LoRA adapter layers for parameter-efficient fine-tuning |
| `transformers` | >=4.45 | Model loading and tokenization |
| `accelerate` | >=1.0 | Distributed training orchestration |
| `datasets` | >=3.0 | Dataset loading and preprocessing |
| `bitsandbytes` | >=0.44 | 8-bit (QLoRA) quantization |

---

## Quick Start

### 1. Ensure preferences exist

The export reads from `data/preferences.jsonl`. To generate the 20-sample
demo dataset:

```bash
python -m training.generate_fake_preferences
```

This writes `data/preferences.jsonl` and migrates the data into PostgreSQL
(if available).

### 2. Export DPO dataset

```bash
python -m training.export_dpo_dataset
```

Output: `data/dpo_dataset.jsonl` — one JSON object per line:

```json
{"prompt": "Brief: ...\n\nShot list:\n", "chosen": "...", "rejected": "..."}
```

### 3. Dry-run training (no GPU required)

```bash
python training/dpo_train.py --mock --dry-run
```

This validates the dataset format and prints a summary without requiring the
full training stack:

```
DPO dataset summary:
  record_count: 20
  prompt_length_avg: 89.4
  chosen_length_avg: 156.3
  rejected_length_avg: 154.1
```

---

## Real DPO Training

### Prerequisites

- A machine with an NVIDIA GPU (24–48 GB VRAM recommended for 7–8B models)
- The `[training]` extras installed
- `data/dpo_dataset.jsonl` populated (see Step 2 above)

### Fine-Tuning Targets

| Task | Model | Notes |
|---|---|---|
| **Text generation** | Llama 3.1 8B Instruct or Qwen2.5 7B Instruct | Mature QLoRA/DPO recipes |
| **Vision fine-tuning** | **Qwen3-VL-8B-Instruct** | Recommended as of July 2026; supersedes Qwen2.5-VL-7B |

### Training Stack

TRL has consolidated into a single **v1.0 release** covering:

- `SFTTrainer` — Supervised fine-tuning
- `DPOTrainer` — Direct Preference Optimization
- `KTOTrainer` — Kahneman-Tversky Optimization
- `ORPOTrainer` — Ordered Preference Optimization
- `GRPOTrainer` — Generalized Reinforce Policy Optimization
- `RewardTrainer` — Reward model training

All trainers have **native Unsloth kernel integration** — roughly 2x faster
SFT/DPO and up to 70% less VRAM out of the box.

The default configuration uses:

```python
config = DPOConfig(
    model_name="meta-llama/Llama-3.1-8B-Instruct",
    learning_rate=5e-5,
    batch_size=1,       # micro-batch; gradient accumulation handles scaling
    epochs=1,
    output_dir="data/dpo_output",
)
```

### Running Real DPO Training

```bash
python training/dpo_train.py \
  --dataset data/dpo_dataset.jsonl \
  --output-dir data/dpo_output \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --epochs 1 \
  --batch-size 1 \
  --learning-rate 5e-5
```

**Important:** Always run `--mock --dry-run` first to confirm the environment,
data format, and checkpoint saving all work before committing to a full run.

### Vision Fine-Tuning

For vision-language models, use the community
[`2U1/Qwen-VL-Series-Finetune`](https://github.com/2U1/Qwen-VL-Series-Finetune)
implementation, which supports Qwen3-VL and Qwen3.5 in addition to Qwen2.5-VL:

```bash
# Qwen3-VL-8B requires this flag (check repo changelog for current status)
python training/dpo_train.py \
  --model Qwen/Qwen3-VL-8B-Instruct \
  --epochs 3 \
  --batch-size 2 \
  --learning-rate 1e-5 \
  --max-train-samples 100
```

> **Note:** As of July 2026, Qwen3.5-series variants require
> `--disable_flash_attn2 True` in that repository. Check the repo changelog
> before your dry run in case this has since been fixed.

---

## GPU Rental Guide

| Provider | Model | Price (USD/hr) | Notes |
|---|---|---|---|
| **RunPod** | RTX 4090 (24GB) | $0.34–0.69 | Balanced default; ~99% uptime SLA; 5-min setup |
| **Vast.ai** | RTX 4090 (24GB) spot | $0.09–0.59 | Cheaper if interruption-tolerant; marketplace pricing; no uptime SLA; can be reclaimed with ~15s notice |
| **Lambda Labs** | A100 80GB | $2.06 | H100 SXM: $2.99; ~99.9% SLA; use only if a long run makes interruption costly |

### Recommendations

- **For 50–150 preference pairs:** One 24–48GB GPU is sufficient. RunPod RTX
  4090 is the sensible default.
- **For longer runs (multi-epoch):** Lambda Labs A100 if the run exceeds 8
  hours and an interruption would be costly to redo.
- **For exploration / dry runs:** Vast.ai spot instance.

### Quick RunPod Setup

```bash
# 1. Create a pod (PyTorch 2.4+ container)
# 2. SSH in:
git clone https://github.com/Hasan26ozcan/Script-Supervisor.git
cd Script-Supervisor
python -m pip install -e ".[training]"
python -m training.generate_fake_preferences
python training/dpo_train.py --mock --dry-run
# If dry-run passes, run real training:
python training/dpo_train.py --model meta-llama/Llama-3.1-8B-Instruct --epochs 1
```

---

## Environment Documentation

A typical working DPO environment (verified July 2026):

```
Python:       3.11
CUDA:         12.4
torch:        2.4.1
transformers: 4.45.0
trl:          1.0.0
peft:         0.13.0
datasets:     3.0.0
accelerate:   1.0.0
```

Document your own environment after the first successful run so that future
iterations are not blocked by environment debugging.

---

## Phase 11: Database Migration

Phase 11 adds PostgreSQL/SQLite-backed preference storage for concurrent
raters and later analytics:

```bash
python training/migrate_preferences_to_db.py
```

This reads `data/preferences.jsonl` and writes to
`data/preferences.db` (SQLite) or the configured PostgreSQL database.

The new `app/db.py` module provides:

- `PreferencePairModel` — SQLAlchemy model for the `preferences` table
- `EvaluationRunModel` — SQLAlchemy model for the `evaluation_runs` table
- `create_sessionmaker()` — factory for SQLAlchemy sessions

Existing JSONL support remains intact — the database path is additive, not a
replacement.
