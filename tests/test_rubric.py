"""Comprehensive tests for app/rubric.py."""
import pytest

from app.rubric import DEFAULT_CRITERIA, Rubric, RubricScore, VISUAL_CRITERIA
from app.schemas import PreferencePair


def test_rubric_defaults_have_uniform_weights():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights.json")
    for crit in DEFAULT_CRITERIA + VISUAL_CRITERIA:
        assert rubric.weights.get(crit, 0) == 1.0


def test_parse_critique_text_simple():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights2.json")
    raw = (
        "clarity: 7/10 - shot descriptions are clear\n"
        "tone_match: 8/10 - appropriate tone\n"
        "actionability: 5/10 - a DP could not shoot this as-is\n"
        "revision_notes: add lens/camera-movement specifics"
    )
    scores, revision = rubric.parse_critique_text(raw)
    assert len(scores) == 3
    assert revision == "add lens/camera-movement specifics"
    criteria = {s.criterion for s in scores}
    assert criteria == {"clarity", "tone_match", "actionability"}


def test_parse_critique_text_ignores_unknown_criteria():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights3.json")
    raw = "contrast: 9/10 - great contrast\nclarity: 7/10 - clear\n"
    scores, _ = rubric.parse_critique_text(raw)
    assert len(scores) == 1
    assert scores[0].criterion == "clarity"


def test_parse_critique_text_with_vision_criteria():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights4.json")
    raw = (
        "visual_continuity: 6/10 - shot 2 framing plausible\n"
        "lighting_match: 5/10 - reference shows warm light\n"
        "mood_match: 7/10 - tone is broadly consistent\n"
        "revision_notes: specify a light source consistent with the reference"
    )
    scores, revision = rubric.parse_critique_text(raw)
    assert len(scores) == 3
    assert all(s.criterion in VISUAL_CRITERIA for s in scores)
    assert "specify a light source" in revision


def test_parse_critique_text_empty_returns_empty():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights5.json")
    scores, revision = rubric.parse_critique_text("")
    assert scores == []
    assert revision == ""


def test_parse_critique_text_malformed_lines_skipped():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights6.json")
    raw = "this is not a valid score line\nclarity: 7/10 - clear\nbroken line\n"
    scores, _ = rubric.parse_critique_text(raw)
    assert len(scores) == 1
    assert scores[0].criterion == "clarity"


def test_parse_critique_text_score_clamped_at_10(monkeypatch, tmp_path):
    """Scores above 10 are not clamped by parser, but RubricScore validation
    rejects them. Test that the parser passes the raw value so validation
    catches invalid scores downstream."""
    rubric = Rubric(weights_path=tmp_path / "w.json")
    raw = "clarity: 15/10 - over the top\n"
    # RubricScore enforces score <= 10, so a score of 15 raises ValidationError
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        rubric.parse_critique_text(raw)


def test_weighted_overall_simple_average_equal_weights():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights8.json")
    rubric.weights = {c: 1.0 for c in DEFAULT_CRITERIA}
    scores = [
        RubricScore(criterion="clarity", score=8.0, rationale="clear"),
        RubricScore(criterion="tone_match", score=6.0, rationale="ok"),
        RubricScore(criterion="actionability", score=4.0, rationale="vague"),
    ]
    # equal weights: simple average
    assert rubric.weighted_overall(scores) == 6.0


def test_weighted_overall_uses_weights():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights9.json")
    rubric.weights = {"clarity": 2.0, "tone_match": 1.0, "actionability": 1.0}
    scores = [
        RubricScore(criterion="clarity", score=8.0, rationale="clear"),
        RubricScore(criterion="tone_match", score=6.0, rationale="ok"),
        RubricScore(criterion="actionability", score=4.0, rationale="vague"),
    ]
    # weighted: (8*2 + 6*1 + 4*1) / (2+1+1) = 26/4 = 6.5
    assert rubric.weighted_overall(scores) == 6.5


def test_weighted_overall_empty_scores_returns_zero():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights10.json")
    assert rubric.weighted_overall([]) == 0.0


def test_weighted_overall_missing_criterion_uses_default_weight():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights11.json")
    scores = [
        RubricScore(criterion="clarity", score=8.0, rationale="clear"),
        RubricScore(criterion="unknown_criterion", score=5.0, rationale="unclear"),
    ]
    # unknown_criterion has default weight 1.0
    result = rubric.weighted_overall(scores)
    assert result > 0


def test_update_from_preference_nudges_weights_toward_correct_criteria():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights12.json")
    rubric.weights = {"clarity": 1.0, "tone_match": 1.0, "actionability": 1.0}

    pref = PreferencePair(
        brief="test", candidate_a="A content", candidate_b="B content", winner="a"
    )

    scores_a = [RubricScore(criterion="clarity", score=8.0, rationale="clear")]
    scores_b = [RubricScore(criterion="clarity", score=4.0, rationale="vague")]

    before = rubric.weights["clarity"]
    rubric.update_from_preference(pref, scores_a, scores_b)
    after = rubric.weights["clarity"]

    # A wins and A has higher clarity -> clarity weight should increase
    assert after > before


def test_update_from_preference_ignores_tie():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights13.json")
    rubric.weights = {"clarity": 1.0}

    pref = PreferencePair(
        brief="test", candidate_a="A", candidate_b="B", winner="tie"
    )

    scores = [RubricScore(criterion="clarity", score=5.0, rationale="ok")]
    before = rubric.weights["clarity"]
    rubric.update_from_preference(pref, scores, scores)
    # weights should not change on a tie
    assert rubric.weights["clarity"] == before


def test_update_from_preference_decreases_wrong_direction_weights():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights14.json")
    rubric.weights = {"clarity": 1.0}

    pref = PreferencePair(
        brief="test", candidate_a="A", candidate_b="B", winner="b"
    )

    # A has higher clarity but B wins -> clarity weight should decrease
    scores_a = [RubricScore(criterion="clarity", score=9.0, rationale="clear")]
    scores_b = [RubricScore(criterion="clarity", score=3.0, rationale="vague")]

    before = rubric.weights["clarity"]
    rubric.update_from_preference(pref, scores_a, scores_b)
    after = rubric.weights["clarity"]

    assert after < before


def test_update_from_preference_never_below_minimum():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights15.json")
    rubric.weights = {"clarity": 0.05}

    pref = PreferencePair(
        brief="test", candidate_a="A", candidate_b="B", winner="b"
    )

    scores_a = [RubricScore(criterion="clarity", score=9.0, rationale="clear")]
    scores_b = [RubricScore(criterion="clarity", score=3.0, rationale="vague")]

    rubric.update_from_preference(pref, scores_a, scores_b)
    # weight should never go below 0.05
    assert rubric.weights["clarity"] >= 0.05


def test_record_weight_snapshot(tmp_path):
    import json

    rubric = Rubric(weights_path=tmp_path / "w.json")
    rubric.record_weight_snapshot()

    assert rubric.weight_history_path.exists()
    with rubric.weight_history_path.open("r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert "weights" in entry
    assert "timestamp" in entry


def test_save_weights_round_trip(tmp_path):
    import json

    rubric = Rubric(weights_path=tmp_path / "w.json")
    rubric.weights["clarity"] = 2.5
    rubric.save_weights()

    loaded = json.loads(rubric.weights_path.read_text())
    assert loaded["clarity"] == 2.5


def test_rubric_all_criteria_included():
    rubric = Rubric(weights_path="/tmp/nonexistent_rubric_weights16.json")
    for crit in DEFAULT_CRITERIA:
        assert crit in rubric.criteria
    for crit in VISUAL_CRITERIA:
        assert crit in rubric.criteria
