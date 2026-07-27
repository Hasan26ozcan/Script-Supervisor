# Phase 11 — Architecture Hardening Pass

This phase adds optional but meaningful architecture hardening to the
Creative Harness, improving durability and credibility without changing
core experimental claims.

## What was added

- `app/db.py`
  - `PreferenceDatabase`: a lightweight SQLite-backed store for preference
    data, including schema creation and JSONL migration.
- `training/migrate_preferences_to_db.py`
  - Migrates `data/preferences.jsonl` into `data/preferences.db`.
- `app/budget.py`
  - `CostBudget` and `BudgetExceeded` for explicit per-run and daily cost
    limits.
- `app/config.py`
  - New settings for `database_path`, `run_budget_usd`, and `daily_budget_usd`.

## Why this matters

Phase 11 is not about new models, it's about stepping up the project
from a research prototype to a credible, hardened architecture.
This foundation supports:

- database-backed preference storage for concurrent raters and later
  analytics,
- explicit cost budgets to keep real API spending under control,
- a cleaner separation between experiment wiring and durable data.

## Notes

These additions are intended as a hardening pass, not a rewrite:
existing JSONL support remains intact, and the new SQLite path is
additive.
