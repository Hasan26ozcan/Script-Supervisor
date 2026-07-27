# Phase 8 Unified Routing Strategy

This document captures the Phase 8 experiment results for vision-aware routing.

## Objective

Determine when vision-grounded critique is worth the extra cost, and whether
an adaptive routing rule can preserve quality while avoiding unnecessary
vision-model expense.

## Regimes

- `text_only`: always use text critique.
- `vision_only`: always use vision-grounded critique.
- `adaptive`: use the vision routing rule to decide whether the critic should
  use vision on a given trial.

## Findings

_TODO: populate after running `python experiments/phase8_vision_routing.py`._

## Notes

- The Phase 8 chart is saved to `docs/phase8_vision_quality_vs_cost.png`.
- The routing rule lives in `config/routing_rules.yaml`.
- If no ground truth images exist, mock trials are used so the experiment still runs in integration mode.
