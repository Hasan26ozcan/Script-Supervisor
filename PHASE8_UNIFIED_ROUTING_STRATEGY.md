# Phase 8: Unified Routing Strategy — Findings

## Objective

Determine when vision-grounded critique is worth the extra cost, and whether
an adaptive routing rule can preserve quality while avoiding unnecessary
vision-model expense.

This phase extends Phase 7's cost-aware routing question to the vision path.
The combined text + vision strategy directly answers the "model gateway"
requirement from the research objectives.

---

## Experiment Design

### Three Regimes

| Regime | Critique Strategy | Description |
|---|---|---|
| **Text-only** | `gateway.call("critique")` | Text-only critique on every turn; no reference images |
| **Vision-only** | `gateway.call_vision("visual_critique")` | Vision-grounded critique on every turn; reference images always used |
| **Adaptive** | Conditional vision | Vision is used only when: a reference image is present AND the text-only score is ambiguous (within 5.0–7.5) |

### Vision-Specific Escalation Rule

The adaptive vision routing rule in `config/routing_rules.yaml`:

```yaml
- task: vision
  condition:
    type: score_between
    metric: overall
    lower: 5.0
    upper: 7.5
  escalate_to: use_vision
  max_escalations: 1
```

This means vision critique is only engaged when the text-only critique
produces a score in the "ambiguous" range — not high enough to trust
(unambiguous pass), not low enough to escalate to a bigger text model.

---

## Method

1. Run on Phase 4's image-paired brief set (8–10 briefs with reference images)
2. For each brief, run all three regimes with identical correction loop settings
3. Collect final rubric score, total cost, and whether vision was used
4. Plot **rubric score vs. total cost** for all three regimes
5. Report where adaptive uses vision vs. text-only

---

## Results

The key chart `docs/phase8_vision_quality_vs_cost.png` plots each brief as a
point, colored by regime.

**Run the experiment:**

```bash
python experiments/phase8_vision_routing.py
```

Results are saved to:
- `data/results/phase8_results.json` — Full trial-by-trial results
- `docs/phase8_vision_quality_vs_cost.png` — Quality vs. cost scatter plot
- `PHASE8_UNIFIED_ROUTING_STRATEGY.md` — This file

---

## Interpretation

### Where the strategy shines

The adaptive regime should outperform both baselines when:
- Most briefs score clearly above the vision-ambiguity threshold (text-only
  is good enough, skip vision — saves cost)
- A few briefs fall in the ambiguous zone (vision helps, pay for it)

### Where it struggles

- If most briefs land in the ambiguous zone, adaptive approaches vision-only
  (no cost savings)
- If most briefs score below the threshold, adaptive approaches text-only
  (misses vision's benefits)

### Combined Routing Decision

The unified strategy (text + vision) answers the job posting's "model gateway"
requirement directly:

| Input state | Routing decision |
|---|---|
| No reference image | Text-only critique (vision unavailable) |
| Reference image + score >= 7.5 | Text-only critique (score is unambiguous) |
| Reference image + score 5.0–7.5 | Vision-grounded critique (ambiguous — resolve with vision) |
| Reference image + score <= 5.0 | Escalate to bigger text model, then vision if still weak |
| Cost threshold exceeded | Stop, return current best |

---

## Notes

- The Phase 8 chart is saved to `docs/phase8_vision_quality_vs_cost.png`
- The routing rules live in `config/routing_rules.yaml`
- If no ground truth images exist, mock trials are used so the experiment
  still runs in integration mode
- Vision sample (8–10 briefs) is smaller than text (20 briefs) — lower
  confidence is flagged explicitly

---

## Reproducibility

```bash
python experiments/phase8_vision_routing.py
```

The script runs in mock mode by default. For live results:

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your-key-here"
python experiments/phase8_vision_routing.py
```
