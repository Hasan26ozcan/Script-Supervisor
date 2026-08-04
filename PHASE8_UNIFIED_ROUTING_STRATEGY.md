# Phase 8 Unified Routing Strategy

This experiment evaluates cost-aware vision routing using the Phase 8 brief set.

## Summary

- Text Only: mean overall=6.000, mean cost=$0.0038
- Vision Only: mean overall=6.000, mean cost=$0.0084
- Adaptive: mean overall=6.000, mean cost=$0.0084

## Notes

- `text_only` uses only text critiques.
- `vision_only` uses the VLM critic on every trial.
- `adaptive` uses the vision routing rules in `config/routing_rules.yaml`.
- The chart is saved to `docs/phase8_vision_quality_vs_cost.png`.
- This script is intentionally runnable in mock mode for integration testing.
