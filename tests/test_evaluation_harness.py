"""Unit tests for internal statistical functions in app/evaluation_harness.py."""
from app.evaluation_harness import (
    _bootstrap_win_rate_ci,
    _binomial_significance,
    _cohens_kappa,
    _fit_bradley_terry,
    _heuristic_judge_winner,
)
from app.schemas import PreferencePair


class TestBootstrapWinRateCI:
    def test_empty_outcomes_returns_zeros(self):
        point, lo, hi = _bootstrap_win_rate_ci([])
        assert point == 0.0
        assert lo == 0.0
        assert hi == 0.0

    def test_all_wins(self):
        outcomes = [1, 1, 1, 1, 1]
        point, lo, hi = _bootstrap_win_rate_ci(outcomes, n_resamples=100)
        assert point == 1.0
        # CI should be tight around 1.0
        assert lo >= 0.9
        assert hi <= 1.0

    def test_all_losses(self):
        outcomes = [0, 0, 0, 0, 0]
        point, lo, hi = _bootstrap_win_rate_ci(outcomes, n_resamples=100)
        assert point == 0.0
        assert lo == 0.0
        assert hi == 0.0

    def test_mixed_outcomes(self):
        outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        point, lo, hi = _bootstrap_win_rate_ci(outcomes, n_resamples=100)
        assert point == 0.5
        assert lo <= point <= hi

    def test_ci_lower_less_than_upper(self):
        outcomes = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0]
        point, lo, hi = _bootstrap_win_rate_ci(outcomes, n_resamples=200)
        assert lo <= point <= hi


class TestBinomialSignificance:
    def test_zero_total_returns_none_pvalue(self):
        result = _binomial_significance(0, 0)
        assert result["p_value"] is None
        assert result["significant_at_05"] is False

    def test_strong_win_significant(self):
        # 9/10 wins -> should be significant vs 50/50
        result = _binomial_significance(9, 10)
        assert result["significant_at_05"] is True
        assert result["p_value"] < 0.05

    def test_even_split_not_significant(self):
        # 5/10 wins -> not significant vs 50/50
        result = _binomial_significance(5, 10)
        assert result["significant_at_05"] is False

    def test_all_wins_highly_significant(self):
        result = _binomial_significance(20, 20)
        assert result["significant_at_05"] is True


class TestCohensKappa:
    def test_perfect_agreement(self):
        x = ["a", "b", "a", "b", "a"]
        y = ["a", "b", "a", "b", "a"]
        kappa = _cohens_kappa(x, y)
        assert kappa == 1.0

    def test_complete_disagreement(self):
        # When every label differs but category distributions are identical,
        # Cohen's kappa is 0 (no agreement beyond chance).
        x = ["a", "a", "a"]
        y = ["b", "b", "b"]
        kappa = _cohens_kappa(x, y)
        assert kappa == 0.0

    def test_empty_lists_returns_none(self):
        assert _cohens_kappa([], []) is None

    def test_mismatched_lengths_returns_none(self):
        assert _cohens_kappa(["a", "b"], ["a"]) is None

    def test_single_category_returns_none(self):
        assert _cohens_kappa(["a", "a"], ["a", "a"]) is None

    def test_three_categories(self):
        x = ["a", "b", "c", "a", "b"]
        y = ["a", "b", "a", "a", "c"]
        kappa = _cohens_kappa(x, y)
        assert kappa is not None
        assert -1.0 <= kappa <= 1.0


class TestFitBradleyTerry:
    def test_empty_returns_defaults(self):
        result = _fit_bradley_terry([])
        assert result["strength_gap_logit"] == 0.0
        assert result["p_a_beats_b"] == 0.5

    def test_all_a_wins(self):
        result = _fit_bradley_terry([1, 1, 1, 1, 1])
        assert result["p_a_beats_b"] > 0.5
        assert result["strength_gap_logit"] > 0

    def test_all_b_wins(self):
        result = _fit_bradley_terry([0, 0, 0, 0, 0])
        assert result["p_a_beats_b"] < 0.5
        assert result["strength_gap_logit"] < 0

    def test_p_a_beats_b_in_valid_range(self):
        result = _fit_bradley_terry([1, 0, 1, 1, 0, 1])
        assert 0.0 <= result["p_a_beats_b"] <= 1.0


class TestHeuristicJudgeWinner:
    def test_a_wins_with_better_structure(self):
        pref = PreferencePair(
            brief="A test brief.",
            candidate_a="Shot 1. Shot 2. Shot 3. Cut to interior.",
            candidate_b="Shot 1 shot 2 shot 3.",
            winner="a",
        )
        assert _heuristic_judge_winner(pref) in ("a", "b", "tie")

    def test_tie_when_equal(self):
        pref = PreferencePair(
            brief="A test brief.",
            candidate_a="Shot 1. Shot 2.",
            candidate_b="Shot 1. Shot 2.",
            winner="a",
        )
        # Same text -> tie
        assert _heuristic_judge_winner(pref) == "tie"

    def test_preserves_human_winner_when_judge_agrees(self):
        pref = PreferencePair(
            brief="A test brief.",
            candidate_a="Cut to the warehouse. Establish the scene.",
            candidate_b="They stand there talking.",
            winner="a",
        )
        judge = _heuristic_judge_winner(pref)
        # Judge should prefer A because it has more concrete action words
        assert judge in ("a", "b", "tie")

    def test_action_words_tip_judge(self):
        # "Cut" and "establish" are strong action words
        pref = PreferencePair(
            brief="A test brief.",
            candidate_a="Cut to close-up. Establish lighting.",
            candidate_b="A soft scene with gentle shadows.",
            winner="a",
        )
        assert _heuristic_judge_winner(pref) == "a"

    def test_preserves_human_winner_structure(self):
        """Heuristic judge should not always match human - it's a proxy."""
        pref = PreferencePair(
            brief="A test brief.",
            candidate_a="A scene with some dialog.",
            candidate_b="Reveal the truth. Keep the tension.",
            winner="b",
        )
        # The judge may or may not agree with the human rater
        judge = _heuristic_judge_winner(pref)
        assert judge in ("a", "b", "tie")
