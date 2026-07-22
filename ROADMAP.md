# Creative Harness — Master Roadmap (Merged v2)

This document merges the original 11-phase roadmap with the follow-up gap
analysis / mastery review. Structure: for each phase — **objective**,
**concrete tasks (with code-level specs where useful)**, **architecture
hardening folded in at the right phase**, **deliverables**, **risks**, and
**time estimate**. Nothing from either source is dropped; the gap analysis's
"masterpiece" upgrades are now embedded inside the phase where they belong,
instead of sitting in a separate document you'd have to cross-reference.

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 6 (start recruiting
in parallel) → Phase 5 → Phase 7/8 → Phase 9 → Phase 10.

**Single biggest lever on total calendar time:** start Phase 6 human
recruitment the day Phase 3 begins — it's the only phase whose duration you
don't control.

---

## Recent research check (July 2026) — what changed in the plan below

A literature pass across four areas surfaced updates worth folding in
(each cited inline in the phase it touches):

1. **Eval harness design (Phases 3/4/6).** Anthropic's own "Demystifying
   evals for AI agents" (Jan 2026) is directly on-topic for this role: it
   argues agent evals are hard specifically because errors compound across
   turns and models find creative "wins" that static tests miss, and it
   pushes back on over-labeling — 20–50 real tasks with automated grading
   beats hundreds of hand-labeled examples for early signal. It also
   stresses testing *both* directions of a behavior (when it should and
   shouldn't happen), since one-sided evals produce one-sided optimization.
   This validates the project's small-brief-set-but-rigorous-stats approach
   and argues against over-investing in dataset size before Phase 6.
2. **VLM grounding methodology (Phase 2).** Published hallucination/
   grounding benchmarks (POPE-style) use binary/adversarial questions about
   object presence specifically to isolate genuine visual grounding from
   language-prior pattern matching — the same logic behind the (b) vs (c)
   relevant/irrelevant-image design already in Phase 2. Adding the paired
   Wilcoxon test brings the experiment in line with how this is actually
   published, not just informally reasoned about.
3. **Cost-aware routing (Phases 7/8).** Current literature draws a real
   distinction between *pre-response* routing (decide the model before
   seeing any output — FrugalGPT, RouteLLM) and *post-response* cascading
   (generate cheap, escalate only if the cheap output looks weak). The
   project's escalation rule is already post-response, which recent work
   argues is the stronger design since it conditions on the actual
   candidate rather than a prediction. One caution worth stating explicitly
   in `PHASE7_ROUTING_FINDINGS.md`: published savings numbers (e.g.
   RouteLLM's ~85%/45% figures) are benchmark-and-model-pair specific —
   report your own measured numbers, don't borrow someone else's percentage.
4. **DPO / vision fine-tuning stack (Phase 9) — this one changes a concrete
   recommendation.** TRL has consolidated into a single v1.0 release
   covering SFTTrainer, DPOTrainer, KTOTrainer, ORPOTrainer, GRPOTrainer,
   and RewardTrainer, with native Unsloth kernel integration for roughly
   2× faster SFT/DPO and up to 70% less VRAM — this is now the default
   install, not an optional add-on. On the vision side, the community
   fine-tuning repo this plan already referenced (`2U1/Qwen-VL-Series-Finetune`)
   now supports Qwen3-VL and Qwen3.5 in addition to Qwen2.5-VL, so
   **Qwen3-VL-8B-Instruct is now the more current fine-tuning target**
   (superseding the Qwen2.5-VL-7B-Instruct recommendation below). GPU
   pricing is essentially unchanged from the original plan and still holds:
   RunPod Secure Cloud RTX 4090 (~$0.34–0.69/hr, ~99% uptime), Vast.ai spot
   (~$0.09–0.59/hr, interruption-tolerant), Lambda Labs (~$2.06/hr A100 80GB,
   ~$2.99/hr H100 SXM, ~99.9% uptime SLA) — RunPod remains the sensible
   default for a short, tolerant experiment.

---

## Phase 0 — Production-grade skeleton ✅ (done, hardening optional)

**Status:** Done. 17 tests, 92% coverage. FastAPI + Pydantic v2 schemas +
gateway with mock mode + rubric with Bradley-Terry-style updates +
structlog + pydantic-settings + Docker + CI (ruff/mypy/pytest).

**Optional hardening (do only if time allows — not blocking Phase 1):**
- `config/routing_rules.yaml` + a `RoutingRule` Pydantic model in
  `config.py`, validated on startup — sets up Phase 7/8 cleanly later.
- CI additions: `bandit` (security), `pip-audit` (deps), `detect-secrets`,
  `pytest-benchmark` for latency regression.
- Multi-stage Dockerfile (builder → runtime), distroless base, SBOM via
  `syft` — nice for the repo but purely cosmetic for the interview.

**Reality check:** the skeleton is the scaffolding, not the proof. Don't
let Phase 0 polish eat time that Phases 1–10 need — those are where the
actual evidence gets produced.

---

## Phase 1 — Real API calls + structured output (text path)

**Objective:** Replace mock mode with real Claude calls; replace the
regex-based critique parser with tool-use-forced structured output so a
model varying its phrasing can't silently break the loop.

**Tasks:**
1. Set `HARNESS_MOCK_MODE=0` + real API key; confirm `gateway.call()`
   works for draft/critique/revise.
2. Implement `gateway.call_structured()`: Anthropic tool-use with
   `tool_choice={"type": "tool", "name": "submit_critique"}`, schema =
   `CritiqueSchema` (Pydantic v2, `.model_json_schema()`), validated with
   Pydantic on the way back — not trusted blindly even though the API
   enforces shape.
3. Retry wrapper: on `ValidationError`, retry once with the error message
   appended to the prompt; on second failure, set
   `Critique.parse_error=True` instead of silently dropping the turn.
4. Write 15–20 varied briefs (action, drama, comedy, minimal-dialogue,
   ensemble-cast) into `data/briefs/phase1_briefs.json` — reused in
   Phases 3, 6, 7.
5. Smoke-test 5–10 briefs manually before trusting the loop.

**Fold-in from architecture review (do now, not later):**
- Make the gateway **async** (`AsyncAnthropic`, `async def call()` /
  `call_structured()`) — retrofitting async after Phases 2–8 depend on the
  sync version is much more painful than doing it now.
- Add a **prompt registry** (`app/prompts.py` + `prompts/<name>/v1.yaml`)
  instead of hardcoded strings in `agent_loop.py`. This buys you prompt
  versioning for free, which the gap analysis flags as a real gap — cheap
  to add here, expensive to retrofit.

**Deliverables:**
- `gateway.call_structured()` with tool-use + retry, used in
  `agent_loop.py` (regex path removed from the hot path)
- `data/briefs/phase1_briefs.json` (20 briefs)
- `prompts/` registry with versioned templates
- `PHASE1_STRUCTURED_OUTPUT_NOTES.md` — validation error rate, retry
  success %, token overhead, short manual QA note

**Risks:** tool-use schemas can get plausible-but-wrong values (e.g. score
as a string) — validate strictly, don't trust the API's own adherence.

**Estimate:** 3–4 days.

---

## Phase 2 — VLM grounding proof (real vision calls)

**Objective:** Prove the vision critic actually uses the reference image
rather than pattern-matching the brief text — quantified, not asserted.
This is flagged by both documents as the single strongest, most specific
interview claim in the whole project, so do it early while API access and
context are fresh.

**Tasks:**
1. Validate `gateway.call_vision()` against real image files (jpg/png).
2. Apply Phase 1's structured-output treatment to
   `VISION_CRITIQUE_SYSTEM`'s response.
3. **Grounding experiment**, same brief + shot list, three conditions:
   - (a) no reference image
   - (b) real, relevant reference image
   - (c) deliberately irrelevant reference image
4. Run across 8–10 brief/image pairs (one example isn't proof).
5. **Statistical rigor (from the gap analysis):** don't just eyeball (b)
   vs (c). Use a paired **Wilcoxon signed-rank test** per criterion
   (`visual_continuity`, `lighting_match`, `mood_match`) plus an effect
   size (mean score delta). Report p-values, not vibes.
6. Source reference images from Unsplash/Pexels (CC0) or your own phone
   photos — avoid anything copyrighted in a public repo. 8 category pairs
   (warehouse, golden-hour street, fluorescent office, neon alley, forest
   clearing, hospital corridor, subway car, rooftop sunset) is enough.
7. Write `PHASE2_VLM_GROUNDING_NOTES.md`: comparison table + p-values +
   effect sizes + an honest verdict — including "partial grounding"
   (some criteria shift, others don't) if that's what you find.

**Methodology note:** this (b) vs (c) relevant/irrelevant-image design
mirrors how published VLM hallucination benchmarks (POPE-style) isolate
genuine visual grounding from language-prior pattern matching — using
binary/adversarial questions specifically so a model can't shortcut to
the right-sounding answer from text alone. Framing it this way in the
write-up ties the experiment to established methodology rather than
looking like an ad hoc test you invented for the interview.

**Code shape:**
```python
# experiments/phase2_grounding.py
from scipy import stats
import numpy as np

async def run_grounding_experiment(trials: list[GroundingTrial]):
    results = {"a": [], "b": [], "c": []}
    for t in trials:
        draft = generate_fixed_draft(t.brief)  # same draft across conditions
        results["a"].append(await gateway.critique_text(t.brief, draft))
        results["b"].append(await gateway.critique_vision(t.brief, draft, [t.reference_image]))
        results["c"].append(await gateway.critique_vision(t.brief, draft, [t.irrelevant_image]))

    for crit in ["visual_continuity", "lighting_match", "mood_match"]:
        b_vals = [r[crit] for r in results["b"]]
        c_vals = [r[crit] for r in results["c"]]
        stat, p = stats.wilcoxon(b_vals, c_vals)
        effect = np.mean(np.array(b_vals) - np.array(c_vals))
        print(f"{crit}: p={p:.4f}, effect={effect:.2f}")
```

**Deliverables:**
- `experiments/phase2_grounding.py` (runnable, not just planned)
- `data/images/grounding/` (relevant + irrelevant pairs, licensed)
- `PHASE2_VLM_GROUNDING_NOTES.md` with real numbers

**Risks:** result may be "partial grounding" — report exactly as found.

**Estimate:** 4–5 days.

---

## Phase 3 — Text correction-loop effectiveness study

**Objective:** Determine with data whether draft→critique→revise actually
improves quality, or just produces longer/more confident-sounding output.

**Tasks:**
1. Run Phase 1's brief set under (a) single-pass, (b) full 3-turn loop.
2. **Paired comparison per brief** (not just averages) — a brief that gets
   worse is as informative as one that improves.
3. Manually read 5–6 brief pairs end to end — qualitative pass matters as
   much as the number.
4. Pull cost/latency straight from Phase 0's structlog `model_call`
   events — don't recompute.
5. **Statistical rigor (gap analysis):** paired t-test or, given small n,
   a **bootstrap 95% CI** on the mean delta — not just a point estimate.
6. Write `PHASE3_CORRECTION_EFFECTIVENESS.md`.

**Fold-in from current eval-harness literature:** Anthropic's own agent-eval
guidance argues 20–50 real tasks with automated grading is enough to
detect large effect sizes — validates *not* expanding past 20 briefs here
even though the correction-loop delta will be noisy; spend the saved time
on the statistics (bootstrap CI) instead of more briefs. Also test both
directions explicitly: some briefs where correction should clearly help
(vague/underspecified) and some where it shouldn't (already-tight briefs)
— a one-sided sample would make the loop look better than it is.

**Fold-in from architecture review:**
- This is the natural point to start an **experiment tracker** (MLflow is
  fine, or even a structured `experiments/tracker.py` that logs params/
  metrics/artifacts) since Phases 3–10 all produce comparable
  quality/cost numbers you'll want to compare later.
- Add a **cost-aware early-stopping** check to the loop here: stop when
  marginal quality gain < marginal cost of one more turn. This directly
  answers the job posting's "small models + good harness > big models +
  hope" thesis and costs almost nothing to add once you have the cost
  data from this phase.

**Deliverable:** "Correction improves rubric score by X points (95% CI:
[L, U]) at Y× the cost of a single pass."

**Risks:** with 15–20 briefs, noise is real — report spread, not just mean.

**Estimate:** 3–4 days.

---

## Phase 4 — Vision-critique effectiveness study

**Objective:** Does vision-grounded critique produce *better final shot
lists* than text-only — not just whether it's grounded (Phase 2), but
whether grounding helps.

**Tasks:**
1. 10–15 brief + real-reference-image pairs, two full correction loops
   each: (a) text-only critique throughout, (b) vision critique throughout.
2. **Blind evaluation**: shuffle (a)/(b) outputs before scoring yourself.
3. If possible, recruit 1–2 outside raters; report agreement — use
   **Cohen's κ** for inter-rater agreement (gap analysis addition) rather
   than a vague "we mostly agreed."
4. Combine with Phase 3's cost data: is vision's quality gain worth the
   extra image-token cost?
5. Save the blind-eval package for reuse as Phase 5 comparison pairs.

**Deliverables:**
- `experiments/phase4_vision_effectiveness.py`
- `data/eval/phase4_blind_pairs.json` (feeds Phase 5)
- `PHASE4_VISION_EFFECTIVENESS.md` with κ and cost/quality verdict

**Risks:** blind self-evaluation is still a single rater by default — say
so plainly if outside raters didn't happen in time.

**Estimate:** 4–5 days.

---

## Phase 5 — Comparison UI + preference-collection infrastructure

**Objective:** A deliberately minimal tool that lets real humans generate
the pairwise preference data Phase 6 needs.

**Tasks:**
1. FastAPI + Jinja2 (or a static page) — brief + reference image (if any),
   two candidates side by side, three buttons (A / B / tie). HTMX keeps it
   zero-JS if you want it deployable fast.
2. Wire to the existing `/compare` endpoint from Phase 0 — no new backend.
3. Track `rater_id` per submission (plain text field / query param —
   no auth system needed for 2–3 known raters).
4. `/rubric/history` endpoint + a `weight_history` list on the `Rubric`
   class so you can watch weights move as comparisons come in.
5. Generate comparison pairs from Phase 3/4's pool: different turns,
   different models, text-vs-vision — enough variety to avoid trivial
   comparisons.

**Deliverables:**
- `app/templates/compare.html`
- `scripts/generate_comparison_pairs.py` → `data/comparisons/phase5_pairs.jsonl`
- `/rubric/history` + weight-history tracking

**Risks:** don't over-invest in UI polish — this is a data-collection
instrument, not a product. Cap time spent here.

**Estimate:** 3–4 days.

---

## Phase 6 — Real human preference collection + rubric calibration

**Objective:** Get real people to make real judgments, and prove the
rubric's weight updates track human preference rather than noise.

**Tasks:**
1. **Start in parallel with Phase 3** — human data collection is the one
   part of this project not bottlenecked by your coding speed. Send
   recruitment messages the day Phase 3 starts.
2. Recruit yourself + 2–3 others; target 50–100 pairwise comparisons
   (~60/40 text/vision split).
3. Split 80/20; update rubric weights only on the 80%, hold out the 20%.
4. On the held-out set: compute the fraction of comparisons where the
   rubric's predicted winner matches the human's pick — separately for
   text-criteria and vision-criteria comparisons. **Target: >65% held-out
   accuracy** to call it meaningfully predictive (gap analysis benchmark).
5. Plot weight evolution over comparison index (matplotlib →
   `docs/phase6_weights.png`) — converging, oscillating, or still moving
   at #100?
6. Write `PHASE6_RUBRIC_CALIBRATION.md` with an honest read: 50–100
   examples is a small-data regime — say so plainly.

**Deliverables:**
- `experiments/phase6_calibration.py` (held-out eval, train/test split)
- `docs/phase6_weights.png`
- `PHASE6_RUBRIC_CALIBRATION.md`

**Risks:** calendar slippage — you don't control how fast people vote.
Recruit early, not after Phase 5 is polished.

**Estimate:** 7–10 days (mostly waiting, run in parallel with 3–5).

---

## Phase 7 — Cost-aware model routing (text)

**Objective:** Test the job posting's core thesis directly — does "small
model + good harness" beat "big model + hope" on quality-per-dollar? Both
source documents agree: this produces **the single most important chart
in the whole project** for the interview.

**Tasks:**
1. Externalize routing into `app/routing.py` + `config/routing_rules.yaml`
   (auditable, not hardcoded) — an `AdaptiveRouter` with an
   `EscalationRule` DSL, e.g. "if critique score stays below threshold for
   2 consecutive turns, escalate to a larger model for the next draft."
2. Run Phase 1's brief set under three regimes: (a) Haiku-only, (b)
   Sonnet/Opus-only, (c) adaptive escalation.
3. Plot **rubric score vs. total cost per brief** for all three regimes.
4. Confirm model provenance is fully visible in every trace (Phase 0's
   `Draft.model` field + structlog events already capture this).
5. Write up where adaptive wins, where it doesn't, and why.

**Code shape:**
```python
# app/routing.py
class AdaptiveRouter:
    def __init__(self, rules: list[EscalationRule]):
        self.rules = rules
        self.escalation_count: dict[str, int] = defaultdict(int)

    def select_model(self, task: str, trace_so_far: RunTrace) -> str:
        for rule in self.rules:
            if rule.task == task and self._evaluate_condition(rule.condition, trace_so_far):
                if self.escalation_count[task] < rule.max_escalations:
                    self.escalation_count[task] += 1
                    return rule.escalate_to
        return TASK_DEFAULT_MODEL[task]
```

**Deliverables:**
- `app/routing.py` + `config/routing_rules.yaml`
- `experiments/phase7_routing.py`
- `docs/phase7_quality_vs_cost.png` — **the** interview chart
- `PHASE7_ROUTING_FINDINGS.md`

**Risks:** result may be "the big model just wins regardless" — a valid,
reportable finding, not a project failure.

**Fold-in from routing literature:** the escalation rule above is a
*post-response* cascade (generate cheap, escalate only if the score looks
weak), which current cascade research argues is stronger than *pre-response*
routing (deciding the model before seeing any output, as in FrugalGPT or
RouteLLM) — it conditions on the actual candidate instead of a prediction.
Say this explicitly in the write-up as the design justification. Also state
plainly in `PHASE7_ROUTING_FINDINGS.md` that any percentage you report is
measured on *your* briefs and *your* model pair — published cascade
savings numbers are specific to their benchmark and model pair and don't
transfer as a guarantee.

**Estimate:** 4–5 days.

---

## Phase 8 — Cost-aware model routing (vision)

**Objective:** Extend Phase 7's routing question to vision: when is
paying for vision-grounded critique actually worth it?

**Tasks:**
1. Vision-specific escalation rule, e.g. "only use vision critique if a
   reference image is present AND the text-only score is ambiguous
   (within N points of the pass threshold, e.g. 5.0–7.5)."
2. Run three regimes on Phase 4's image-paired brief set: (a) text-only
   always, (b) vision always, (c) adaptive.
3. Same quality/cost chart as Phase 7, for the vision-specific sample.
4. Write a combined routing-decision document covering text + vision —
   directly answers the "model gateway" requirement in the job posting.

**Deliverables:**
- Extended `routing_rules.yaml` (vision rule)
- `experiments/phase8_vision_routing.py`
- `docs/phase8_vision_quality_vs_cost.png`
- `PHASE8_UNIFIED_ROUTING_STRATEGY.md`

**Risks:** vision sample (10–15 briefs) is smaller than text — flag lower
confidence explicitly rather than presenting both charts as equally solid.

**Estimate:** 3–4 days.

---

## Phase 9 — Post-training data prep + DPO pipeline setup

**Objective:** Turn Phase 6's preference data into a working, tested
fine-tuning pipeline *before* spending real GPU money.

**Tasks:**
1. **Schema fix first:** add a `prompt: str` field to `PreferencePair` —
   without it you can't reconstruct the exact prompt that generated both
   candidates once they come from different turns/models/conditions. This
   is a real gap the original 11-phase plan didn't flag; fix it before
   writing the exporter.
2. `training/export_dpo_dataset.py`: converts `data/preferences.jsonl`
   into `{prompt, chosen, rejected}` records (TRL's `DPOTrainer` format).
3. **Fine-tuning target (updated):** text-only → Llama 3.1 8B Instruct or
   Qwen2.5 7B Instruct (mature QLoRA/DPO recipes, unchanged). Vision →
   **Qwen3-VL-8B-Instruct** (updated from the earlier Qwen2.5-VL-7B
   recommendation) via the community `2U1/Qwen-VL-Series-Finetune`
   implementation, which now supports Qwen3-VL and Qwen3.5 in addition to
   Qwen2.5-VL, using only HuggingFace + Liger-Kernel (QLoRA + vision +
   DeepSpeed). Note: Qwen3.5-series variants currently need
   `--disable_flash_attn2 True` in that repo — check the repo's changelog
   before the dry run in case this has since been fixed.
4. **Training stack (updated):** TRL has consolidated into a single v1.0
   release covering `SFTTrainer`, `DPOTrainer`, `KTOTrainer`, `ORPOTrainer`,
   `GRPOTrainer`, and `RewardTrainer` in one library, with native Unsloth
   kernel integration built in — roughly 2× faster SFT/DPO and up to 70%
   less VRAM out of the box, so this is now the default install rather
   than an optional add-on. Use `DPOConfig` (inherits from
   `transformers.TrainingArguments`) + PEFT LoRA as the default path.
5. **GPU (pricing checked July 2026, unchanged from original estimate):**
   one 24–48GB-class GPU is enough for a single 7–8B QLoRA/DPO run.
   RunPod Secure Cloud RTX 4090 (~$0.34–0.69/hr, ~99% uptime SLA, 5-minute
   setup) is the sensible balanced default; Vast.ai spot (~$0.09–0.59/hr,
   marketplace pricing, no uptime SLA, can be reclaimed with ~15 seconds
   notice) is cheaper if the job tolerates interruption; Lambda Labs
   (~$2.06/hr A100 80GB, ~$2.99/hr H100 SXM, ~99.9% uptime SLA) only if a
   long run makes an interruption costly to redo.
6. **Dry run:** 1–2 epochs on 10–20 examples to confirm environment, data
   format, and checkpoint saving all work before committing to a full run.
7. Document environment (CUDA/package versions, exact commands) in
   `training/README.md` so Phase 10 isn't blocked by environment debugging.

**Deliverables:**
- `PreferencePair.prompt` field + migration script
- `training/export_dpo_dataset.py`, tested end-to-end
- `training/run_dpo.py` (TRL DPOTrainer + LoRA/QLoRA wrapper)
- `training/README.md` (exact env, GPU rental guide)
- Dry run passes on a small subset (no OOM, checkpoints save)

**Risks:** library/CUDA version mismatches are historically the biggest
time sink here — budget slack days specifically, dry-run before renting
anything beyond the cheapest available instance.

**Estimate:** 5–6 days.

---

## Phase 10 — DPO training run, evaluation, honest limitations, final packaging

**Objective:** Run the real fine-tune, evaluate it honestly, package the
whole project for GitHub and the interview.

**Tasks:**
1. Full DPO run on the rented GPU with the full (not subset) dataset.
2. Evaluate pre- vs. post-fine-tune on the **same rubric** used
   throughout, on Phase 6's held-out set.
3. Check for overfitting (train vs. held-out gap) — with only 50–150
   preference pairs, this is a real risk; report it if you see it.
4. Write an explicit limitations section: this is not a production-quality
   model; it demonstrates the DPO mechanism works end-to-end on real human
   preference data; quality scaling with more data is the expected next
   step, not yet demonstrated.
5. **Final packaging:**
   - Consolidate all `PHASE*_NOTES.md` files into one `FINDINGS.md`.
   - Update the top-level `README.md` to reflect the finished state.
   - Push to GitHub, public, clean commit history (squash exploratory
     commits).
   - Record a 3–5 min walkthrough (or `WALKTHROUGH.md`) covering:
     architecture, the VLM grounding finding, the routing finding, the
     DPO result.
6. Prepare the one-paragraph interview answer the job posting explicitly
   asks for — pull it directly from whichever surprised you more: Phase
   2's grounding result or Phase 7's routing result.

**Deliverables:** trained model with pre/post comparison, public
well-documented repo, ready interview answer grounded in real data.

**Risks:** time pressure is highest here — ship "DPO ran end-to-end,
mechanism proven" over chasing hyperparameter tuning nobody will ask about.

**Estimate:** 6–8 days.

---

## Phase 11 (optional, bonus) — Architecture hardening pass

Only attempt this if Phases 1–10 are done with time to spare. These are
the gap analysis's "production scale" items that matter for *credibility*
but not for the *evidence* the interview cares about — sequence them last
so they never crowd out an actual experiment.

- **Database migration:** JSONL → SQLite/Postgres for `runs`, `traces`,
  `preferences`, `rubric_weights` (schema sketch below). Useful once
  Phase 5's UI has real concurrent raters.
  ```sql
  CREATE TABLE preferences (
      pair_id UUID PRIMARY KEY,
      brief TEXT NOT NULL,
      prompt TEXT NOT NULL,
      winner VARCHAR(4),
      rater VARCHAR(100),
      notes TEXT,
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```
- **Semantic caching** (embedding-based, `sentence-transformers/all-MiniLM-L6-v2`)
  to cut eval-run costs during Phases 3–8's repeated experiments.
- **Cost budgets & alerts:** a `CostBudget` class with per-run and daily
  limits, raising `BudgetExceeded` before an experiment accidentally burns
  real money.
- **Distributed tracing:** OpenTelemetry → Langfuse, full trace tree
  (gateway → loop → API) instead of structlog-only. Langfuse remains the
  strongest self-hosted, genuinely-free option with no per-seat pricing —
  relevant if brief content is sensitive and you don't want it leaving
  your infra. Promptfoo is a lighter, CLI-only alternative if you don't
  want to stand up a server just for Phase 7/8's regression-style
  comparisons.
- **RL beyond DPO:** if there's real time left, TRL's `GRPOTrainer` with
  the rubric itself as a reward model is the natural "bonus phase" the
  gap analysis floats — closes the preference → rubric → reward model →
  RL loop the job posting gestures at, but treat this as a stretch goal,
  not a commitment.

---

## Summary timeline

| Phase | Focus | Est. time | Parallel with |
|---|---|---|---|
| 0 | Skeleton | done | — |
| 1 | Real API + structured output (text) + async gateway + prompt registry | 3–4 days | — |
| 2 | VLM grounding proof (statistically rigorous) | 4–5 days | — |
| 3 | Text correction-loop study + cost-aware early stop | 3–4 days | Phase 6 (start recruiting) |
| 4 | Vision-critique study (blind, κ agreement) | 4–5 days | Phase 6 |
| 5 | Comparison UI | 3–4 days | Phase 6 |
| 6 | Human preference collection + calibration | 7–10 days | Phases 3–5 |
| 7 | Text routing (the chart) | 4–5 days | — |
| 8 | Vision routing | 3–4 days | — |
| 9 | DPO data prep + pipeline (with `prompt` field fix) | 5–6 days | — |
| 10 | DPO run + eval + packaging | 6–8 days | — |
| 11 | Optional hardening (DB, caching, budgets, OTel, GRPO) | flexible | anytime slack exists |

**Masterpiece checklist (definition of done), condensed:**
- [ ] Every phase's `.md` note published, including negative/null results
- [ ] `docs/phase2_grounding_results.png`, `phase3_correction_effectiveness.png`,
      `phase7_quality_vs_cost.png` (the chart), `phase6_weight_evolution.png`
- [ ] `FINDINGS.md` consolidating all phase notes
- [ ] `WALKTHROUGH.md` or 3–5 min video
- [ ] One-paragraph "most interesting harness/eval + what I learned was
      wrong" answer, ready verbatim for the interview