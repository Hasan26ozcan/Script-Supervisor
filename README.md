# Creative Harness — Script Supervisor

[![CI](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/ci.yml/badge.svg)](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/codeql.yml/badge.svg)](https://github.com/Hasan26ozcan/Script-Supervisor/actions/workflows/codeql.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

A production-grade evaluation harness for creative shot-list generation. It delivers a complete, runnable system with a FastAPI backend, prompt-driven correction loops, human preference collection, DPO dataset export, Mem0-style compression-pair validation, PostgreSQL-backed persistence, and structured CI/CD.

The core research question the harness answers with measurable evidence: **can a structured correction loop, calibrated rubric, and vision-aware critique outperform a single-pass generation strategy while remaining cost-effective and auditable?**

### Architecture at a Glance

```mermaid
graph TD
    A["🎨 Presentation Layer<br/>FastAPI REST API<br/>Comparison UI (HTML)<br/>Inspect AI CLI"] --> B["⚙️ Orchestration Layer<br/>CorrectionLoop<br/>AdaptiveRouter<br/>EvaluationHarness"]
    B --> C["🔧 Service Layer<br/>ModelGateway<br/>Rubric<br/>Mem0<br/>PreferenceStore<br/>Budget"]
    C --> D["💾 Persistence Layer<br/>PostgreSQL (primary)<br/>JSONL (offline fallback)"]
    D --> E["🏗️ Infrastructure Layer<br/>Docker<br/>Postgres 16<br/>Langfuse (optional)<br/>GitHub Actions"]
```

The system is organized into five architectural layers, each with a clear responsibility boundary:

1. **Presentation** — REST API endpoints, comparison UI, and Inspect AI CLI
2. **Orchestration** — Correction loop, adaptive routing, and statistical evaluation
3. **Service** — Model gateway, rubric scoring, Mem0 tracking, preference storage, and budget management
4. **Persistence** — PostgreSQL as the primary backend with JSONL as an offline fallback
5. **Infrastructure** — Docker, Postgres 16, optional Langfuse observability, and GitHub Actions CI/CD

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Testing & Quality](#testing--quality)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Area | What it does |
|---|---|
| **Correction loop** | Draft → critique → revise, with cost-aware early stopping and plateau detection |
| **Vision-grounded critique** | Optional VLM critique when reference images are attached |
| **Rubric scoring** | Weighted criteria with Bradley-Terry MLE updates from human preferences |
| **Preference collection** | Pairwise comparison API (`/compare`) with persistent storage |
| **Mem0 compression pairs** | Stale detection, validation, and replacement for compression pairs |
| **DPO dataset export** | Convert recorded preferences into TRL-compatible training data |
| **DPO training** | Optional TRL `DPOTrainer` wrapper (GPU + API keys required) |
| **Adaptive routing** | YAML-driven model escalation rules with cost-aware model selection |
| **Eval harness** | Bootstrap CIs, binomial significance, Bradley-Terry fit, Cohen's κ |
| **Inspect AI adapter** | Optional integration with the AISI Inspect framework for model-graded runs |
| **PostgreSQL persistence** | Primary backend with JSONL fallback for offline use |
| **Observability** | Optional Langfuse tracing for every gateway call |
| **Cost tracking** | Per-run and per-day budget enforcement with cost-per-quality metrics |

---

## Quick Start

### Prerequisites

- Python 3.11 or newer
- Git
- Docker (optional, for PostgreSQL and full-stack deployment)

### Installation

```bash
git clone https://github.com/Hasan26ozcan/Script-Supervisor.git
cd Script-Supervisor
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### Run locally (mock mode)

```bash
HARNESS_MOCK_MODE=1 uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API.

### Run the evaluation harness

```bash
python -m training.generate_fake_preferences
python -m app.evaluation_harness
```

This generates `docs/evaluation/evaluation_report.{md,html}`, `docs/evaluation/metrics.json`, and charts from a 20-sample demo dataset. See [HARNESS_NOTES](docs/evaluation/HARNESS_NOTES.md) for methodology and limitations.

### Run with a real model

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your_key"
uvicorn app.main:app --reload
```

---

## Usage

### Correction loop

```python
from app.agent_loop import CorrectionLoop

loop = CorrectionLoop()
trace = await loop.run("A cinematic wide of a desert at golden hour...")
print(trace.final_output)
print(f"Cost: ${trace.total_cost_usd:.4f}")
```

### Pairwise comparison

```bash
curl -X POST http://127.0.0.1:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "A dramatic opening shot",
    "candidate_a": "Wide angle, slow dolly in...",
    "candidate_b": "Close-up, handheld shake...",
    "winner": "a"
  }'
```

### Evaluation suite

```bash
curl -X POST http://127.0.0.1:8000/evaluation/run
```

### Inspect AI (model-graded eval)

```bash
pip install inspect-ai
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view
```

---

## Project Structure

```
Script-Supervisor/
├── app/                     # FastAPI application and core logic
│   ├── main.py              # API entrypoints
│   ├── agent_loop.py        # Correction loop (draft → critique → revise)
│   ├── gateway.py           # Async model gateway (mock + live)
│   ├── rubric.py            # Rubric scoring + Bradley-Terry updates
│   ├── mem0.py              # Compression pair tracking + validation
│   ├── preference_store.py  # Preference persistence (PostgreSQL + JSONL)
│   ├── db.py                # SQLAlchemy models and session management
│   ├── routing.py           # AdaptiveRouter with YAML escalation rules
│   ├── config.py            # Pydantic-settings configuration
│   ├── schemas.py           # Pydantic v2 schemas
│   ├── prompts.py           # Prompt registry
│   ├── budget.py            # Cost budget tracking
│   ├── evaluation_harness.py# Statistical evaluation suite
│   ├── logging_config.py    # structlog configuration
│   └── templates/           # Comparison UI HTML
├── config/
│   └── routing_rules.yaml   # External model routing rules
├── data/                    # Briefs, preferences, images, traces, artifacts
├── docs/                    # Architecture, CI/CD, and evaluation guides
├── evals/                   # Inspect AI adapter
├── experiments/             # Reproducible experiment scripts
├── prompts/                 # Versioned prompt templates
├── scripts/                 # Utility scripts (pair generation, regression)
├── training/                # DPO export, training wrapper, migration
├── tests/                   # Unit and integration tests (200+)
├── .github/workflows/       # CI/CD (lint, test, security, SonarCloud)
├── docker-compose.yml       # Full-stack deployment (app + Postgres + Langfuse)
├── Dockerfile               # Container image
├── Makefile                 # Developer command shortcuts
├── pyproject.toml           # Project metadata and dependencies
└── README.md                # This file
```

---

## Configuration

All settings use the `HARNESS_` prefix, managed by `pydantic-settings`. A `.env` file works out of the box.

| Variable | Default | Description |
|---|---|---|
| `HARNESS_MOCK_MODE` | `1` | Mock responses; set `0` for live API calls |
| `HARNESS_ANTHROPIC_API_KEY` | — | Required when mock=0 |
| `HARNESS_PROVIDER` | `anthropic` | `anthropic` or `groq` |
| `HARNESS_DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness` | PostgreSQL connection string |
| `HARNESS_MAX_TURNS` | `3` | Max correction-loop iterations |
| `HARNESS_THRESHOLD` | `8.0` | Quality score to stop the loop |
| `HARNESS_RUN_BUDGET_USD` | — | Per-run cost cap |
| `HARNESS_DAILY_BUDGET_USD` | — | Daily cost cap |
| `HARNESS_LANGFUSE_ENABLED` | `false` | Enable Langfuse trace export |

---

## Testing & Quality

- **200+ tests** in `tests/` covering unit and integration scenarios
- `pytest` with coverage reporting (`--cov=app`, gate at 70%)
- `ruff` for linting and formatting
- `mypy` for static type checking
- `pre-commit` hooks enforce checks before every commit
- `pip-audit` flags high-severity dependency vulnerabilities
- `bandit` runs security scanning in CI

```bash
make test      # run the full test suite with coverage
make lint      # run ruff + mypy
make audit     # run pip-audit dependency check
make precommit # install git hooks
```

---

## CI/CD

The pipeline runs on every push and pull request to `main`:

| Job | What it does |
|---|---|
| **Lint** | `ruff check`, `ruff format --check`, `mypy` |
| **Security (Bandit)** | Static security analysis of `app/` |
| **Test** | `pytest` with coverage, PostgreSQL service container, Codecov upload |
| **Eval Regression** | Runs the golden-qa regression suite, uploads artifacts |
| **SonarCloud** | Code quality and coverage analysis |

See [docs/CI_CD_GUIDE.md](docs/CI_CD_GUIDE.md) for full details.

---

## Deployment

### Local development

```bash
HARNESS_MOCK_MODE=1 uvicorn app.main:app --reload
```

### Docker Compose (full stack)

```bash
docker compose up -d          # app + PostgreSQL
docker compose --profile observability up -d   # adds Langfuse
```

The default compose profile includes the app and a PostgreSQL 16 container. The optional `observability` profile adds Langfuse for trace visualization.

### Environment variables for Docker

Set these in `.env` or GitHub Actions secrets:

- `HARNESS_MOCK_MODE`
- `HARNESS_ANTHROPIC_API_KEY`
- `HARNESS_GROQ_API_KEY`
- `HARNESS_DATABASE_URL`
- `SONAR_PROJECT_KEY`, `SONAR_ORGANIZATION`, `SONAR_TOKEN`

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Install dev dependencies: `pip install -e .[dev]`
4. Install pre-commit hooks: `make precommit`
5. Make your changes and run `make lint && make test`
6. Commit with a descriptive message
7. Open a pull request

### Running specific phases

```bash
make phase3   # text correction-loop effectiveness
make phase4   # vision-critique effectiveness
make phase6   # rubric calibration
make phase7   # text routing
make phase8   # vision routing
```

---

## License

This project is released under the [MIT](LICENSE) license.

---

<!-- TODO: update after Trivy workflow fix is pushed -->
