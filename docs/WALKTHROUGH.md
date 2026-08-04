# Creative Harness — Quick Walkthrough

A 3–5 minute guide to understanding, running, and extending Creative Harness.

---

## 1. What Is This?

Creative Harness is a research-driven evaluation system for AI-assisted creative
shot-list generation. It asks one question:

> Can a structured correction loop, calibrated rubric, and vision-aware critique
> outperform a single-pass generation strategy — measured with real statistics?

The answer is documented with data across 11 research phases. See
[ROADMAP.md](../ROADMAP.md) for the full roadmap and
[docs/FINDINGS.md](FINDINGS.md) for consolidated results.

---

## 2. Architecture in 60 Seconds

```
Brief → [Draft (cheap model)] → [Critique (text or VLM)] → [Rubric score]
  ↓ yes (score < threshold)
[Revise (escalate to better model)] → [Critique again] → [New score]
  ↓ repeat until threshold met, plateau, cost threshold, or max turns
Trace saved → /compare → Rubric weights update → DPO training data
```

**Five layers:** Presentation (FastAPI) → Orchestration (loops, router) →
Service (gateway, rubric, Mem0) → Persistence (PostgreSQL + JSONL) →
Infrastructure (Docker, GitHub Actions)

See `docs/PROJECT_ARCHITECTURE.md` and `docs/TECHNICAL_DIAGRAMS.md` for full
details.

---

## 3. Run It Locally (5 minutes)

```bash
# Clone and install
git clone https://github.com/Hasan26ozcan/Script-Supervisor.git
cd Script-Supervisor
pip install -e ".[dev]"

# Run in mock mode (no API keys needed)
HARNESS_MOCK_MODE=1 uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs — you get an interactive Swagger UI for all
endpoints.

### Try the correction loop:

```bash
curl -X POST http://127.0.0.1:8000/run \
  -H "Content-Type: application/json" \
  -d '{"brief": "A tense confrontation in a dimly lit warehouse at night.", "max_turns": 3}'
```

You'll get back a `RunTrace` with every draft, critique, score, and stop reason.

### Try the comparison UI:

Open http://127.0.0.1:8000/compare-ui

---

## 4. Run the Experiments (2 minutes each, mock mode)

```bash
make phase2    # VLM grounding proof
make phase3    # Does correction improve quality?
make phase7    # The key chart: quality vs. cost by routing regime
make phase8    # Vision routing: when is vision worth the cost?
make phase6    # Rubric calibration: does the rubric predict human preference?
```

Each phase script runs in mock mode by default, producing synthetic but
structurally-valid results. For real results, set `HARNESS_MOCK_MODE=0` and
provide an Anthropic API key.

---

## 5. Run the Evaluation Harness

```bash
python -m training.generate_fake_preferences  # 20-sample demo dataset
python -m app.evaluation_harness               # Statistical suite
```

This produces:
- `docs/evaluation/evaluation_report.html` — full statistical report
- `docs/evaluation/metrics.json` — machine-readable metrics
- `docs/evaluation/charts/*.png` — visualizations (win rate CI, trend, etc.)

The evaluation harness uses real statistics: bootstrap CIs, binomial tests,
Bradley-Terry MLE, and Cohen's kappa. See
`docs/evaluation/HARNESS_NOTES.md` for methodology.

---

## 6. The Most Interesting Finding (Phase 2)

The vision critic demonstrates **strong grounding** (p < 0.05 for all
criteria), but not equally:

| Criterion | Effect | p-value |
|---|---|---|
| Visual continuity | +2.6 points | 0.0032 |
| Lighting match | +2.7 points | 0.0018 |
| Mood match | +1.2 points | 0.0410 |

**What this means:** Vision models process spatial/layout and lighting
features effectively, but abstract atmospheric qualities (mood) are harder to
ground. This directly informs Phase 8's vision routing decision.

Full details in `PHASE2_VLM_GROUNDING_NOTES.md`.

---

## 7. The Key Chart (Phase 7)

`docs/phase7_quality_vs_cost.png` plots rubric score vs. total cost for
three routing regimes:

- **Cheap model only** (Haiku) — low cost, lower quality ceiling
- **Expensive model only** (Sonnet) — high cost, higher quality ceiling
- **Adaptive escalation** — start cheap, escalate when the rubric score is
  below threshold

The adaptive regime's value depends on where the cheap model succeeds vs.
fails. See `PHASE7_ROUTING_FINDINGS.md` for interpretation.

---

## 8. DPO Training Pipeline (Phase 9/10)

```bash
# Export preferences to DPO format
python training/export_dpo_dataset.py

# Dry-run training (no GPU needed)
python training/dpo_train.py --mock --dry-run

# Real training (requires GPU)
python training/dpo_train.py \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --epochs 1
```

The `[training]` extras (TRL, PEFT, transformers) are optional — install only
when ready to train. See `training/README.md` for the full GPU rental guide.

---

## 9. Next Steps

1. **Read the architecture docs** — `docs/PROJECT_ARCHITECTURE.md`,
   `docs/TECHNICAL_DIAGRAMS.md`
2. **Run in mock mode** — `make test` (200+ tests), `make run`
3. **Run experiments** — `make phase2` through `make phase8`
4. **Try live mode** — set `HARNESS_MOCK_MODE=0` with a real API key
5. **Contribute** — see `CONTRIBUTING.md`
6. **Deploy** — `docker compose up -d` (full stack with PostgreSQL + optional
   Langfuse)

---

## 10. File Map

```
Key files you should know:
  app/main.py              — FastAPI API (POST /run, POST /compare, GET /rubric)
  app/agent_loop.py        — CorrectionLoop (the core draft-critique-revise loop)
  app/gateway.py           — ModelGateway (mock + live Anthropic/Groq)
  app/rubric.py            — Rubric scoring + Bradley-Terry weight updates
  app/routing.py           — AdaptiveRouter (YAML-driven model escalation)
  app/evaluation_harness.py — Statistical evaluation suite
  config/routing_rules.yaml — Model escalation rules (auditable, version-controlled)
  prompts/                 — Versioned prompt templates (draft, critique, vision_critique, revise)
  experiments/             — Phase experiment scripts
  data/briefs/             — 20 creative briefs for testing
  docs/                    — Architecture, CI/CD, evaluation, findings
```
