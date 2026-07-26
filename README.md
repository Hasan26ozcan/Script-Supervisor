# Creative Harness — Script Supervisor

An AI agent harness that drafts, critiques, and revises creative shot lists — built to answer one question with real data: **does a structured correction loop with a calibrated eval harness actually beat a single big-model pass, and when is vision-grounded critique worth the extra cost?**

This project was built as a focused technical portfolio piece for AI harness / eval engineering roles, where the evidence matters more than the demo. Every claim below is backed by a phase note with real numbers — including the negative or partial results.

## What this demonstrates

- **Multi-step agent correction loops** — draft → critique → revise, with structured tool-use output instead of regex parsing, so the loop doesn't silently break when a model varies its phrasing.
- **Eval harness design with statistical rigor** — paired comparisons, bootstrap confidence intervals, Wilcoxon signed-rank tests, and Cohen's κ for inter-rater agreement, instead of eyeballed averages.
- **VLM-based visual grounding** — quantified proof (not assertion) that a vision critic actually uses a reference image, using a relevant/irrelevant-image design similar to published hallucination benchmarks (POPE-style).
- **Cost-aware model routing** — a post-response escalation cascade (generate cheap, escalate only if the output looks weak) benchmarked against always-cheap and always-expensive baselines, producing a quality-vs-cost chart.
- **Post-training (SFT/DPO)** — real human preference data collected through a purpose-built comparison UI, used to calibrate a scoring rubric and to fine-tune a model end-to-end via TRL's `DPOTrainer`.

## Architecture

FastAPI + Pydantic v2 schemas, an async Anthropic gateway with structured tool-use output and retry logic, a versioned prompt registry, a Bradley-Terry-style rubric with weight-history tracking, structlog for full trace visibility, and Docker/CI (ruff, mypy, pytest). Routing rules are externalized to YAML and validated on startup rather than hardcoded.

## Status

This is an active build, developed in phases so that each stage produces a standalone, honestly-reported artifact rather than one big unverifiable claim at the end.

| Phase | Focus | Status |
|---|---|---|
| 0 | Production-grade skeleton (FastAPI, gateway, rubric, CI) | ✅ Done |
| 1 | Real API calls + structured output, async gateway, prompt registry | In progress |
| 2 | VLM grounding proof (statistically rigorous) | Planned |
| 3 | Text correction-loop effectiveness study | Planned |
| 4 | Vision-critique effectiveness study (blind, κ agreement) | Planned |
| 5 | Comparison UI for preference collection | In progress |
| 6 | Human preference collection + rubric calibration | In progress |
| 7 | Cost-aware model routing (text) — the key quality-vs-cost chart | Planned |
| 8 | Cost-aware model routing (vision) | Planned |
| 9 | DPO data prep + fine-tuning pipeline | Planned |
| 10 | DPO training run, evaluation, honest limitations, packaging | Planned |
| 11 | Optional architecture hardening (DB, caching, budgets, tracing) | Stretch |

Full phase-by-phase task breakdown, code specs, and risk notes live in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Why this design

Two things this project deliberately does *not* do: inflate the dataset size, and assume routing/grounding results before measuring them.

- **Small, rigorous evals over large, shallow ones.** In line with current agent-eval guidance, this project uses ~20 hand-written briefs with automated grading rather than hundreds of loosely-labeled examples — enough to detect a real effect size, with the saved time spent on statistics (bootstrap CIs, paired tests) instead of dataset volume.
- **Post-response cascading over pre-response routing.** The escalation rule generates a cheap draft first and only escalates if the critique score looks weak, conditioning on the actual output rather than predicting up front which model a task needs. Any cost-savings percentage reported is measured on this project's own briefs and model pair — published cascade numbers from other benchmarks aren't assumed to transfer.
- **Findings are reported as found.** If vision grounding turns out to be partial, or the big model just wins regardless of routing, or the fine-tune shows overfitting on a small preference set, that's what gets written up — this repo optimizes for honest signal, not for a clean story.

## Tech stack

FastAPI · Pydantic v2 · Anthropic API (async, tool-use structured output) · structlog · pydantic-settings · scipy (Wilcoxon, bootstrap) · TRL (`DPOTrainer`, LoRA/QLoRA) · Qwen3-VL-8B-Instruct / Llama 3.1 8B / Qwen2.5 7B · Docker · ruff · mypy · pytest

## Repository layout

```
app/               FastAPI app, gateway, rubric, routing
prompts/           Versioned prompt templates
experiments/        Per-phase experiment scripts
data/              Briefs, images, preference/comparison datasets
training/          DPO export + training pipeline
docs/              Roadmap, findings, generated charts
PHASE*_NOTES.md    Per-phase results, written as each phase completes
FINDINGS.md        Consolidated findings (added at the end)
```

## Findings

Populated progressively as each phase completes — see `FINDINGS.md` once available, or the individual `PHASE*_NOTES.md` files for phase-level detail in the meantime.

## Limitations

This is a portfolio-scale project, not a production system: preference data is collected from a small number of raters (2–4), and any fine-tuned model is a proof of mechanism (DPO runs end-to-end on real human preference data) rather than a production-quality model. Where sample sizes are small, confidence intervals and honest uncertainty are reported instead of point estimates presented as fact.
