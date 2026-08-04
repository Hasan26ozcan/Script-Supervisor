# Phase 7 Routing Findings

This experiment compares cheap-only, expensive-only, and adaptive model routing on the Phase 1 brief set.

## Summary

- Cheap: mean overall=6.000, mean cost=$0.0044
- Expensive: mean overall=6.000, mean cost=$0.0066
- Adaptive: mean overall=6.000, mean cost=$0.0044

## Notes

- The adaptive regime uses the rules in `config/routing_rules.yaml`.
- The chart `docs/phase7_quality_vs_cost.png` plots each brief as a point.
- This script is intentionally runnable in mock mode for local integration testing.
