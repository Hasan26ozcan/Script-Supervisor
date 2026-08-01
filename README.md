# Creative Harness — Script Supervisor

[![CI](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/ci.yml/badge.svg)](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/ci.yml)
[![SonarQube](https://sonarcloud.io/api/project_badges/measure?project=hasan26ozcan_Script-Supervisor&metric=alert_status)](https://sonarcloud.io/summary/overall?id=hasan26ozcan_Script-Supervisor)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=hasan26ozcan_Script-Supervisor&metric=coverage)](https://sonarcloud.io/summary/overall?id=hasan26ozcan_Script-Supervisor)

A production-grade AI evaluation harness for creative shot list generation. It delivers a complete technical release with a FastAPI backend, prompt-driven correction loop, human preference collection, DPO dataset export, Mem0-style compression pair validation, PostgreSQL-backed persistence, and structured CI/CD.

---

## Table of Contents

- [About](#about)
- [Current state](#current-state)
- [Key features](#key-features)
- [Quick start](#quick-start)
- [Development workflow](#development-workflow)
- [Testing & quality](#testing--quality)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [CI/CD](#cicd)
- [Roadmap](#roadmap)
- [License](#license)

---

## About

This project answers a concrete research question with measurable evidence: can a structured correction loop, calibrated rubric, and vision-aware critique outperform a simple single-pass generation strategy while remaining cost-effective and auditable?

It is designed as a polished, maintainable release rather than a prototype. The core system is production-ready for internal evaluation and experimentation; real model usage and GPU training runs require API keys and optional GPU resources.

---

## Current state

| Area | Status |
|---|---|
| Core API (FastAPI + correction loop) | Complete |
| Mock & live gateway (async) | Complete |
| Vision-grounded critique | Complete |
| Rubric scoring + Bradley-Terry weight updates | Complete |
| Mem0 compression pair tracking | Complete |
| Preference persistence (PostgreSQL + JSONL fallback) | Complete |
| DPO dataset export + training wrapper | Complete |
| Cost-aware routing with YAML rules | Complete |
| Modern eval harness (Inspect AI adapter) | Complete |
| Statistical evaluation (bootstrap CI, Bradley-Terry, Cohen's κ) | Complete |
| Comparison UI | Complete |
| CI/CD (ruff, mypy, pytest, coverage, pip-audit, SonarCloud) | Complete |
| Phase notes (2, 4, 6, 7, 8, 11) | Present |

---

## Key features

- **End-to-end preference collection** via `/compare` and stored `PreferencePair` records
- **Mem0 compression pair tracking** with validation, stale detection, and replacement
- **DPO dataset export** from recorded preferences
- **Mock-safe training wrapper** with real TRL training support when the optional stack is installed
- **Async gateway abstraction** supporting mock and live providers
- **Routable escalation logic** through external YAML rules
- **PostgreSQL migration path** for preference persistence with JSONL fallback
- **Modern eval framework** — optional [Inspect AI](https://inspect.aisi.org.uk/) adapter for real model-graded pairwise runs with position-bias-checked scoring
- **Statistical evaluation** — bootstrap confidence intervals, binomial significance tests, Bradley-Terry fit, and judge/human agreement (Cohen's κ)

---

## Quick start

### Prerequisites

- Python 3.11 or newer
- Git
- Optional: Docker for containerized deployment

### Install

```bash
cd Script-Supervisor
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### Run locally

```bash
HARNESS_MOCK_MODE=1 uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

### Run the evaluation harness

```bash
python -m training.generate_fake_preferences
python -m app.evaluation_harness
```

This writes `docs/evaluation/evaluation_report.{md,html}`, `docs/evaluation/metrics.json`, and `docs/evaluation/charts/*.png` from the 20-sample fake human judgment dataset, and persists a run row to the configured SQL backend. Read `docs/evaluation/HARNESS_NOTES.md` first — it documents exactly what the statistics can and can't tell you about this demo dataset, and how to run the same pipeline against real PostgreSQL via Docker Compose.

For a real model-graded run via Inspect AI:

```bash
pip install inspect-ai
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view
```

### Run with real model calls

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your_key"
```

Then start the app as above.

---

## Development workflow

| Command | What it does |
|---|---|
| `make install` | Install the project and dev requirements |
| `make lint` | Run `ruff` and `mypy` |
| `make test` | Run the test suite with coverage |
| `make audit` | Run dependency security checks with `pip-audit` |
| `make precommit` | Install git pre-commit hooks |
| `make coverage` | Generate `coverage.xml` |
| `make format` | Format code with `ruff` |

To run a specific phase experiment:

```bash
make phase3   # text correction-loop effectiveness
make phase4   # vision-critique effectiveness
make phase6   # rubric calibration
make phase7   # text routing
make phase8   # vision routing
```

---

## Testing & quality

- Unit and integration tests are in `tests/` (200+ tests)
- `pytest` is configured with coverage support (`--cov=app`)
- `ruff` enforces linting and formatting rules
- `mypy` performs static typing checks
- `pre-commit` ensures checks run before commits
- `pip-audit` flags high-severity dependency issues
- Coverage gate: CI fails if overall coverage drops below 70%

---

## Architecture

```
app/
├── main.py              # FastAPI entrypoints (run, compare, evaluation, rubric, mem0)
├── gateway.py           # Async model gateway (mock + live, structured output, vision)
├── agent_loop.py        # Correction loop (draft → critique → revise)
├── rubric.py            # Rubric scoring + Bradley-Terry weight updates
├── mem0.py              # Mem0 compression pair tracking + validation
├── preference_store.py  # Preference persistence (PostgreSQL + JSONL fallback)
├── db.py                # Database initialization
├── config.py            # Settings (pydantic-settings)
├── routing.py           # AdaptiveRouter with YAML-based escalation rules
├── schemas.py           # Pydantic v2 schemas
├── prompts.py           # Prompt registry
├── budget.py            # Cost budget tracking
├── evaluation_harness.py # Statistical evaluation suite
├── logging_config.py    # structlog configuration
└── templates/           # Comparison UI HTML

config/
└── routing_rules.yaml   # External model routing rules

data/
├── briefs/              # Phase 1 brief set
├── images/              # Reference images for VLM experiments
├── traces/              # Stored correction-loop traces
├── preferences.jsonl    # Human preference pairs
├── dpo_dataset.jsonl    # Exported DPO dataset
├── rubric_weights.json  # Current rubric weights
└── rubric_weight_history.jsonl  # Weight evolution over time

training/
├── export_dpo_dataset.py  # DPO dataset exporter
├── dpo_train.py           # DPO training wrapper (TRL)
├── run_dpo.py             # Quick dry-run entry point
├── generate_fake_preferences.py  # Fake data generator
└── migrate_preferences_to_db.py  # JSONL → PostgreSQL migration

evals/
└── inspect_preference_task.py  # Inspect AI adapter

experiments/
├── phase2_grounding.py           # VLM grounding experiment
├── phase3_correction_effectiveness.py  # Text correction study
├── phase4_vision_effectiveness.py      # Vision critique study
├── phase6_calibration.py             # Rubric calibration
├── phase7_routing.py                 # Text routing experiment
└── phase8_vision_routing.py          # Vision routing experiment

scripts/
├── generate_comparison_pairs.py  # Phase 5 pair generator
└── run_eval_regression.py        # Eval regression gate

tests/                             # 200+ unit and integration tests
prompts/                           # Versioned prompt templates
docs/                              # Architecture, CI/CD, and evaluation guides
```

For architecture and CI documentation, see `docs/PROJECT_ARCHITECTURE.md` and `docs/CI_CD_GUIDE.md`.

---

## Repository layout

```
app/                FastAPI app, gateway, rubric, and services
config/             routing and runtime configuration
data/               briefs, preferences, images, traces, and generated state
docs/               architecture, CI/CD, and evaluation guides
evals/              Inspect AI eval adapter
experiments/        evaluation and grounding experiment scripts
scripts/            utility scripts for pair generation and regression gates
training/           DPO export, training wrapper, and migration
tests/              unit and integration test coverage
prompts/            versioned prompt templates
.github/            CI/CD workflow definitions (ci, sonarcloud, codeql, gitleaks)
```

---

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for the full strategic plan with all 12 phases (0–11), implementation history, research updates, and the masterpiece checklist.

---

## License

This project is released under the [MIT](LICENSE) license.
