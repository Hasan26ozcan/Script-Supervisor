from pathlib import Path

from app.gateway import TASK_DEFAULT_MODEL
from app.routing import AdaptiveRouter
from app.schemas import TraceStep, Critique, Draft


def test_load_from_file_and_select_model(tmp_path):
    rules_path = tmp_path / "routing_rules.yaml"
    rules_path.write_text(
        "- task: revise\n  condition:\n    type: score_below\n    metric: overall\n    threshold: 7.0\n  escalate_to: test-large-model\n  max_escalations: 1\n",
        encoding="utf-8",
    )

    router = AdaptiveRouter.load_from_file(rules_path)
    assert router.select_model("draft", []) == TASK_DEFAULT_MODEL["draft"]
    assert router.select_model("critique", []) == TASK_DEFAULT_MODEL["critique"]

    trace = [
        TraceStep(
            draft=Draft(turn=1, content="", model="", prompt_tokens=0, completion_tokens=0, latency_ms=0.0),
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
        "- task: vision\n  condition:\n    type: score_between\n    metric: overall\n    lower: 5.0\n    upper: 7.5\n  escalate_to: use_vision\n  max_escalations: 1\n",
        encoding="utf-8",
    )
    router = AdaptiveRouter.load_from_file(rules_path)

    mid_trace = [
        TraceStep(
            draft=Draft(turn=1, content="", model="", prompt_tokens=0, completion_tokens=0, latency_ms=0.0),
            critique=Critique(turn=1, scores=[], overall=6.0, revision_notes="", modality="text"),
        )
    ]
    high_trace = [
        TraceStep(
            draft=Draft(turn=1, content="", model="", prompt_tokens=0, completion_tokens=0, latency_ms=0.0),
            critique=Critique(turn=1, scores=[], overall=8.0, revision_notes="", modality="text"),
        )
    ]

    assert router.should_use_vision(mid_trace) is True
    assert router.should_use_vision(high_trace) is False
