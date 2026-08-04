# CI/CD and Quality Assurance Guide

This repository includes a full production-grade CI/CD pipeline designed for
code quality, security, and reliability. This guide documents every workflow,
the local developer workflow, and how to troubleshoot common issues.

---

## Pipeline Overview

The CI/CD pipeline runs on every push and pull request to `main`. All jobs
run in parallel on GitHub Actions runners — no job blocks another unless
explicitly configured with `needs:`.

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | push, PR | Lint, type checking, tests, coverage, eval regression |
| `trivy.yml` | push, PR | Filesystem + container image vulnerability scanning |
| `codeql.yml` | push, PR, weekly | Semantic code analysis for security issues |
| `sonarcloud.yml` | push, PR | Code quality and coverage analysis |
| `gitleaks.yml` | push, PR | Secret scanning |

```mermaid
graph TD
    TRIGGER["push / pull_request to main"]
    LINT["Lint - ruff check + format check<br/>mypy type checking"]
    SECURITY["Security - bandit static scan<br/>pip-audit dependency check"]
    TEST["Test - pytest with coverage<br/>PostgreSQL service container<br/>70% coverage gate"]
    EVAL_REG["Eval Regression - golden-qa dataset<br/>artifact upload"]
    SONAR["SonarCloud - code quality + coverage"]
    CODEQL["CodeQL - semantic analysis"]
    TRIVY_FS["Trivy Filesystem - vulnerability scan"]
    TRIVY_IMG["Trivy Docker Image - vulnerability scan"]
    GITGUARD["Gitleaks - secret scanning"]

    TRIGGER --> LINT
    TRIGGER --> SECURITY
    TRIGGER --> TEST
    TRIGGER --> EVAL_REG
    TRIGGER --> SONAR
    TRIGGER --> TRIVY_FS
    TRIGGER --> GITGUARD
    EVAL_REG --> TRIVY_IMG
    CODEQL -.->|"weekly cron"| CODEQL

    LINT --> GATE{"All jobs pass?"}
    SECURITY --> GATE
    TEST --> GATE
    EVAL_REG --> GATE
    SONAR --> GATE
    TRIVY_FS --> GATE
    GITGUARD --> GATE
    TRIVY_IMG --> GATE

    GATE -->|"success"| MERGE["Merge to main"]
    GATE -->|"failure"| BLOCK["Block PR"]
```

---

## Workflow Details

### `ci.yml` — Continuous Integration

**Jobs:** `lint`, `security-bandit`, `test`, `eval-regression`

**Steps:**

1. **Checkout** — `actions/checkout@v4` with full history
2. **Setup Python** — Python 3.11 (matches runtime)
3. **Install dependencies** — `pip install -e ".[dev]"` (editable with dev extras)
4. **Lint** (ruff):
   - `ruff check app tests` — lint check
   - `ruff format --check app tests` — format check
   - `mypy app` — static type checking
5. **Security** (bandit):
   - `bandit -r app/ -ll -f screen` — AST-based security scan (low and above)
6. **Test**:
   - PostgreSQL 16 service container with health checks
   - `pytest tests/ -q --tb=short --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=70`
   - Uploads `coverage.xml` to Codecov (non-blocking if upload fails)
7. **Eval Regression** (depends on `test` passing):
   - Runs `python -m scripts.run_eval_regression --dataset eval/golden_qa.jsonl --threshold-config eval/thresholds.yaml`
   - Uploads `docs/evaluation/` as a downloadable artifact

**Test environment variables:**
```yaml
HARNESS_MOCK_MODE: 1
HARNESS_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness
```

### `trivy.yml` — Container & Filesystem Scanning

**Jobs:** `trivy-filesystem`, `trivy-docker`

**Filesystem scan:**
- Scans the repository source code for known vulnerabilities
- Reports CRITICAL and HIGH severity findings as SARIF to GitHub Security tab
- Fails the build on any unfixed CRITICAL/HIGH vulnerability

**Docker image scan:**
- Builds the Docker image from the `Dockerfile`
- Scans the resulting image for vulnerabilities
- Reports findings as SARIF to GitHub Security tab

### `codeql.yml` — Semantic Analysis

**Trigger:** push, PR, and weekly (Monday 6 AM UTC via cron)

- Analyzes Python source code for security vulnerabilities using CodeQL's
  semantic analysis engine
- Writes results to the GitHub Security tab
- Weekly scheduled runs catch vulnerabilities introduced over time

### `sonarcloud.yml` — Code Quality

**Jobs:** `sonarqube`

- Runs `pytest` with coverage (note: coverage gate is set to 0 here — the
  real gate is in `ci.yml` at 70%)
- Uploads results to SonarCloud for code quality metrics, code smells,
  security hotspots, and coverage trends

**Required secrets:**
| Secret | Description |
|---|---|
| `SONAR_TOKEN` | Authentication token for SonarCloud |

### `gitleaks.yml` — Secret Scanning

- Scans commit diffs for accidentally committed secrets (API keys, passwords,
  tokens)
- Fails the build if any secrets are detected

---

## Local Developer Workflow

### Prerequisites

- Python 3.11+
- Git
- Docker (for integration tests with PostgreSQL)
- Pre-commit (optional, for git hooks)

### Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Install pre-commit hooks

```bash
make precommit
# or manually:
pre-commit install
```

### Run checks locally

```bash
make lint       # ruff check + format check + mypy
make test       # pytest with coverage
make audit      # pip-audit dependency check
make format     # auto-format code with ruff
```

### Pre-commit hooks

The repository uses pre-commit to enforce checks before every commit:

| Hook | Purpose |
|---|---|
| `ruff` | Linting (E, F, I, UP, B rules) |
| `ruff format` | Code formatting |
| `mypy` | Static type checking |
| `isort` | Import sorting |
| `end-of-file-fixer` | Ensure files end with a newline |
| `trailing-whitespace` | Strip trailing whitespace |
| `check-yaml` | Validate YAML files |
| `check-added-large-files` | Prevent large files in commits |
| `detect-secrets` | Detect accidentally committed secrets |

Run all hooks manually:

```bash
pre-commit run --all-files
```

---

## Test Suite

### Running tests

```bash
# Run all tests with coverage
make test

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_rubric.py -v

# Run with live PostgreSQL (integration tests)
HARNESS_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness" \
  HARNESS_MOCK_MODE=1 pytest tests/ -v --cov=app

# Run eval regression (CI gate)
python -m scripts.run_eval_regression \
  --dataset eval/golden_qa.jsonl \
  --threshold-config eval/thresholds.yaml
```

### Test categories

| Category | Files | Purpose |
|---|---|---|
| **Unit tests** | `test_rubric.py`, `test_gateway.py`, `test_budget.py`, `test_schemas.py` | Individual component behavior |
| **Integration tests** | `test_agent_loop.py`, `test_main.py`, `test_preference_store.py` | Multi-component integration |
| **Phase tests** | `test_phase1.py`, `test_phase3.py`, `test_phase4.py`, `test_phase6.py` | Phase-specific validation |
| **Eval regression** | `test_evaluation_harness.py`, `test_modern_evaluation_harness.py` | Statistical pipeline correctness |

### Test fixtures

| Fixture | Description |
|---|---|
| `MockGateway` | Gateway returning synthetic responses |
| `TestDatabase` | SQLite in-memory database for preference storage |
| `FakePreferences` | 20-sample synthetic preference dataset |

### Coverage

The project enforces a **70% coverage gate** in CI:

```bash
pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=70
```

Coverage is uploaded to both Codecov (via `ci.yml`) and SonarCloud (via
`sonarcloud.yml`).

---

## Dependency Security

### pip-audit

`pip-audit` scans installed dependencies against the Python Package Authority's
vulnerability database:

```bash
# Local execution
python -m pip_audit --fail-on high

# Or via Makefile
make audit
```

Fails on any vulnerability rated HIGH or above.

### Bandit

Bandit performs static analysis of Python source code for common security
issues:

```bash
bandit -r app/ -ll -f screen
```

Scans `app/` only (not tests or training), reporting issues at LOW severity
and above (`-ll` = level low).

### Trivy

Trivy scans both the filesystem and the Docker image for OS-level and
application vulnerabilities:

```bash
# Filesystem scan (filesystem scope, CRITICAL/HIGH severity)
trivy fs --scanners vuln --severity CRITICAL,HIGH .

# Docker image scan
trivy image --scanners vuln --severity CRITICAL,HIGH script-supervisor:latest
```

---

## Environment Variables for CI

All CI secrets should be stored as GitHub Actions secrets (never in code):

| Secret | Used In | Description |
|---|---|---|
| `HARNESS_ANTHROPIC_API_KEY` | `ci.yml` | Anthropic API key (for live tests when not in mock mode) |
| `HARNESS_GROQ_API_KEY` | `ci.yml` | Groq API key |
| `SONAR_TOKEN` | `sonarcloud.yml` | SonarCloud authentication token |
| `CODECOV_TOKEN` | `ci.yml` | Codecov upload token (if private repo) |

Non-secret environment variables are set directly in the workflow YAML:

| Variable | Value in CI |
|---|---|
| `HARNESS_MOCK_MODE` | `1` |
| `HARNESS_DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness` |

---

## Troubleshooting

### Tests fail with "database backend unavailable"

The evaluation harness falls back to JSONL when PostgreSQL is unreachable.
To use real Postgres:

```bash
docker compose up -d db
export HARNESS_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness"
pytest tests/ --cov=app
```

Verify the write landed in Postgres (not a fallback):
```bash
docker compose exec db psql -U postgres -d creative_harness -c "SELECT count(*) FROM preferences;"
```

### MyPy type errors

The project targets Python 3.11. Ensure your environment matches:

```bash
python --version  # should be 3.11+
python -m pip install -e ".[dev]"
mypy app
```

If you see import errors for optional dependencies (e.g., `inspect_ai`), they
are expected — those packages are not installed by default.

### Coverage gate fails locally but tests pass

Ensure you're running with the coverage flag:

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

### Pre-commit hooks block commits

```bash
# Auto-fix what you can
pre-commit run --all-files --hook-stage manual

# Skip hooks for a single commit (not recommended)
git commit -m "message" --no-verify
```
