# Phase 4: Vision-Critique Effectiveness — Results

## Research Question

Does vision-grounded critique produce *better* final shot lists than text-only
critique — not just whether it is grounded (Phase 2), but whether grounding
helps the final output quality?

---

## Experiment Design

### Conditions

| Condition | Critique Modality | Reference Images |
|---|---|---|
| (a) Text-only | `gateway.call("critique")` | None |
| (b) Vision | `gateway.call_vision("visual_critique")` | Real relevant reference image |

Two full 3-turn correction loops are run per brief: one text-only, one
vision-grounded. Both use the same brief and the same number of turns
(`max_turns=3`, thresholds set high to ensure completion).

### Blind Evaluation

Outputs from (a) and (b) are shuffled before scoring to eliminate ordering
bias. The scorer does not know which regime produced which output.

---

## Results

| Metric | Value |
|---|---|
| Mean vision minus text overall delta | 0.000 |
| Median delta | 0.000 |
| Bootstrap 95% CI | [0.000, 0.000] |
| Wilcoxon signed-rank p-value | 1.0000 |
| Mean text-only cost | $0.0039 |
| Mean vision cost | $0.0085 |
| Mean cost ratio (vision/text) | 2.218x |

---

## Interpretation

In the demo/mock dataset, vision-grounded critique produced no measurable
quality improvement over text-only critique (delta = 0.000, p = 1.0). However,
the vision path costs **2.2x** as much per brief due to image-token overhead.

### Key takeaways:

1. **Cost-quality tradeoff:** Vision critique is expensive (2.2x cost) with no
   demonstrated quality gain in the mock dataset. This is a valid finding —
   the value of vision depends on the specific briefs and reference images used.

2. **Sample size:** The vision sample (8–10 brief/image pairs) is smaller than
   the text sample (20 briefs from Phase 1). This limits statistical power —
   lower confidence is flagged explicitly.

3. **Mock mode caveat:** These results are from mock mode (synthetic responses).
   With live model calls, the quality delta and cost ratio will differ. The
   experiment script is designed to run in both modes.

### When to use vision critique:

- **High-value briefs** where the reference image contains critical visual
  details (camera angles, lighting setup, costume, set design)
- **Continuity-sensitive scenes** where spatial relationships matter
- **Not for:** Routine briefs, cost-sensitive batch generation, or when the
  reference image is a generic mood board

---

## Files

- `experiments/phase4_vision_effectiveness.py` — Runnable experiment script
- `data/eval/phase4_blind_pairs.json` — Blind-eval pairs (feeds Phase 5)
- `data/results/phase4_results.json` — Raw results

---

## Limitations

1. **Single rater (blind self-evaluation):** With one scorer, inter-rater
   reliability is not measurable. This is stated plainly — seek outside raters.
2. **Mock mode results:** The 0.000 delta reflects synthetic responses, not real
   model behavior.
3. **Small vision sample:** 8–10 briefs with reference images, vs. 20 text
   briefs. Lower confidence explicitly flagged.
4. **No Cohen's kappa:** Inter-rater agreement is not computable without
   multiple raters per item (see `docs/evaluation/HARNESS_NOTES.md`).

---

## Reproducibility

```bash
python -m training.generate_fake_preferences
python experiments/phase4_vision_effectiveness.py
```

Results are saved to `data/results/phase4_results.json` and
`PHASE4_VISION_EFFECTIVENESS.md`.
