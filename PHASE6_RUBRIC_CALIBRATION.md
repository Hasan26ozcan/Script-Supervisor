# Phase 6 Rubric Calibration

This report evaluates how well the live rubric predicts held-out human preferences after updating weights on a training subset of the data.

## Summary

- Training preferences: 16
- Held-out preferences: 4
- Held-out overall rubric accuracy: 0.000
- Text-criteria prediction accuracy: 0.000 (4 comparisons)
- Vision-criteria prediction accuracy: 0.000 (0 comparisons)

## Notes

- The holdout accuracy is computed using the rubric's weighted overall score for each candidate.
- Text-criteria and vision-criteria accuracies are computed separately by restricting the rubric to only those criterion groups.
- Because the dataset is small, accuracy values should be interpreted cautiously, with confidence intervals and weights tracked over time.
- A weight evolution plot is saved to `docs/phase6_weight_evolution.png`.
