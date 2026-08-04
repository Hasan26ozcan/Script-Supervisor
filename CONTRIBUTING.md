# Contributing to Creative Harness

Thank you for your interest in contributing! This document covers the
development workflow, coding standards, testing requirements, and pull
request process.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Running Experiments](#running-experiments)
- [Data & Privacy](#data--privacy)

---

## Code of Conduct

This project is intended to be a welcoming and inclusive space for everyone.
Be respectful in all interactions — code reviews, issues, and discussions
alike.

---

## Getting Started

### Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.11 |
| Git | 2.30+ |
| Docker | 20.10+ (for PostgreSQL tests) |
| pip | 23.0+ |

### Clone and install

```bash
git clone https://github.com/Hasan26ozcan/Script-Supervisor.git
cd Script-Supervisor

# Create a virtual environment (recommended)
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install with dev dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Install pre-commit hooks
make precommit
```

---

## Development Workflow

1. **Create a branch** for your feature or fix:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Run tests** as you work:

   ```bash
   make test       # full suite with coverage
   pytest tests/test_file.py -v   # specific file
   ```

3. **Run linting** before committing:

   ```bash
   make lint       # ruff + mypy
   make format     # auto-format
   ```

4. **Commit** with a clear, descriptive message:

   ```bash
   git add .
   git commit -m "Fix: resolve memory leak in preference store

   The PreferenceStore was accumulating fallback records on every
   add() call even when the database write succeeded, causing
   unbounded memory growth in long-running sessions.

   Fixes #123"
   ```

5. **Push and open a PR:**

   ```bash
   git push origin feature/your-feature-name
   ```

   Then open a pull request on GitHub.

---

## Coding Standards

### Linting

The project uses **ruff** for linting and formatting, and **mypy** for static
type checking:

| Tool | Rules | Command |
|---|---|---|
| ruff (lint) | E, F, I, UP, B | `ruff check app tests` |
| ruff (format) | Black-compatible | `ruff format app tests` |
| mypy (types) | `python_version = "3.11"` | `mypy app` |

### Imports

- Imports are sorted alphabetically within groups using `isort` rules
- Standard library, then third-party, then local application (separated by blank lines)
- No wildcard imports

### Type annotations

- All function signatures must include type annotations
- Use `from __future__ import annotations` for forward references
- Pydantic v2 models are preferred for data structures

### Documentation

- Module-level docstrings are required for all modules
- Public functions and classes should have docstrings
- Use Google-style docstrings

### Style

- Line length: 100 characters
- Target Python: 3.11+ (no compatibility shims for older versions)

---

## Testing

### Running tests

```bash
# Run the full suite with coverage (70% minimum gate)
make test

# Run a specific test file
pytest tests/test_rubric.py -v

# Run with verbose output and coverage details
pytest tests/ -v --cov=app --cov-report=term-missing

# Run only unit tests (faster)
pytest tests/test_gateway.py tests/test_rubric.py tests/test_budget.py -v
```

### Test categories

The test suite is organized by component:

| Directory | Tests | What's Covered |
|---|---|---|
| `tests/test_*_loop*.py` | 2 files | Correction loop logic, early stopping |
| `tests/test_gateway.py` | 1 file | Gateway mock + live paths, structured output |
| `tests/test_rubric.py` | 1 file | Rubric scoring, weight updates, parsing |
| `tests/test_mem0*.py` | 2 files | Mem0 store, entry validation, staleness |
| `tests/test_preference_store.py` | 1 file | PostgreSQL + JSONL persistence |
| `tests/test_routing.py` | 1 file | YAML routing rules, escalation logic |
| `tests/test_*.py` | 10+ files | Schemas, budget, prompts, DPO export, phases |

### Test fixtures

| Fixture | Description |
|---|---|
| `MockGateway` | Gateway returning synthetic, deterministic responses |
| `TestDatabase` | SQLite in-memory database for preference storage |
| `FakePreferences` | 20-sample synthetic preference dataset |
| `MockGatewayFactory` | Factory for gateways with different configurations |

### Integration tests with PostgreSQL

When running tests locally with PostgreSQL:

```bash
docker compose up -d db
HARNESS_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness" \
  HARNESS_MOCK_MODE=1 pytest tests/ -v --cov=app
```

### Coverage gate

CI enforces a **70% coverage** minimum:

```bash
pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=70
```

### Adding tests

- Place test files in `tests/` with the `test_` prefix
- Use the existing fixtures and patterns
- Each public function should be tested
- Mock external API calls — never hit the real Anthropic or Groq API in tests

---

## Pull Request Process

1. **Ensure all tests pass:**

   ```bash
   make lint && make test
   ```

2. **Review your diff:** Ensure commits are clean and focused. Squash
   exploratory commits before opening the PR.

3. **Update documentation** if your changes affect:
   - API endpoints
   - Configuration variables
   - Architecture or data flow
   - Environment variables

4. **PR description should include:**
   - What changed and why
   - How to test the change
   - Any breaking changes (with migration path)
   - Related issue numbers (e.g., `Fixes #123`)

5. **Review process:**
   - At least one approval from a project maintainer
   - All CI checks must pass (lint, security, tests, eval regression)
   - No unresolved threads in the review

---

## Running Experiments

The project includes 11 phase experiment scripts. Each is designed to run
in mock mode for local testing:

```bash
make phase2    # VLM grounding proof
make phase3    # Text correction-loop effectiveness
make phase4    # Vision-critique effectiveness
make phase5    # Generate comparison pairs for the UI
make phase6    # Rubric calibration
make phase7    # Cost-aware text routing
make phase8    # Cost-aware vision routing
make phase9    # DPO dataset export
make phase10   # DPO dry-run training
make phase11   # Migrate preferences to database
```

For live experiments (requires API keys):

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your-key-here"
python experiments/phase3_correction_effectiveness.py
```

Results are saved to `data/results/` as JSON, with markdown reports generated
for Phases 3, 4, 6, 7, and 8.

---

## Data & Privacy

- **Reference images:** Source from CC0-licensed stock photos (Unsplash,
  Pexels) or your own photos. Avoid copyrighted material in a public repo.
- **Brief content:** May contain unpublished creative material — use `.env`
  files (never committed) for API keys
- **Secrets:** Never commit API keys, passwords, or tokens. The repo includes
  `gitleaks` and `detect-secrets` pre-commit hooks for this
- **Langfuse:** Recommended for self-hosted observability when brief content
  is sensitive — it is MIT-licensed and can run entirely on-prem

---

## Reporting Issues

When filing an issue, include:

1. **Environment:** Python version, OS, installed via `pip install -e ".[dev]"`
2. **Steps to reproduce:** Minimal, reproducible example
3. **Expected behavior:** What you thought should happen
4. **Actual behavior:** What actually happened (include full error output)
5. **Mock mode:** Does the issue reproduce in mock mode? (`HARNESS_MOCK_MODE=1`)

---

## Questions?

- Open an [issue](https://github.com/Hasan26ozcan/Script-Supervisor/issues)
  for bugs or feature requests
- Check the [`docs/`](docs/) directory for architecture and methodology
- Review the [ROADMAP.md](ROADMAP.md) for project context
