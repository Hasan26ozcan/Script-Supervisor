from pathlib import Path

from app.evaluation_harness import run_evaluation_suite
from training.generate_fake_preferences import build_fake_preferences


def test_run_evaluation_suite_writes_reports_and_charts(tmp_path: Path) -> None:
    preferences = build_fake_preferences()

    result = run_evaluation_suite(
        preferences=preferences,
        workspace_root=tmp_path,
        suite_name="demo-harness",
        include_demo_dataset=True,
    )

    metrics = result["metrics"]
    assert result["summary"]["n_samples"] == 20
    assert metrics["demo_dataset_included"] is True
    assert 0.0 <= metrics["win_rate"] <= 1.0
    assert len(metrics["win_rate_95ci"]) == 2
    assert metrics["win_rate_95ci"][0] <= metrics["win_rate"] <= metrics["win_rate_95ci"][1]
    assert "p_value" in metrics["significance_vs_50_50"]
    assert "p_a_beats_b" in metrics["bradley_terry"]
    assert 0.0 <= metrics["heuristic_judge_agreement_rate"] <= 1.0
    assert metrics["inter_rater_reliability"] == (
        "not computable: every item in this dataset has exactly one rater"
    )
    assert metrics["limitations"]  # honesty section must be present

    assert result["report_markdown_path"].exists()
    assert result["report_html_path"].exists()
    assert result["metrics_json_path"].exists()
    assert result["chart_paths"]["win_rate_ci"].exists()
    assert result["chart_paths"]["win_rate_trend"].exists()
    assert result["chart_paths"]["samples_per_rater"].exists()


def test_run_evaluation_suite_flags_small_datasets_honestly(tmp_path: Path) -> None:
    preferences = build_fake_preferences()[:5]

    result = run_evaluation_suite(
        preferences=preferences,
        workspace_root=tmp_path,
        suite_name="small-sample",
        include_demo_dataset=True,
    )

    # Fewer than 20 samples must NOT be reported as the full demo dataset.
    assert result["metrics"]["demo_dataset_included"] is False
