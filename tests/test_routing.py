import pytest

from app.gateway import TASK_DEFAULT_MODEL
from app.routing import AdaptiveRouter, EscalationCondition
from app.schemas import Critique, Draft, TraceStep


def _trace_with(overall: float):
    return [
        TraceStep(
            draft=Draft(turn=1, content="x", model="", prompt_tokens=0,
                        completion_tokens=0, latency_ms=0.0),
            critique=Critique(turn=1, scores=[], overall=overall,
                              revision_notes="", modality="text"),
        )
    ]


def test_load_from_file_and_select_model(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: revise\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: test-large-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )

    router = AdaptiveRouter.load_from_file(rules_path)
    assert router.select_model("draft", []) == TASK_DEFAULT_MODEL["draft"]
    assert router.select_model("critique", []) == TASK_DEFAULT_MODEL["critique"]

    trace = [
        TraceStep(
            draft=Draft(
                turn=1, content="", model="", prompt_tokens=0,
                completion_tokens=0, latency_ms=0.0,
            ),
            critique=Critique(turn=1, scores=[], overall=6.5, revision_notes="", modality="text"),
        )
    ]

    selected = router.select_model("revise", trace)
    assert selected == "test-large-model"


def test_select_model_no_rules_returns_default():
    router = AdaptiveRouter([])
    assert router.select_model("draft", []) == TASK_DEFAULT_MODEL["draft"]
    assert router.select_model("critique", []) == TASK_DEFAULT_MODEL["critique"]
    assert router.select_model("revise", []) == TASK_DEFAULT_MODEL["revise"]


def test_vision_rule_enables_vision_only_in_range(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: vision\n  condition:\n"
        "    type: score_between\n    metric: overall\n"
        "    lower: 5.0\n    upper: 7.5\n"
        "  escalate_to: use_vision\n  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)

    mid_trace = [
        TraceStep(
            draft=Draft(
                turn=1, content="", model="", prompt_tokens=0,
                completion_tokens=0, latency_ms=0.0,
            ),
            critique=Critique(turn=1, scores=[], overall=6.0, revision_notes="", modality="text"),
        )
    ]
    high_trace = [
        TraceStep(
            draft=Draft(
                turn=1, content="", model="", prompt_tokens=0,
                completion_tokens=0, latency_ms=0.0,
            ),
            critique=Critique(turn=1, scores=[], overall=8.0, revision_notes="", modality="text"),
        )
    ]

    assert router.should_use_vision(mid_trace) is True
    assert router.should_use_vision(high_trace) is False


# --- load_from_file: file-not-found fallback (line 45) ---
def test_load_from_file_missing_returns_empty_router(tmp_path):
    router = AdaptiveRouter.load_from_file(tmp_path / "missing_rules.yaml")
    assert router.rules == []


# --- select_model: unknown task raises ValueError (line 84) ---
def test_select_model_raises_for_unknown_task(tmp_path):
    router = AdaptiveRouter([])
    with pytest.raises(ValueError, match="No default model configured"):
        router.select_model("nonexistent_task", [])


# --- _evaluate_condition: unknown routing metric (line 121) ---
def test_evaluate_condition_unknown_metric_raises(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: big-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    trace = _trace_with(5.0)
    with pytest.raises(ValueError, match=r"Unknown routing metric"):
        router._evaluate_condition(
            EscalationCondition(
                type="score_below", metric="nonexistent_metric", threshold=5.0,
            ),
            trace,
        )


# --- _evaluate_condition: missing threshold for score_below (line 125) ---
def test_evaluate_condition_score_below_no_threshold_raises(monkeypatch, tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: big-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    with pytest.raises(ValueError, match=r"Threshold required"):
        router._evaluate_condition(
            EscalationCondition(type="score_below", metric="overall"),
            _trace_with(5.0),
        )


# --- _evaluate_condition: missing threshold for score_above (line 129) ---
def test_evaluate_condition_score_above_no_threshold_raises(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_above\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: big-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    with pytest.raises(ValueError, match=r"Threshold required"):
        router._evaluate_condition(
            EscalationCondition(type="score_above", metric="overall"),
            _trace_with(5.0),
        )


# --- _evaluate_condition: missing lower bound for score_between (lines 132-133) ---
def test_evaluate_condition_score_between_missing_lower_raises(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_between\n    metric: overall\n"
        "    lower: 5.0\n    upper: 7.0\n"
        "  escalate_to: mid-model\n  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    with pytest.raises(ValueError, match=r"Lower and upper bounds"):
        router._evaluate_condition(
            EscalationCondition(
                type="score_between", metric="overall",
                lower=None, upper=7.0,
            ),
            _trace_with(5.0),
        )


# --- _evaluate_condition: missing upper bound for score_between (lines 132-133) ---
def test_evaluate_condition_score_between_missing_upper_raises(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_between\n    metric: overall\n"
        "    lower: 5.0\n    upper: 7.0\n"
        "  escalate_to: mid-model\n  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    with pytest.raises(ValueError, match=r"Lower and upper bounds"):
        router._evaluate_condition(
            EscalationCondition(
                type="score_between", metric="overall",
                lower=5.0, upper=None,
            ),
            _trace_with(5.0),
        )


# --- score_between condition type (lines 128-130) ---
def test_evaluate_condition_score_between_within_bounds(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_between\n    metric: overall\n"
        "    lower: 5.0\n    upper: 7.0\n"
        "  escalate_to: mid-model\n  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    cond = EscalationCondition(
        type="score_between", metric="overall",
        lower=5.0, upper=7.0, threshold=None,
    )
    assert router._evaluate_condition(cond, _trace_with(6.0)) is True
    assert router._evaluate_condition(cond, _trace_with(8.0)) is False


# --- unknown condition type (line 135) ---
def test_evaluate_condition_unknown_type_raises(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: big-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    with pytest.raises(ValueError, match=r"Unknown condition type"):
        router._evaluate_condition(
            EscalationCondition(type="impossible_condition", metric="overall"),
            _trace_with(5.0),
        )


# --- _evaluate_condition: empty trace returns False (line 116) ---
def test_evaluate_condition_empty_trace_returns_false(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: draft\n  condition:\n"
        "    type: score_below\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: big-model\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    cond = EscalationCondition(
        type="score_below", metric="overall", threshold=5.0,
    )
    assert router._evaluate_condition(cond, []) is False


# --- empty trace in should_use_vision returns True (lines 101-104) ---
def test_should_use_vision_empty_trace_returns_true(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: vision\n  condition:\n"
        "    type: score_above\n    metric: overall\n"
        "    threshold: 7.0\n  escalate_to: use_vision\n"
        "  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)
    assert router.should_use_vision([]) is True
