from app.schemas import PreferencePair
from experiments.phase6_calibration import (
    predict_winner,
    split_preferences,
    weighted_overall_for_criteria,
)


def test_weighted_overall_for_criteria_text_and_vision():
    weights = {"clarity": 2.0, "visual_continuity": 1.0}
    scores = [
        type("Score", (), {"criterion": "clarity", "score": 8.0}),
        type("Score", (), {"criterion": "visual_continuity", "score": 6.0}),
    ]

    overall = weighted_overall_for_criteria(scores, weights, ["clarity"])
    assert overall == 8.0

    vision = weighted_overall_for_criteria(scores, weights, ["visual_continuity"])
    assert vision == 6.0


def test_predict_winner_uses_weighted_overall():
    scores_a = [type("Score", (), {"criterion": "clarity", "score": 8.0})]
    scores_b = [type("Score", (), {"criterion": "clarity", "score": 7.0})]
    weights = {"clarity": 1.0}

    assert predict_winner(scores_a, scores_b, weights, ["clarity"]) == "a"
    assert predict_winner(scores_b, scores_a, weights, ["clarity"]) == "b"


def test_split_preferences_preserves_order_and_seed(tmp_path):
    prefs = [
        PreferencePair(
            brief=f"brief-{i}", candidate_a="a", candidate_b="b", winner="a"
        )
        for i in range(10)
    ]
    train1, holdout1 = split_preferences(prefs, test_fraction=0.2, seed=123)
    train2, holdout2 = split_preferences(prefs, test_fraction=0.2, seed=123)

    assert len(train1) == 8
    assert len(holdout1) == 2
    assert [p.pair_id for p in train1] == [p.pair_id for p in train2]
    assert [p.pair_id for p in holdout1] == [p.pair_id for p in holdout2]
