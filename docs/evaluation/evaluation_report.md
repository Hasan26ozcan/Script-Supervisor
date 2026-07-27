# Evaluation Report (standalone proof-run)

- Suite: proof-run-standalone
- Dataset: fake_human_judgments_20_samples (demo dataset included: True)
- Samples: 20 (holdout size: 4)
- Candidate A win rate: 0.500 (95% bootstrap CI: 0.300-0.700)
- Two-sided binomial test vs 50/50: p = 1.0, significant at 0.05: False
- Bradley-Terry P(A beats B): 0.5
- Heuristic judge vs human agreement: 0.500 (Cohen's kappa: 0.0)
- Inter-rater reliability: not computable: every item in this dataset has exactly one rater

> Produced by a standalone proof-runner (no pydantic/sqlalchemy available in this analysis sandbox, no network). Identical statistical/plotting logic to app/evaluation_harness.py. DB persistence step was not exercised here -- run the real module locally per docs/evaluation/HARNESS_NOTES.md.

See `docs/evaluation/HARNESS_NOTES.md` for full methodology, limitations,
and the exact commands to re-run this against real PostgreSQL.
