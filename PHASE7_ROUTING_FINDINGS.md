# Phase 7 Routing Findings

This document will capture the results of the cost-aware model routing experiment.
It compares three configurations:

- `cheap`: always use the default inexpensive model for each task
- `expensive`: always use a larger or more expensive model for each task
- `adaptive`: escalate only when the critique score is below the configured threshold

The key output is the quality-vs-cost chart at `docs/phase7_quality_vs_cost.png`.

## Summary

_TODO: populate after running `python experiments/phase7_routing.py`._
