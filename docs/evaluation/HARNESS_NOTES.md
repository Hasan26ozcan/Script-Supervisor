# Evaluation Harness — Methodology & Notes

This document details the statistical methodology, design decisions, and
known limitations of the Creative Harness evaluation harness. It is the
primary reference for understanding what the numbers in
`docs/evaluation/metrics.json`, `docs/evaluation/evaluation_report.md`, and
`docs/evaluation/charts/` actually mean.

---

## Overview

Creative Harness ships two complementary evaluation layers:

| Layer | Framework | Offline? | Requires API key? | File |
|---|---|---|---|---|
| **Offline harness** | Self-contained (numpy/scipy) | Yes | No | `app/evaluation_harness.py` |
| **Inspect AI adapter** | [Inspect AI](https://inspect.aisi.org.uk/) (UK AISI) | No (live model) | Yes | `evals/inspect_preference_task.py` |

The offline harness runs fully without network access — ideal for CI and
local development. The Inspect AI adapter performs real model-graded
pairwise-preference evaluation and produces Inspect's standard run logs with
a web UI for inspection.

---

## What the Harness Actually Does

This file replaces the earlier version of the evaluation harness, which
self-described as "modern"/"frontier" without implementing actual statistical
rigor. The current version:

1. **Bootstrap 95% confidence interval** on the human win rate — percentile
   method, 5000 resamples, fixed random seed (`RNG_SEED = 20260726`) for
   reproducibility
2. **Two-sided binomial significance test** against a 50/50 null hypothesis
   — `scipy.stats.binomtest`
3. **Bradley-Terry MLE fit** — maximum-likelihood estimation of relative
   candidate-template strength using `scipy.optimize.minimize` with BFGS
4. **Cohen's κ (kappa)** between a deterministic heuristic offline judge and
   the recorded human label — this is the standard "model-graded vs human"
   check used in modern LLM eval harnesses
5. **SQL backend verification** — actually writes a row to PostgreSQL (or
   SQLite fallback), reads it back, and reports which dialect really served
   the write — not a hardcoded string

---

## The Demo Dataset — What It Can and Cannot Support

`training/generate_fake_preferences.py` generates 20 rows using **two fixed
candidate templates** repeated across every brief, with **one rater per
item**. Running the real statistics on this data:

| Metric | Demo Dataset Value | Interpretation |
|---|---|---|
| Win rate | 0.500 (95% CI: 0.350–0.650) | No signal — synthetic data alternates winner by index parity |
| Binomial test vs 50/50 | p = 1.0 (not significant) | Cannot reject the null — correct for alternating data |
| Bradley-Terry P(A beats B) | 0.5 | No detectable template strength difference |
| Cohen's κ | 0.0 (not computable with 1 rater/item) | Inter-rater reliability impossible with single rater |

**This is the correct answer, not a bug.** The synthetic data alternates the
winner by index parity (odd → A wins, even → B wins), so there is no real
signal in it. A harness that reported "94% accuracy" on this data would be
misleading.

### To get statistically meaningful results:

Replace the demo data with real multi-rater human judgments. The code already
supports this:

- `PreferencePair.rater` — records which rater made each judgment
- The Cohen's κ calculation generalizes to multiple raters
- The Bradley-Terry fit handles any number of pairwise outcomes

---

## What the Heuristic Judge Is

The `heuristic_judge_*` metrics come from a **deterministic offline text-feature
judge** — not a live LLM-graded judge. It uses simple features:

- **Sentence count** — longer, more detailed outputs tend to win
- **Action verb hits** — count of cinematic action verbs (dolly, pan, zoom,
  cut, etc.)

This exists so the agreement-with-automated-judge metric has something real to
compute in mock/offline mode. When `HARNESS_MOCK_MODE=0` and real preference
data is collected with >= 2 raters per item, swap the heuristic judge for
`app.rubric.Rubric` + a live model call.

---

## Modern Harness Framework: Inspect AI

### Why Inspect AI?

As of mid-2026, the LLM evaluation ecosystem has converged on **Inspect AI**
(https://inspect.aisi.org.uk/), the open-source framework from the UK AI
Security Institute, used by Anthropic, DeepMind, and the broader AISI/Inspect
Evals ecosystem.

We chose Inspect AI over alternatives:

| Framework | Why Not Chosen |
|---|---|
| `lm-evaluation-harness` | Benchmark-focused, less suited to custom pairwise-preference tasks |
| `promptfoo` / `DeepEval` | Product-eval tools, less standard for research-style reporting |
| Fully custom pairwise-judge pipeline | Loses the log viewer, statistical aggregation, and reproducibility tooling for free |

### What Inspect AI Provides

- **Dataset -> Task -> Solver -> Scorer** pipeline
- Sandboxed execution
- Built-in statistical aggregation (mean/stderr/bootstrap)
- Web UI (`inspect view`) for result inspection
- Reproducible run logs

### Position Bias Mitigation

A known limitation of pairwise LLM-judge comparisons is **position bias** —
the tendency to favor whichever candidate is shown first. Inspect AI's
standard single-ordering eval is subject to this. The harness mitigates it
the standard way:

```python
@task
def script_supervisor_preference_eval_bias_checked() -> Task:
    """Runs every pair in both A/B orderings in a single dataset."""
    records = _load_records()
    samples = (
        _records_to_samples(records, swap=False)
        + _records_to_samples(records, swap=True)
    )
    return Task(
        dataset=MemoryDataset(samples),
        solver=generate(),
        scorer=human_label_match(),
    )
```

**Treat a pair's model judgment as reliable only when both orderings agree.**
A single-ordering win rate should not be reported as ground truth on its own.

### Running the Inspect AI Adapter

```bash
pip install inspect-ai
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view
```

---

## Running Against Real PostgreSQL

The repo's default config already points at PostgreSQL
(`app/config.py: database_url`), and `docker-compose.yml` ships a
`db: postgres:16-alpine` service. To execute end-to-end:

```bash
# 1. Bring up Postgres (and optionally the app) via Docker
docker compose up -d db
docker compose ps                      # wait for db to report "healthy"

# 2. Install the project locally
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# 3. Point the app at the containerized Postgres
export HARNESS_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/creative_harness"

# 4. Generate the 20-sample demo dataset and migrate it into Postgres
python -m training.generate_fake_preferences

# 5. Run the harness -- writes evaluation_report.{md,html}, metrics.json,
#    charts/*.png, and persists one run row to Postgres
python -m app.evaluation_harness

# 6. Confirm the row actually landed in Postgres (not a fallback)
docker compose exec db psql -U postgres -d creative_harness -c \
  "SELECT run_id, suite_name, n_samples, accuracy FROM evaluation_runs ORDER BY created_at DESC LIMIT 5;"
docker compose exec db psql -U postgres -d creative_harness -c \
  "SELECT count(*) FROM preferences;"

# 7. Run the full test suite against the same Postgres instance
HARNESS_DATABASE_URL=$HARNESS_DATABASE_URL pytest -v

# 8. (Optional) modern harness run via Inspect AI -- requires a real model key
uv run inspect eval evals/inspect_preference_task.py --model anthropic/claude-sonnet-4-6
inspect view

# 9. (Optional) bring up the full stack including Langfuse
docker compose --profile default up -d
docker compose --profile observability up -d   # adds Langfuse + its own Postgres

# 10. Tear down
docker compose down            # keep volumes for next run
docker compose down -v         # also wipe the Postgres volume
```

**Step 6 is the critical verification:** it proves the write went to real
PostgreSQL, not the JSONL fallback that `app/preference_store.py` uses
silently when the database is unreachable.

---

## How to Run the Offline Harness

```bash
# Generate demo preferences (20 samples)
python -m training.generate_fake_preferences

# Run the evaluation suite
python -m app.evaluation_harness
```

Output files:

| File | Description |
|---|---|
| `docs/evaluation/evaluation_report.md` | Human-readable markdown report |
| `docs/evaluation/evaluation_report.html` | Stylized HTML report |
| `docs/evaluation/metrics.json` | Machine-readable metrics |
| `docs/evaluation/charts/win_rate_ci.png` | Win rate with 95% CI |
| `docs/evaluation/charts/win_rate_trend.png` | Win rate over preference sequence |
| `docs/evaluation/charts/samples_per_rater.png` | Samples per rater distribution |

---

## Statistical Methods Reference

### Bootstrap Confidence Interval

- **Method:** Percentile bootstrap
- **Resamples:** 5000
- **Seed:** 20260726 (fixed for reproducibility)
- **What it estimates:** Plausible range for the true human win rate

### Binomial Test

- **Null hypothesis:** Win rate = 0.5 (no preference)
- **Method:** Two-sided exact binomial test
- **Implementation:** `scipy.stats.binomtest`

### Bradley-Terry MLE

- **Model:** P(A beats B) = sigma(beta_A - beta_B), where beta are latent strengths
- **Optimization:** `scipy.optimize.minimize` with BFGS solver on the
  negative log-likelihood
- **What it estimates:** Relative candidate-template strength from pairwise
  outcomes

### Cohen's Kappa

- **Purpose:** Inter-rater agreement beyond chance
- **Interpretation:** 1.0 = perfect, 0.0 = chance, <0 = worse than chance
- **Limitation:** Not computable if any item has only one rater — the harness
  reports this explicitly

---

## References

- Inspect AI: https://inspect.aisi.org.uk/
- Inspect Evals: https://github.com/UKGovernmentBEIS/inspect_evals
- UK AISI announcement: https://www.aisi.gov.uk/blog/inspect-evals
- Anthropic "Demystifying Evals for AI Agents" (Jan 2026)
- POPE: "Prompt-based Optical/Perceptual Evaluation" — grounding benchmark methodology
