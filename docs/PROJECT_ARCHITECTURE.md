# Project Architecture

## Overview

The Creative Harness is a production-quality AI evaluation and preference-collection system for shot list generation. It combines:

- FastAPI as the service layer
- Pydantic v2 models for schema validation
- Async LLM gateway abstraction for live and mock providers
- Structured prompt registry and versioned prompt templates
- Rubric calibration with Bradley-Terry-style weight updates
- Mem0-style compression pair tracking and stale replacement
- DPO dataset export and optional TRL DPO training pipeline
- External routing rules exposed as YAML for model escalation
- PostgreSQL as the primary backend for preference persistence and evaluation-run
  records (SQLAlchemy models in `app/db.py`), with JSONL as an offline/local
  fallback only -- see `docker-compose.yml`'s `db` service
- Two complementary evaluation layers: a statistically-grounded offline harness
  (`app/evaluation_harness.py`: bootstrap CIs, significance testing, Bradley-Terry
  fit, judge/human agreement) and an Inspect AI adapter
  (`evals/inspect_preference_task.py`) for real model-graded runs -- see
  `docs/evaluation/HARNESS_NOTES.md`
- CI/CD pipeline with linting, type checks, tests, coverage, dependency audit, and SonarCloud analysis

## Directory layout

- `app/`: core FastAPI app and backend logic
- `config/`: runtime routing and config assets
- `data/`: persistent JSONL, images, briefs, and model artifacts
- `docs/`: operational guides, roadmap, CI/CD docs
- `experiments/`: reproducible experiment scripts for each phase
- `training/`: DPO dataset export and training wrapper
- `tests/`: unit and integration coverage
- `prompts/`: structured prompt templates for each stage

## Key components

### FastAPI app

- `app/main.py`: API entry points including `/compare`, `/mem0/*`, `/run`, and `/health`
- `app/agent_loop.py`: correction loop logic that produces drafts, critiques, and revisions
- `app/gateway.py`: model gateway abstraction with mock/live provider support
- `app/rubric.py`: evaluation rubric, scoring, and weight updates
- `app/mem0.py`: compression pair ingestion, validation, stale detection, and refresh
- `app/preference_store.py` and `app/db.py`: preference persistence options

### Evaluation

- `app/evaluation_harness.py`: offline-safe harness. Computes a bootstrap
  95% CI on human win rate, a binomial significance test vs. 50/50, a
  Bradley-Terry MLE fit of candidate strength, and agreement/Cohen's kappa
  between a heuristic offline judge and the recorded human label. Writes
  `docs/evaluation/{evaluation_report.md,evaluation_report.html,metrics.json}`
  and `docs/evaluation/charts/*.png`, and persists one run row to the SQL
  backend. See `docs/evaluation/HARNESS_NOTES.md` for full methodology and
  known limitations of the bundled 20-sample demo dataset.
- `evals/inspect_preference_task.py`: optional adapter into Inspect AI (UK
  AISI's framework, used by Anthropic/DeepMind), for real model-graded
  pairwise-preference runs with position-bias-checked scoring.

### Training

- `training/export_dpo_dataset.py`: build DPO JSONL dataset from recorded preferences
- `training/dpo_train.py`: mock-safe DPO wrapper with a real training stub

### Experimental validation

- `experiments/phase2_grounding.py`: VLM grounding test harness
- `experiments/phase3_correction_effectiveness.py`: correction loop evaluation
- `experiments/phase4_vision_effectiveness.py`: vision-critique performance analysis
- `experiments/phase6_calibration.py`: rubric calibration validation

## Deployment

The service is deployable via:
- `uvicorn app.main:app --reload` for local development
- `docker compose up` for containerized runtime

## Environment variables

Use `.env` or GitHub Actions secrets for:
- `HARNESS_MOCK_MODE`
- `HARNESS_ANTHROPIC_API_KEY`
- `HARNESS_GROQ_API_KEY`
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SONAR_TOKEN`

## Quality gates

- `ruff` linting + formatting
- `mypy` static typing
- `pytest` unit tests
- `pip-audit` dependency security
- `SonarCloud` code analysis
