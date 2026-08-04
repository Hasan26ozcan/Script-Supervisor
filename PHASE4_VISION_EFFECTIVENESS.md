# Phase 4 Vision Effectiveness

This report compares text-only correction loops against vision-grounded correction loops using the Phase 4 trial set.

## Summary

- Mean vision minus text overall delta: 0.000
- Median delta: 0.000
- Bootstrap 95% CI: [0.000, 0.000]
- Wilcoxon signed-rank p-value: 1.0000
- Mean text-only cost: $0.0045
- Mean vision cost: $0.0092
- Mean cost ratio (vision/text): 2.042x

## Notes

- The script runs two full correction loops per trial.
- Text-only uses no reference images. Vision uses a single relevant reference image for each brief.
- This is a within-brief paired evaluation.
