# Phase 3 Correction Effectiveness

This report compares a single-pass draft + critique flow against a full 3-turn correction loop on the Phase 1 brief set.

## Summary

- Mean loop vs single-pass delta: 0.000
- Median delta: 0.000
- Bootstrap 95% CI on mean delta: [0.000, 0.000]
- Paired t-test p-value: nan
- Wilcoxon signed-rank p-value: nan
- Mean cost ratio (loop / single): 3.600x

## Notes

- The experiment uses the Phase 1 brief set from `data/briefs/phase1_briefs.json`.
- Single-pass is implemented as a one-turn run followed by its critique.
- Full correction loop is allowed up to 3 turns with plateau detection disabled so the loop completes through the turn limit.
- This script is intentionally runnable in mock mode for local integration testing.
