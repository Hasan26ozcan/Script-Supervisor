# Phase 11 — Architecture Hardening Pass

This phase adds optional but meaningful architecture hardening to the Creative
Harness, improving durability and credibility without changing core
experimental claims.

---

## What Was Added

### 1. Database Layer (`app/db.py`)

`app/db.py` provides PostgreSQL/SQLite-backed preference storage:

- **`PreferencePairModel`** — SQLAlchemy model for the `preferences` table
  with fields: `pair_id`, `created_at`, `brief`, `prompt`, `candidate_a`,
  `candidate_b`, `winner`, `rater`, `notes`
- **`EvaluationRunModel`** — SQLAlchemy model for the `evaluation_runs` table
  tracking suite metadata and report paths
- **`create_sessionmaker()`** — Factory function returning a session-local
  pair and an engine, with `pool_pre_ping=True` for connection health
- **`init_db()`** — Convenience function to create all tables

**Why this matters:** Phase 5's UI can have concurrent raters — JSONL files
don't handle concurrent writes safely. A real database does.

### 2. Preference Migration (`training/migrate_preferences_to_db.py`)

Reads `data/preferences.jsonl` and migrates records into the SQL backend
(PostgreSQL or SQLite). This bridges the Phase 0–6 JSONL workflow with the
Phase 11 database workflow.

### 3. Cost Budgets (`app/budget.py`)

The `CostBudget` class provides explicit per-run and daily cost limits:

- `consume(amount)` — tracks spend, raises `BudgetExceeded` if limits exceeded
- `reset_run()` — resets per-run counter
- `reset_daily()` — resets daily counter (with date tracking)
- `to_dict()` — serializes state for logging

`BudgetExceeded` is raised **before** an experiment accidentally burns real
money — the gateway checks the budget before every model call.

### 4. Configuration Extensions (`app/config.py`)

New settings added:

| Variable | Description |
|---|---|
| `HARNESS_DATABASE_PATH` | SQLite database path (when PostgreSQL unavailable) |
| `HARNESS_RUN_BUDGET_USD` | Per-run cost budget in USD |
| `HARNESS_DAILY_BUDGET_USD` | Daily cost budget in USD |

### Design principle: additive, not replacement

These additions are intended as a hardening pass, not a rewrite:

- **JSONL support remains intact** — `PreferenceStore` writes to both
  PostgreSQL (primary) and JSONL (fallback), so existing workflows continue
  to work
- The database path is additive — it coexists with the JSONL workflow
- Cost budgets are optional — if `run_budget_usd` and `daily_budget_usd`
  are `None` (the default), no enforcement occurs

---

## Why This Matters

Phase 11 is not about new models, it's about stepping up the project from a
research prototype to a credible, hardened architecture. This foundation
supports:

- **Database-backed preference storage** for concurrent raters and later
  analytics — essential if the comparison UI gets real usage
- **Explicit cost budgets** to keep real API spending under control —
  prevents runaway costs during long-running experiments
- **Cleaner separation** between experiment wiring and durable data —
  preferences are data, not session state

---

## Future Work (Documented, Not Implemented)

These items were identified during the architecture review but left as
documented future work:

### Semantic Caching

Embedding-based caching (`sentence-transformers/all-MiniLM-L6-v2`) to cut
eval-run costs during Phases 3–8's repeated experiments. A cache key based on
the brief + shot list would prevent redundant re-processing of identical
inputs.

### Distributed Tracing

OpenTelemetry → Langfuse for a full trace tree (gateway → loop → API) instead
of structlog-only logging. This would provide:

- End-to-end trace visualization
- Per-span latency and cost attribution
- Distributed context propagation across services

Langfuse remains the strongest self-hosted, genuinely-free option with no
per-seat pricing — relevant if brief content is sensitive and should not
leave your infrastructure.

**Alternative:** Promptfoo is a lighter, CLI-only alternative if you do not
want to stand up a server just for Phase 7/8's regression-style comparisons.

### RL Beyond DPO

If there is real time left, TRL's `GRPOTrainer` with the rubric itself as
a reward model is the natural "bonus phase" — it would close the full
preference → rubric → reward model → RL loop that the research objectives
gesture at. This is a stretch goal, not a commitment.

---

## Files Changed

| File | Change |
|---|---|
| `app/db.py` | New — SQLAlchemy models + session management |
| `app/budget.py` | New — `CostBudget` class + `BudgetExceeded` exception |
| `training/migrate_preferences_to_db.py` | New — JSONL → database migration |
| `app/config.py` | Extended — `database_path`, `run_budget_usd`, `daily_budget_usd` |

---

## Reproducibility

```bash
# Migrate existing JSONL preferences to the database
python training/migrate_preferences_to_db.py
```
