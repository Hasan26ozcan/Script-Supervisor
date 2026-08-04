# Phase 7: Cost-Aware Model Routing (Text) — Findings

## Research Question

Does "small model + good harness" beat "big model + hope" on quality-per-dollar?

This is the core thesis from the research objectives. The key output is the
quality-vs-cost chart at `docs/phase7_quality_vs_cost.png`.

---

## Design

### Three Regimes

| Regime | Strategy | Description |
|---|---|---|
| **Cheap** | Small model only | Every call uses the default inexpensive model (e.g., Claude Haiku) |
| **Expensive** | Big model only | Every call uses a larger, more capable model (e.g., Claude Sonnet) |
| **Adaptive** | Escalate when needed | Start cheap; escalate to a larger model only when the rubric score falls below a threshold |

### Post-Response Cascading

The adaptive regime uses **post-response cascading** — generate with a cheap
model first, then escalate to a larger model only when the critique score
indicates the output is weak. This design is stronger than **pre-response
routing** (deciding the model before seeing any output) because:

1. It conditions on the *actual* candidate output, not a prediction
2. It avoids escalating on outputs that are already good
3. It only pays for the expensive model when the cheap one fails

This aligns with recent cascade research findings folded into the roadmap.

### Routing Rules

Routing rules are externalized to `config/routing_rules.yaml` for
auditability:

```yaml
- task: draft
  condition:
    type: score_below
    metric: overall
    threshold: 7.5
  escalate_to: claude-sonnet-5
  max_escalations: 1
```

The `AdaptiveRouter` reads these rules at startup, making the escalation
policy version-controllable and auditable.

---

## Method

1. Run Phase 1's 20-brief set under all three regimes
2. Collect final rubric score and total cost per brief
3. Plot **rubric score vs. total cost per brief** for all three regimes
4. Confirm model provenance is visible in every trace

---

## Results

The key chart `docs/phase7_quality_vs_cost.png` plots each brief as a point,
colored by regime.

**Run the experiment:**

```bash
python experiments/phase7_routing.py
```

Results are saved to:
- `data/results/phase7_results.json` — Full trial-by-trial results
- `docs/phase7_quality_vs_cost.png` — Quality vs. cost scatter plot
- `PHASE7_ROUTING_FINDINGS.md` — This file

---

## Interpretation

The adaptive regime's value depends on where the cheap model performs
adequately vs. where it fails. The chart answers:

- **Where does adaptive win?** Briefs where the cheap model produces a strong
  enough draft that no escalation is needed — quality matches expensive,
  cost matches cheap.
- **Where does adaptive lose?** Briefs where the cheap model fails but the
  escalation trigger doesn't fire soon enough — the loop wastes a turn on the
  cheap model before escalating.
- **Where does expensive win outright?** If the cheap model is too weak to
  produce salvageable output even with escalation, the expensive baseline
  dominates.

### Honest Limitations

- Any percentage saved or quality gained is **measured on this brief set and
  this model pair** — published cascade savings numbers are specific to their
  benchmark and model pair and do not transfer as a guarantee
- The escalation rule (score threshold) is itself a hyperparameter — tuning it
  could shift the tradeoff curve
- Results may differ with different brief styles (action vs. dialogue-heavy
  vs. visual-specification scenes)

### "The big model just wins regardless" is a valid finding

If the expensive model dominates across the brief set, that is a real,
reportable result — not a project failure. It means the harness's value is
in the rubric and correction loop, not in routing.

---

## Files

- `app/routing.py` — AdaptiveRouter with escalation rule DSL
- `config/routing_rules.yaml` — YAML routing rules (auditable)
- `experiments/phase7_routing.py` — Runnable experiment script
- `data/results/phase7_results.json` — Raw results

---

## Reproducibility

```bash
python experiments/phase7_routing.py
```

The script runs in mock mode by default (`HARNESS_MOCK_MODE=1`), producing
synthetic results for integration testing. For real results:

```bash
export HARNESS_MOCK_MODE=0
export HARNESS_ANTHROPIC_API_KEY="your-key-here"
python experiments/phase7_routing.py
```
