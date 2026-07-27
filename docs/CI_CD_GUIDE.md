# CI/CD and Quality Assurance Guide

This repository includes a full CI/CD pipeline designed for production readiness.

## GitHub Actions

### `ci.yml`

Runs on push and pull request events targeting `main` or `master`.

Steps:
- checkout repository
- set up Python 3.11 and 3.12
- install editable package with `[dev]` extras
- run `ruff` and `mypy`
- run `pytest` with coverage
- run `pip-audit` with `--fail-on high`
- upload `coverage.xml`

### `sonarcloud.yml`

Runs SonarCloud analysis on push and PRs.

Requirements:
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SONAR_TOKEN`

## Local developer workflow

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Install pre-commit hooks:

```bash
make precommit
```

Run checks locally:

```bash
make lint
make test
make audit
```

## Pre-commit hooks

The repository uses:
- `ruff` for linting and formatting
- `mypy` for static typing
- `isort` for import sorting
- `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-added-large-files`

Run them manually with:

```bash
pre-commit run --all-files
```

## Coverage

Coverage is reported to `coverage.xml` on CI and locally using:

```bash
pytest --cov=app --cov-report=xml --cov-report=term-missing -q
```

## Dependency Security

A dependency audit runs automatically using `pip-audit`.

Local execution:

```bash
python -m pip_audit --fail-on high
```

## SonarCloud

This repo includes SonarCloud integration via GitHub Actions. Add these secrets to the repository settings:
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SONAR_TOKEN`

The workflow uses coverage data from `coverage.xml`.
