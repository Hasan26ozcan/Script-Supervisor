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
