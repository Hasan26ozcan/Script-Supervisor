# Creative Harness — Script Supervisor

A production-grade AI evaluation harness for creative shot list generation. This repository delivers a complete technical release with:

- a FastAPI backend and prompt-driven correction loop
- human preference collection and DPO dataset export
- Mem0-style compression pair validation and stale replacement
- PostgreSQL-backed preference storage and JSONL migration fallback
- structured CI/CD, pre-commit hooks, type checking, linting, coverage, and dependency security

## Project vision

This project is built to answer a concrete research question with measurable evidence: can a structured correction loop, calibrated rubric, and vision-aware critique outperform a simple single-pass generation strategy while remaining cost-effective and auditable?

It is designed as a polished, maintainable release rather than a prototype. The core system is production-ready for internal evaluation and experimentation; real model usage and training runs require API keys and optional GPU resources.

## Key features

- **End-to-end preference collection** via `/compare` and stored `PreferencePair` records
- **Mem0 compression pair tracking** with validation, stale detection, and replacement
- **DPO dataset export** from recorded preferences
- **Mock-safe training wrapper** with real TRL training support when the optional stack is installed
- **Async gateway abstraction** supporting mock and live providers
- **Routable escalation logic** through external YAML rules
- **PostgreSQL migration path** for preference persistence with JSONL fallback
- **CI/CD pipeline** covering lint, type checks, tests, coverage, dependency audit, and SonarCloud

## Current state

- Core API: complete
- Preference persistence: complete with PostgreSQL as the primary backend and JSONL fallback
- Evaluation harness: rewritten to use real statistical methodology (bootstrap
  confidence intervals, a binomial significance test, a Bradley-Terry fit, and
  judge/human agreement with Cohen's kappa) instead of a cosmetic accuracy
  number, and to actually run and persist charts/reports -- see
  `docs/evaluation/HARNESS_NOTES.md` for the full methodology, its honest
  limitations on the bundled 20-sample demo dataset, and exact commands to
  run it against real PostgreSQL
- Modern eval framework: an optional [Inspect AI](https://inspect.aisi.org.uk/)
  adapter (`evals/inspect_preference_task.py`) for real model-graded pairwise
  runs with position-bias-checked scoring, matching current industry practice
  at Anthropic/DeepMind/UK AISI
- Mem0 entry lifecycle: complete
- DPO export and training wrapper: implemented
- CI/CD and code quality automation: implemented
- Experimental analysis notes: present for Phases 2, 4, 6, 7, 8, 11
- Real model keys / GPU training: optional and controlled by environment

## Getting started

### Prerequisites

- Python 3.11 or newer
- Git
- Optional: Docker for containerized deployment

### Install

```bash
cd path/to/Script-Supervisor-main
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

This writes `docs/evaluation/evaluation_report.{md,html}`, `docs/evaluation/metrics.json`,
and `docs/evaluation/charts/*.png` from the 20-sample fake human judgment dataset,
and persists a run row to the configured SQL backend. Read
`docs/evaluation/HARNESS_NOTES.md` first -- it documents exactly what the
statistics can and can't tell you about this demo dataset, and how to run
the same pipeline against real PostgreSQL via Docker Compose.

For a real model-graded run via [Inspect AI](https://inspect.aisi.org.uk/):

```bash
pip install inspect-ai
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view
```

### Run with real model calls

Set environment variables and disable mock mode:

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your_key"
```

Then start the app as above.

## Development workflow

- `make install` — install the project and dev requirements
- `make lint` — run `ruff` and `mypy`
- `make test` — run the test suite with coverage
- `make audit` — run dependency security checks with `pip-audit`
- `make precommit` — install git pre-commit hooks
- `make coverage` — generate `coverage.xml`

To format code:

```bash
make format
```

## Testing and quality

- Unit and integration tests are in `tests/`
- `pytest` is configured with coverage support
- `ruff` enforces linting and formatting rules
- `mypy` performs static typing checks
- `pre-commit` ensures checks run before commits
- `pip-audit` flags high-severity dependency issues

## CI/CD

This repository includes GitHub Actions workflows for:

- `ci.yml` — lint, type checks, tests, coverage, and dependency audit on push and PR
- `sonarcloud.yml` — SonarCloud analysis for code quality and metrics

Configure SonarCloud secrets in the repository settings:
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SONAR_TOKEN`

## Architecture

The app is structured around:

- `app/main.py` — FastAPI application entrypoints
- `app/gateway.py` — model gateway with mock/live support
- `app/rubric.py` — rubric scoring and weight updates
- `app/mem0.py` — memory compression entry tracking and validation
- `app/preference_store.py` / `app/db.py` — preference persistence
- `training/export_dpo_dataset.py` — DPO export pipeline
- `training/dpo_train.py` — DPO training wrapper
- `prompts/` — versioned prompt templates
- `config/routing_rules.yaml` — external model routing rules

For architecture and CI documentation, see `docs/PROJECT_ARCHITECTURE.md` and `docs/CI_CD_GUIDE.md`.

## Repository layout

```
app/                FastAPI app, gateway, rubric, and services
config/             routing and runtime configuration files
data/               briefs, preferences, images, and generated state
docs/               architecture, CI/CD, and operational guides
experiments/        evaluation and grounding experiment scripts
training/           DPO export and training wrapper
tests/              unit and integration test coverage
prompts/            versioned prompt templates
.github/            CI/CD workflow definitions
```

## Roadmap

The project is now in a final release state for the harness and evaluation infrastructure:

- Core evaluation API: complete
- Preference ingestion and persistence: complete
- Mem0 lifecycle management: complete
- DPO data export and training wrapper: complete
- CI/CD and code quality pipeline: complete

Experimental work and deployment notes are captured in the roadmap and phase note documents.

See `ROADMAP.md` for the full strategic plan and implementation history.

## License

This project is released under the `MIT` license.
