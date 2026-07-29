"""Adaptive routing for Phase 7.

This module externalizes escalation rules into YAML so the model-cascade
policy is auditable and can evolve without changing the correction loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import settings
from app.schemas import TraceStep


@dataclass
class EscalationCondition:
    type: str
    metric: str
    threshold: float | None = None
    lower: float | None = None
    upper: float | None = None


@dataclass
class RoutingRule:
    task: str
    condition: EscalationCondition
    escalate_to: str | None = None
    max_escalations: int = 1


class AdaptiveRouter:
    def __init__(self, rules: list[RoutingRule]):
        self.rules = rules
        self.escalation_count: dict[str, int] = {}

    @classmethod
    def load_from_file(cls, path: str | Path) -> AdaptiveRouter:
        full_path = Path(path)
        if not full_path.exists():
            # If routing rules are intentionally absent, fallback to no rules
            # and rely on the gateway's default task models.
            return cls([])

        with full_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or []

        rules = []
        for entry in raw:
            cond_data = entry["condition"]
            condition = EscalationCondition(
                type=cond_data["type"],
                metric=cond_data["metric"],
                threshold=(
                    float(cond_data["threshold"])
                    if cond_data.get("threshold") is not None
                    else None
                ),
                lower=float(cond_data["lower"]) if cond_data.get("lower") is not None else None,
                upper=float(cond_data["upper"]) if cond_data.get("upper") is not None else None,
            )
            rules.append(
                RoutingRule(
                    task=entry["task"],
                    condition=condition,
                    escalate_to=entry.get("escalate_to"),
                    max_escalations=int(entry.get("max_escalations", 1)),
                )
            )

        return cls(rules)

    def select_model(self, task: str, trace_so_far: list[TraceStep]) -> str:
        self.escalation_count.setdefault(task, 0)

        selected = getattr(settings, "routing_default_models", {}).get(task)
        if selected is None:
            from app.gateway import TASK_DEFAULT_MODEL

            selected = TASK_DEFAULT_MODEL.get(task)
            if selected is None:
                raise ValueError(f"No default model configured for task: {task}")

        for rule in self.rules:
            if rule.task != task:
                continue
            if self._evaluate_condition(rule.condition, trace_so_far):
                if self.escalation_count[task] < rule.max_escalations:
                    self.escalation_count[task] += 1
                    return rule.escalate_to
        return selected

    def should_use_vision(self, trace_so_far: list[TraceStep]) -> bool:
        vision_rules = [rule for rule in self.rules if rule.task == "vision"]
        if not vision_rules:
            return True
        if not trace_so_far:
            # If we haven't yet seen a critique, use the vision path by default
            # when reference images are present so the first turn can be grounded.
            return True
        for rule in vision_rules:
            if self._evaluate_condition(rule.condition, trace_so_far):
                return rule.escalate_to == "use_vision"
        return False

    def _evaluate_condition(
        self,
        condition: EscalationCondition,
        trace_so_far: list[TraceStep],
    ) -> bool:
        if not trace_so_far:
            return False

        latest = trace_so_far[-1].critique
        metric_value = getattr(latest, condition.metric, None)
        if metric_value is None:
            raise ValueError(f"Unknown routing metric: {condition.metric}")

        if condition.type == "score_below":
            if condition.threshold is None:
                raise ValueError("Threshold required for score_below condition")
            return metric_value < condition.threshold
        if condition.type == "score_above":
            if condition.threshold is None:
                raise ValueError("Threshold required for score_above condition")
            return metric_value > condition.threshold
        if condition.type == "score_between":
            if condition.lower is None or condition.upper is None:
                raise ValueError("Lower and upper bounds required for score_between condition")
            return condition.lower <= metric_value <= condition.upper
        raise ValueError(f"Unknown condition type: {condition.type}")
