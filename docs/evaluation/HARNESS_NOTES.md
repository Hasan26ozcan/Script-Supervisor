# Evaluation Harness Notes

This file documents what the evaluation harness actually does, what it does
not do, why, and exactly how to execute it end-to-end with a real
PostgreSQL backend. It replaces the earlier version of this harness, which
self-described as "modern"/"frontier" in its docstring without actually
implementing any statistical rigor or integrating a real eval framework.

## What changed and why

The previous `app/evaluation_harness.py`:
- computed "accuracy" as `(wins_a + wins_b) / total`, which is ~1.0 for any
  dataset without ties and carries no information about quality
- hardcoded `"database_backend": "postgresql"` as a string literal instead
  of querying what actually served the write
- drew two static bar charts of raw counts
- had never actually been executed in this repo (`docs/evaluation/` did not
  exist before this change)

The current version:
- reports a **bootstrap 95% confidence interval** on the human win rate
  (percentile method, 5000 resamples, fixed seed for reproducibility)
- runs a **two-sided binomial significance test** against a 50/50 null
- fits a **Bradley-Terry model** (MLE via `scipy.optimize`) for relative
  candidate-template strength
- computes **agreement + Cohen's kappa** between a deterministic offline
  "judge" and the recorded human label -- the standard "model-graded vs
  human" check used in modern harnesses (see references below), clearly
  labeled as a heuristic stand-in, not a live LLM judge
- actually **writes and reads back** a row from the SQL backend via
  SQLAlchemy and reports which dialect really served it
- states its own limitations in the generated report rather than omitting
  them

## What it honestly cannot do with the bundled 20-sample dataset

`training/generate_fake_preferences.py` generates 20 rows using **two
fixed candidate templates** repeated across every brief, with **one rater
per item**. Running the real statistics on this data (see the reproducible
run below) correctly shows:

- win rate: 0.5, 95% CI [0.30, 0.70]
- binomial test vs 50/50: p = 1.0 (not significant)
- Bradley-Terry: no detectable template strength difference
- inter-rater reliability: **not computable** -- no item has more than one
  rating

This is the right answer, not a bug: the synthetic data alternates winner
by index parity, so there is no real signal in it. A harness that reported
a confident "94% accuracy" on this data (as the old cosmetic accuracy
metric implicitly did) would be misleading. If you want statistically
meaningful results, replace the demo data with real multi-rater human
judgments -- the code already supports it (`PreferencePair.rater`, the
kappa calculation, and the Bradley-Terry fit all generalize).

## Modern harness framework: Inspect AI

Industry practice as of mid-2026 (Anthropic, DeepMind, and the wider AISI
evals ecosystem) has converged on **Inspect AI**
(https://inspect.aisi.org.uk/, UK AI Security Institute, MIT-licensed) as
the standard open-source framework for reproducible LLM evaluation:
Dataset -> Task -> Solver -> Scorer, sandboxed execution, a log viewer UI,
and built-in statistical aggregation (accuracy/stderr/bootstrap). We chose
it over `lm-evaluation-harness`/OpenCompass (benchmark-focused, less suited
to custom pairwise-preference tasks), promptfoo/DeepEval (product-eval
tools, less standard for research-style reporting), and rolling a fully
custom pairwise-judge pipeline (loses the log viewer, statistical
aggregation, and reproducibility tooling for free).

`evals/inspect_preference_task.py` wires this project's preference dataset
into Inspect:

```bash
pip install inspect-ai
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view
```

It ships two tasks:
- `script_supervisor_preference_eval` -- single-ordering pairwise judge eval
- `script_supervisor_preference_eval_bias_checked` -- runs every pair in
  both A/B orderings, since pairwise LLM-judge comparisons are known to be
  sensitive to **position bias** (favoring whichever candidate is shown
  first). Treat a pair's model judgment as reliable only when both
  orderings agree; a single-ordering win rate should not be reported as
  ground truth on its own.

This is complementary to `app/evaluation_harness.py`, not a replacement:
the internal harness runs fully offline (no API key, no network -- useful
in CI and for anyone without model access), while the Inspect task
requires a real model call and produces Inspect's standard run logs.

## Running the full pipeline against real PostgreSQL

This repo's default config already points at PostgreSQL
(`app/config.py: database_url`), and `docker-compose.yml` already ships a
`db: postgres:16-alpine` service plus an optional Langfuse observability
stack. To execute end-to-end for real:

```bash
# 1. Bring up Postgres (and the app) via Docker
docker compose up -d db
docker compose ps                      # wait for db to report "healthy"

# 2. Install the project (with dev + eval extras) into a local venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install inspect-ai       # optional, for the Inspect AI task

# 3. Point the app at the containerized Postgres and disable mock mode
#    for real API calls if desired (mock mode works fine for the harness
#    itself, since it only needs the preference data, not live generation)
export HARNESS_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness"

# 4. Generate the 20-sample demo dataset and migrate it into Postgres
python -m training.generate_fake_preferences

# 5. Run the statistically-grounded harness -- writes
#    docs/evaluation/{evaluation_report.md,evaluation_report.html,metrics.json}
#    and docs/evaluation/charts/*.png, and persists one run row to Postgres
python -m app.evaluation_harness

# 6. Confirm the row actually landed in Postgres (not a fallback)
docker compose exec db psql -U postgres -d creative_harness -c \
  "SELECT run_id, suite_name, n_samples, accuracy FROM evaluation_runs ORDER BY created_at DESC LIMIT 5;"
docker compose exec db psql -U postgres -d creative_harness -c \
  "SELECT count(*) FROM preferences;"

# 7. Run the full test suite against the same Postgres instance
HARNESS_DATABASE_URL=$HARNESS_DATABASE_URL pytest -v

# 8. (Optional) modern harness run via Inspect AI -- requires a real model
#    key, e.g. ANTHROPIC_API_KEY, since this makes live model calls
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view

# 9. (Optional) bring up the full stack including the API server and the
#    Langfuse observability profile
docker compose --profile default up -d
docker compose --profile observability up -d   # adds Langfuse + its own Postgres

# 10. Tear down
docker compose down            # keep volumes (pgdata) for next run
docker compose down -v         # also wipe the Postgres volume
```

Step 6 is the important one: it proves the write went to real Postgres,
not the JSONL fallback that `app/preference_store.py` silently uses when
the database is unreachable.

## References
- Inspect AI: https://inspect.aisi.org.uk/
- Inspect Evals: https://github.com/UKGovernmentBEIS/inspect_evals
- UK AISI announcement: https://www.aisi.gov.uk/blog/inspect-evals
