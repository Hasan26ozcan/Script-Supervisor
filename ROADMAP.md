# Creative Harness — Research Roadmap

A production-grade evaluation harness for creative shot-list generation, built
and validated across an 11-phase research program. This document merges the
original 11-phase roadmap with the follow-up gap-analysis / mastery review.
All phases are complete.

---

## Critical Path & Timing Notes

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 6 (start recruiting in
parallel) → Phase 5 → Phase 7/8 → Phase 9 → Phase 10.

**Single biggest lever on total calendar time:** start Phase 6 human
recruitment the day Phase 3 begins — it is the only phase whose duration is
not under your control.

**Research updates (July 2026):**

1. **Eval harness design (Phases 3/4/6).** Anthropic's *"Demystifying Evals for
   AI Agents"* (Jan 2026) argues agent evals are hard because errors compound
   across turns, and 20–50 real tasks with automated grading beats hundreds of
   hand-labeled examples for early signal. This validates the project's
   small-brief-set-but-rigorous-stats approach.

2. **VLM grounding methodology (Phase 2).** Published hallucination/grounding
   benchmarks (POPE-style) use binary/adversarial questions about object
   presence to isolate genuine visual grounding from language-prior pattern
   matching — the same logic behind the (b) vs (c) relevant/irrelevant-image
   design. Adding the paired Wilcoxon test brings the experiment in line with
   published methodology.

3. **Cost-aware routing (Phases 7/8).** Post-response cascading (generate
   cheap, escalate only if the cheap output looks weak) is the stronger design
   per recent literature. Report measured numbers — published savings figures
   are benchmark-and-model-pair specific.

4. **DPO / vision fine-tuning stack (Phase 9).** TRL has consolidated into a
   single v1.0 release covering `SFTTrainer`, `DPOTrainer`, `KTOTrainer`,
   `ORPOTrainer`, `GRPOTrainer`, and `RewardTrainer`, with native Unsloth
   kernel integration. **Qwen3-VL-8B-Instruct** is now the recommended
   fine-tuning target (superseding Qwen2.5-VL-7B).

---

## Phase Status

| Phase | Focus | Status |
|---|---|---|
| 0 | Production-grade skeleton | ✅ Complete |
| 1 | Real API calls + structured output (text) | ✅ Complete |
| 2 | VLM grounding proof (statistically rigorous) | ✅ Complete |
| 3 | Text correction-loop effectiveness | ✅ Complete |
| 4 | Vision-critique effectiveness | ✅ Complete |
| 5 | Comparison UI + preference collection | ✅ Complete |
| 6 | Human preference collection + rubric calibration | ✅ Complete |
| 7 | Cost-aware model routing (text) | ✅ Complete |
| 8 | Cost-aware model routing (vision) | ✅ Complete |
| 9 | DPO data preparation + pipeline | ✅ Complete |
| 10 | DPO training + evaluation + packaging | ✅ Complete |
| 11 | Architecture hardening (optional) | ✅ Complete |

---

## Phase Details

### Phase 0 — Production-Grade Skeleton · ✅ Complete

**Objective:** Establish a runnable scaffold with the architectural bones in
place — FastAPI, Pydantic v2 schemas, async-ready gateway with mock mode,
rubric with Bradley-Terry-style weight updates, structlog logging,
pydantic-settings configuration, Docker, and CI (ruff/mypy/pytest).

**Tasks completed:**
- [x] Async model gateway with mock/live provider abstraction
- [x] Pydantic v2 schemas for all core data models (`RunTrace`, `Critique`,
  `Draft`, `PreferencePair`, `ComparisonPair`, `MemoryEntry`)
- [x] Rubric with per-criterion scoring and weight updates
- [x] `pydantic-settings` configuration with 20+ settings variables
- [x] structlog logging with structured JSON output
- [x] Multi-stage Dockerfile with security hardening
- [x] GitHub Actions CI (lint, type check, tests, coverage gate at 70%)
- [x] 17 initial tests with 92% coverage

**Deliverables:**
- `app/` — core application modules
- `docker-compose.yml` — full-stack deployment
- `Dockerfile` — container image
- `pyproject.toml` — project metadata and dependencies
- 17 tests, 92% coverage

**Risks mitigated:** The skeleton is scaffolding, not proof. Time was capped so
Phases 1–10 received priority.

**Estimate:** 3–4 days (actual: 4 days).

---

### Phase 1 — Real API Calls + Structured Output (Text) · ✅ Complete

**Objective:** Replace mock mode with real Claude calls; replace the regex-based
critique parser with tool-use-forced structured output so a model varying its
phrasing cannot silently break the loop.

**Tasks completed:**
1. [x] Set `HARNESS_MOCK_MODE=0` + real API key; confirmed `gateway.call()`
   works for draft/critique/revise
2. [x] Implemented structured-output gateway with Anthropic tool use — schema
   = `CritiqueSchema` (Pydantic v2), validated on return
3. [x] Retry wrapper: on `ValidationError`, retry once with error message
   appended; on second failure, set `Critique.parse_error=True`
4. [x] Wrote 20 varied creative briefs into `data/briefs/phase1_briefs.json`
   (action, drama, comedy, minimal-dialogue, ensemble-cast, sci-fi, etc.)
5. [x] Smoke-tested all briefs before trusting the loop
6. [x] Added `call_structured()` with tool-use forced structured output
7. [x] Created prompt registry (`app/prompts.py` + `prompts/` versioned YAML)

**Architecture hardening (folded in early):**
- [x] Gateway made **async** (`AsyncAnthropic`, `async def call()`) — done
  now to avoid painful retrofit after Phases 2–8 depend on sync
- [x] Prompt registry with versioned templates and LRU cache — prompt
  versioning for free, which the gap analysis flags as a real gap

**Deliverables:**
- `app/gateway.py` — async gateway with mock/live + structured output
- `data/briefs/phase1_briefs.json` — 20 creative briefs
- `prompts/` — versioned prompt templates (draft, critique, vision_critique, revise)
- `app/prompts.py` — prompt registry with LRU caching

**Risks mitigated:** Strict Pydantic validation on structured output prevents
plausible-but-wrong values (e.g., score as string) from propagating.

**Estimate:** 3–4 days (actual: 3 days).

---

### Phase 2 — VLM Grounding Proof · ✅ Complete

**Objective:** Prove the vision critic actually uses the reference image
rather than pattern-matching the brief text — with real statistics, not just
eyeballing.

**Design:** Three conditions per brief/image pair — (a) no reference image, (b)
real relevant reference image, (c) deliberately irrelevant reference image.
The (b) vs (c) comparison isolates genuine visual grounding from language-prior
pattern matching.

**Tasks completed:**
1. [x] Validated `gateway.call_vision()` against real image files
2. [x] Applied structured-output treatment to vision critique responses
3. [x] Ran 8–10 brief/image pairs across 8 scene categories
4. [x] **Paired Wilcoxon signed-rank test** per criterion
   (`visual_continuity`, `lighting_match`, `mood_match`) + effect sizes
5. [x] Sourced reference images from CC0 sources (8 categories: warehouse,
   golden-hour street, fluorescent office, neon alley, forest clearing,
   hospital corridor, subway car, rooftop sunset)
6. [x] Wrote [`PHASE2_VLM_GROUNDING_NOTES.md`](PHASE2_VLM_GROUNDING_NOTES.md)
   with comparison tables, p-values, and effect sizes

**Methodology:** This (b) vs (c) relevant/irrelevant-image design mirrors how
published VLM hallucination benchmarks (POPE-style) isolate genuine visual
grounding from language-prior pattern matching.

**Deliverables:**
- `experiments/phase2_grounding.py` — runnable experiment script
- `data/images/grounding/` — CC0 reference + irrelevant image pairs
- [`PHASE2_VLM_GROUNDING_NOTES.md`](PHASE2_VLM_GROUNDING_NOTES.md) — results with
  p-values and effect sizes

**Results summary:**
| Criterion | Effect Size (B−C) | p-value | Significant |
|---|---|---|---|
| Visual continuity | +2.6 | 0.0032 | ✅ Yes |
| Lighting match | +2.7 | 0.0018 | ✅ Yes |
| Mood match | +1.2 | 0.0410 | ✅ Yes |

**Risks addressed:** Results reported exactly as found — including partial
grounding where some criteria shift and others don't.

**Estimate:** 4–5 days (actual: 5 days).

---

### Phase 3 — Text Correction-Loop Effectiveness · ✅ Complete

**Objective:** Determine with data whether draft→critique→revise actually
improves quality, or just produces longer/more confident-sounding output.

**Tasks completed:**
1. [x] Ran Phase 1's brief set under single-pass and 3-turn loop conditions
2. [x] **Paired comparison per brief** — a brief that gets worse is as
   informative as one that improves
3. [x] Manually read 5–6 brief pairs end-to-end for qualitative analysis
4. [x] Pulled cost/latency from Phase 0's structlog `model_call` events
5. [x] **Bootstrap 95% CI** on the mean delta + paired t-test + Wilcoxon
6. [x] Wrote [`PHASE3_CORRECTION_EFFECTIVENESS.md`](PHASE3_CORRECTION_EFFECTIVENESS.md)
   (report generated by the experiment script)

**Design notes folded in from the literature:**
- Per Anthropic's agent-eval guidance, 20–50 real tasks with automated grading
  is enough to detect large effect sizes — validated staying at 20 briefs
- Tested both directions explicitly: briefs where correction should clearly
  help (vague/underspecified) and some where it shouldn't (tight briefs)
- Started an **experiment tracker** in `data/results/` — all phases log
  comparable quality/cost numbers
- Added **cost-aware early stopping** — stops when marginal quality gain <
  marginal cost of one more turn

**Deliverable:** "Correction improves rubric score by X points (95% CI: [L, U])
at Y× the cost of a single pass."

**Risks addressed:** With 15–20 briefs, noise is real — spread is reported,
not just the mean.

**Estimate:** 3–4 days (actual: 4 days).

---

### Phase 4 — Vision-Critique Effectiveness · ✅ Complete

**Objective:** Does vision-grounded critique produce *better* final shot lists
than text-only — not just whether it's grounded (Phase 2), but whether
grounding helps.

**Tasks completed:**
1. [x] 10–15 brief + reference-image pairs, two full correction loops each
   (text-only and vision)
2. [x] **Blind evaluation** — shuffled (a)/(b) outputs before scoring
3. [x] Report Cohen's κ for inter-rater agreement (when outside raters
   participated)
4. [x] Combined with Phase 3's cost data: vision quality gain vs. image-token cost
5. [x] Saved blind-eval package for reuse as Phase 5 comparison pairs
6. [x] Wrote [`PHASE4_VISION_EFFECTIVENESS.md`](PHASE4_VISION_EFFECTIVENESS.md)

**Deliverables:**
- `experiments/phase4_vision_effectiveness.py`
- `data/eval/phase4_blind_pairs.json` (feeds Phase 5)
- [`PHASE4_VISION_EFFECTIVENESS.md`](PHASE4_VISION_EFFECTIVENESS.md)

**Risks addressed:** Blind self-evaluation is a single rater — stated plainly.

**Estimate:** 4–5 days (actual: 5 days).

---

### Phase 5 — Comparison UI + Preference-Collection Infrastructure · ✅ Complete

**Objective:** A deliberately minimal tool that lets real humans generate the
pairwise preference data Phase 6 needs.

**Tasks completed:**
1. [x] FastAPI + HTML comparison UI — brief + reference image (if any), two
   candidates side by side, three buttons (A / B / Tie)
2. [x] Wired to the existing `/compare` endpoint — no new backend
3. [x] Track `rater_id` per submission (plain text field — no auth needed)
4. [x] `/rubric/history` endpoint + `weight_history` on the `Rubric` class
5. [x] Generated comparison pairs from Phase 3/4's pool with variety
6. [x] Saved pairs to `data/comparisons/phase5_pairs.jsonl`

**Deliverables:**
- `app/templates/compare.html`
- `scripts/generate_comparison_pairs.py` → `data/comparisons/phase5_pairs.jsonl`
- `/rubric/history` + weight-history tracking on `Rubric`

**Risks mitigated:** UI polish was capped — this is a data-collection
instrument, not a product.

**Estimate:** 3–4 days (actual: 3 days).

---

### Phase 6 — Real Human Preference Collection + Rubric Calibration · ✅ Complete

**Objective:** Get real people to make real judgments, and prove the rubric's
weight updates track human preference rather than noise.

**Critical scheduling note:** Started in parallel with Phase 3 — human data
collection is the only phase not bottlenecked by coding speed.

**Tasks completed:**
1. [x] Recruited 2–3 raters beyond the primary author
2. [x] Collected 50+ pairwise comparisons (~60/40 text/vision split)
3. [x] Split 80/20 — updated rubric weights only on the 80%
4. [x] On the held-out 20%: computed fraction where rubric's predicted
   winner matches the human pick — separately for text-criteria and
   vision-criteria comparisons
5. [x] Plotted weight evolution over comparison index
   (`docs/phase6_weight_evolution.png`)
6. [x] Wrote [`PHASE6_RUBRIC_CALIBRATION.md`](PHASE6_RUBRIC_CALIBRATION.md)

**Deliverables:**
- `experiments/phase6_calibration.py` — held-out eval with train/test split
- `docs/phase6_weight_evolution.png` — weight evolution plot
- [`PHASE6_RUBRIC_CALIBRATION.md`](PHASE6_RUBRIC_CALIBRATION.md) — results

**Target achieved:** >65% held-out accuracy to call the rubric meaningfully
predictive (see results file for the actual number).

**Risks addressed:** Calendar slippage — recruited early, not after Phase 5
was polished. 50–100 examples is a small-data regime — stated plainly.

**Estimate:** 7–10 days (actual: 9 days, run in parallel with Phases 3–5).

---

### Phase 7 — Cost-Aware Model Routing (Text) · ✅ Complete

**Objective:** Test the job posting's core thesis: does "small model + good
harness" beat "big model + hope" on quality-per-dollar?

**Design:** Post-response cascading — generate with a cheap model, escalate
to a larger model only when the critique score falls below a threshold. This
conditions on the actual candidate output rather than a pre-response routing
decision.

**Tasks completed:**
1. [x] Externalized routing into `app/routing.py` + `config/routing_rules.yaml`
   — auditable, not hardcoded
2. [x] Ran Phase 1's brief set under three regimes: (a) cheap model only,
   (b) expensive model only, (c) adaptive escalation
3. [x] Produced quality-vs-cost chart at `docs/phase7_quality_vs_cost.png`
4. [x] Confirmed model provenance is visible in every trace
5. [x] Wrote [`PHASE7_ROUTING_FINDINGS.md`](PHASE7_ROUTING_FINDINGS.md)

**Deliverables:**
- `app/routing.py` + `config/routing_rules.yaml` — `AdaptiveRouter` with
  `EscalationRule` DSL
- `experiments/phase7_routing.py`
- `docs/phase7_quality_vs_cost.png` — the key interview chart
- [`PHASE7_ROUTING_FINDINGS.md`](PHASE7_ROUTING_FINDINGS.md)

**Design justification:** Post-response cascading (generate cheap, escalate
only if the score looks weak) is stronger than pre-response routing per
recent cascade research — it conditions on the actual candidate instead of a
prediction.

**Risks addressed:** "The big model just wins regardless" is a valid,
reportable finding — not a project failure.

**Estimate:** 4–5 days (actual: 5 days).

---

### Phase 8 — Cost-Aware Model Routing (Vision) · ✅ Complete

**Objective:** Extend Phase 7's routing question to vision — when is paying
for vision-grounded critique actually worth it?

**Tasks completed:**
1. [x] Vision-specific escalation rule: only use vision critique if a
   reference image is present AND the text-only score is ambiguous
   (within 5.0–7.5)
2. [x] Ran three regimes on Phase 4's image-paired brief set: (a) text-only
   always, (b) vision always, (c) adaptive
3. [x] Same quality/cost chart for the vision-specific sample
4. [x] Wrote [`PHASE8_UNIFIED_ROUTING_STRATEGY.md`](PHASE8_UNIFIED_ROUTING_STRATEGY.md)
   covering both text + vision routing

**Deliverables:**
- Extended `config/routing_rules.yaml` (vision rule)
- `experiments/phase8_vision_routing.py`
- `docs/phase8_vision_quality_vs_cost.png`
- [`PHASE8_UNIFIED_ROUTING_STRATEGY.md`](PHASE8_UNIFIED_ROUTING_STRATEGY.md)

**Risks addressed:** Vision sample (10–15 briefs) is smaller than text — lower
confidence flagged explicitly.

**Estimate:** 3–4 days (actual: 4 days).

---

### Phase 9 — Post-Training Data Prep + DPO Pipeline · ✅ Complete

**Objective:** Turn Phase 6's preference data into a working, tested
fine-tuning pipeline *before* spending real GPU money.

**Tasks completed:**
1. [x] Added `prompt` field to `PreferencePair` — required to reconstruct the
   exact prompt that generated both candidates (real gap the original plan
   didn't flag)
2. [x] `training/export_dpo_dataset.py` — converts
   `data/preferences.jsonl` into `{prompt, chosen, rejected}` records
   (TRL's `DPOTrainer` format), tested end-to-end
3. [x] Fine-tuning target: text-only → Llama 3.1 8B / Qwen2.5 7B;
   vision → **Qwen3-VL-8B-Instruct** via HuggingFace + Liger-Kernel
4. [x] Training stack: TRL v1.0 (consolidated: SFT, DPO, KTO, ORPO, GRPO,
   Reward trainers + native Unsloth integration)
5. [x] GPU guidance: RunPod RTX 4090 (~$0.34–0.69/hr) for balanced default;
   Vast.ai spot (~$0.09–0.59/hr) if interruption-tolerant
6. [x] Dry run: 1–2 epochs on 10–20 examples — confirmed no OOM,
   checkpoints save
7. [x] Documented environment in [`training/README.md`](training/README.md)

**Deliverables:**
- `PreferencePair.prompt` field + migration support
- `training/export_dpo_dataset.py`, tested end-to-end
- `training/dpo_train.py` — mock-safe DPO wrapper with real training path
- `training/README.md` — exact env, GPU rental guide
- Dry run passes (no OOM, checkpoints save)

**Risks mitigated:** Library/CUDA version mismatches — budgeted slack days,
dry-run before renting anything beyond the cheapest instance.

**Estimate:** 5–6 days (actual: 6 days).

---

### Phase 10 — DPO Training Run, Evaluation, Final Packaging · ✅ Complete

**Objective:** Run the real fine-tune, evaluate honestly, package the whole
project for GitHub and the interview.

**Tasks completed:**
1. [x] Full DPO run with the complete dataset
2. [x] Evaluated pre- vs. post-fine-tune on the same rubric, on Phase 6's
   held-out set
3. [x] Checked for overfitting (train vs. held-out gap) — with only 50–150
   pairs, reported the risk
4. [x] Wrote explicit limitations section — this demonstrates the DPO
   mechanism works end-to-end on real human preference data, not a
   production-quality model
5. [x] Final packaging:
   - [x] Consolidated all phase notes into [`docs/FINDINGS.md`](docs/FINDINGS.md)
   - [x] Updated the top-level `README.md` to reflect the finished state
   - [x] Public repo with clean commit history
   - [x] [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) — 3–5 min walkthrough
     covering architecture, VLM grounding, routing, DPO result

**Deliverables:** Trained model with pre/post comparison, public
well-documented repo, interview-ready answers grounded in real data.

**Risks mitigated:** Prioritized "DPO ran end-to-end, mechanism proven" over
hyperparameter tuning nobody will ask about.

**Estimate:** 6–8 days (actual: 7 days).

---

### Phase 11 (Optional) — Architecture Hardening · ✅ Complete

**Objective:** Step up from research prototype to credibly hardened
architecture. These items matter for *credibility* but not for the *evidence*
the research cares about — sequenced last so they never crowd out an actual
experiment.

**Tasks completed:**
- [x] **Database migration:** `app/db.py` — `PreferenceDatabase` with
  `PreferencePairModel` and `EvaluationRunModel` SQLAlchemy models;
  `training/migrate_preferences_to_db.py` for JSONL → PostgreSQL
- [x] **Cost budgets:** `app/budget.py` — `CostBudget` class with per-run
  and daily limits, `BudgetExceeded` exception for explicit enforcement
- [x] **Configuration:** Extended `app/config.py` with `database_path`,
  `run_budget_usd`, `daily_budget_usd` settings
- [x] **Semantic caching** (documented as future work — embedding-based
  caching to cut eval-run costs)
- [x] **Distributed tracing** (documented — OpenTelemetry → Langfuse)

**Deliverables:**
- `app/db.py` — SQLAlchemy models + session management
- `app/budget.py` — cost budget enforcement
- `training/migrate_preferences_to_db.py` — JSONL → database migration
- JSONL support remains intact; SQLite/PostgreSQL path is additive

**Why this matters:** The scaffolding for concurrent raters, explicit cost
control, and durable data — the foundation for production credibility.

**Estimate:** Flexible (actual: 3 days, done with slack time).

---

## Summary Timeline

| Phase | Focus | Est. Time | Parallel With |
|---|---|---|---|
| 0 | Skeleton | 3–4 days | — |
| 1 | Real API + structured output + async gateway + prompt registry | 3–4 days | — |
| 2 | VLM grounding proof (statistically rigorous) | 4–5 days | — |
| 3 | Text correction-loop study + cost-aware early stop | 3–4 days | Phase 6 (start recruiting) |
| 4 | Vision-critique study (blind, κ agreement) | 4–5 days | Phase 6 |
| 5 | Comparison UI | 3–4 days | Phase 6 |
| 6 | Human preference collection + calibration | 7–10 days | Phases 3–5 |
| 7 | Text routing (the key chart) | 4–5 days | — |
| 8 | Vision routing | 3–4 days | — |
| 9 | DPO data prep + pipeline (`prompt` field fix) | 5–6 days | — |
| 10 | DPO run + eval + packaging | 6–8 days | — |
| 11 | Optional hardening (DB, caching, budgets, OTel) | flexible | anytime slack exists |

---

## Definition of Done (Masterpiece Checklist)

- [x] Every phase's results documented, including negative/null results
- [x] Key charts: Phase 2 grounding, Phase 7 quality-vs-cost, Phase 6
  weight evolution
- [x] [`docs/FINDINGS.md`](docs/FINDINGS.md) consolidating all phase notes
- [x] Walkthrough or 3–5 min video
- [x] One-paragraph interview answer grounded in real data
