"""Phase 6: Rubric calibration using human pairwise preference data."""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.gateway import GatewayLedger, ModelGateway
from app.logging_config import configure_logging
from app.preference_store import PreferenceStore
from app.prompts import get_prompt
from app.rubric import Rubric, DEFAULT_CRITERIA, VISUAL_CRITERIA
from app.schemas import PreferencePair, RubricScore

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

DATA_DIR = Path("data")
RESULTS_DIR = DATA_DIR / "results"
RESULTS_PATH = RESULTS_DIR / "phase6_calibration_results.json"
REPORT_PATH = Path("PHASE6_RUBRIC_CALIBRATION.md")
WEIGHT_PLOT_PATH = Path("docs") / "phase6_weight_evolution.png"


def weighted_overall_for_criteria(scores: list[RubricScore], weights: dict[str, float], criteria: list[str]) -> float:
    filtered = [s for s in scores if s.criterion in criteria]
    if not filtered:
        return 0.0
    total_weight = sum(weights.get(s.criterion, 1.0) for s in filtered)
    if total_weight == 0:
        return sum(s.score for s in filtered) / len(filtered)
    return sum(s.score * weights.get(s.criterion, 1.0) for s in filtered) / total_weight


def predict_winner(scores_a: list[RubricScore], scores_b: list[RubricScore], weights: dict[str, float], criteria: list[str]) -> str:
    score_a = weighted_overall_for_criteria(scores_a, weights, criteria)
    score_b = weighted_overall_for_criteria(scores_b, weights, criteria)
    if math.isclose(score_a, score_b, abs_tol=1e-6):
        return "tie"
    return "a" if score_a > score_b else "b"


def load_preferences(store: PreferenceStore) -> list[PreferencePair]:
    return store.all()


def split_preferences(prefs: list[PreferencePair], test_fraction: float, seed: int) -> tuple[list[PreferencePair], list[PreferencePair]]:
    rng = random.Random(seed)
    prefs_copy = prefs.copy()
    rng.shuffle(prefs_copy)
    cut = max(1, int(len(prefs_copy) * (1 - test_fraction)))
    return prefs_copy[:cut], prefs_copy[cut:]


def score_candidate(candidate: str, brief: str, gateway: ModelGateway, critique_system: str) -> list[RubricScore]:
    prompt = f"Brief: {brief}\n\nShot list:\n{candidate}"
    result = gateway.call("critique", critique_system, prompt)
    # If the gateway is synchronous from mock mode, this will still work.
    # For a real async gateway, the script should await - but in the current
    # code path `ModelGateway.call` is synchronous in mock mode.
    if hasattr(result, "__await__"):
        import asyncio
        result = asyncio.run(result)
    scores, _ = Rubric().parse_critique_text(result.text)
    return scores


def evaluate_holdout(
    holdout: list[PreferencePair], rubric: Rubric, gateway: ModelGateway, critique_system: str
) -> dict[str, Any]:
    results = []
    for pref in holdout:
        scores_a = score_candidate(pref.candidate_a, pref.brief, gateway, critique_system)
        scores_b = score_candidate(pref.candidate_b, pref.brief, gateway, critique_system)
        predicted_overall = predict_winner(scores_a, scores_b, rubric.weights, rubric.criteria)
        predicted_text = predict_winner(scores_a, scores_b, rubric.weights, DEFAULT_CRITERIA)
        predicted_vision = predict_winner(scores_a, scores_b, rubric.weights, VISUAL_CRITERIA)
        results.append({
            "pair_id": pref.pair_id,
            "winner": pref.winner,
            "predicted_overall": predicted_overall,
            "predicted_text": predicted_text,
            "predicted_vision": predicted_vision,
            "scores_a": [{"criterion": s.criterion, "score": s.score} for s in scores_a],
            "scores_b": [{"criterion": s.criterion, "score": s.score} for s in scores_b],
        })

    def accuracy(pred_key: str) -> float:
        scored = [1 for row in results if row[pred_key] == row["winner"]]
        return float(sum(scored)) / len(results) if results else 0.0

    coverage_text = [row for row in results if any(c["criterion"] in DEFAULT_CRITERIA for c in row["scores_a"] + row["scores_b"])]
    coverage_vision = [row for row in results if any(c["criterion"] in VISUAL_CRITERIA for c in row["scores_a"] + row["scores_b"])]

    return {
        "n_holdout": len(results),
        "overall_accuracy": accuracy("predicted_overall"),
        "text_criteria_accuracy": float(sum(1 for row in coverage_text if row["predicted_text"] == row["winner"])) / len(coverage_text) if coverage_text else 0.0,
        "vision_criteria_accuracy": float(sum(1 for row in coverage_vision if row["predicted_vision"] == row["winner"])) / len(coverage_vision) if coverage_vision else 0.0,
        "coverage_text": len(coverage_text),
        "coverage_vision": len(coverage_vision),
        "results": results,
    }


def run_calibration(prefs: list[PreferencePair], test_fraction: float, seed: int) -> dict[str, Any]:
    if not prefs:
        raise ValueError("No preference data available for Phase 6 calibration.")

    train, holdout = split_preferences(prefs, test_fraction=test_fraction, seed=seed)
    rubric = Rubric()
    gateway = ModelGateway(GatewayLedger())
    critique_system = get_prompt("critique")

    print(f"Training on {len(train)} preferences, evaluating on {len(holdout)} held-out preferences")

    for pref in train:
        scores_a = score_candidate(pref.candidate_a, pref.brief, gateway, critique_system)
        scores_b = score_candidate(pref.candidate_b, pref.brief, gateway, critique_system)
        rubric.update_from_preference(pref, scores_a, scores_b)

    holdout_analysis = evaluate_holdout(holdout, rubric, gateway, critique_system)
    return {
        "trained_pairs": len(train),
        "heldout_pairs": len(holdout),
        "weight_history": rubric.weight_history,
        "holdout_analysis": holdout_analysis,
    }


def save_results(data: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_report(data: dict[str, Any]) -> None:
    analysis = data["holdout_analysis"]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 6 Rubric Calibration\n\n")
        f.write("This report evaluates how well the live rubric predicts held-out human preferences after updating weights on a training subset of the data.\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Training preferences: {data['trained_pairs']}\n")
        f.write(f"- Held-out preferences: {data['heldout_pairs']}\n")
        f.write(f"- Held-out overall rubric accuracy: {analysis['overall_accuracy']:.3f}\n")
        f.write(f"- Text-criteria prediction accuracy: {analysis['text_criteria_accuracy']:.3f} ({analysis['coverage_text']} comparisons)\n")
        f.write(f"- Vision-criteria prediction accuracy: {analysis['vision_criteria_accuracy']:.3f} ({analysis['coverage_vision']} comparisons)\n")
        f.write("\n## Notes\n\n")
        f.write("- The holdout accuracy is computed using the rubric's weighted overall score for each candidate.\n")
        f.write("- Text-criteria and vision-criteria accuracies are computed separately by restricting the rubric to only those criterion groups.\n")
        f.write("- Because the dataset is small, accuracy values should be interpreted cautiously, with confidence intervals and weights tracked over time.\n")
        if MATPLOTLIB_AVAILABLE:
            f.write("- A weight evolution plot is saved to `docs/phase6_weight_evolution.png`.\n")
        else:
            f.write("- Matplotlib is not available in the environment, so the weight evolution plot was not generated.\n")


def save_weight_plot(weight_history: list[dict[str, Any]]) -> None:
    if not MATPLOTLIB_AVAILABLE:
        print("matplotlib not installed; skipping Phase 6 weight history plot.")
        return
    WEIGHT_PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    criteria = list(weight_history[0]["weights"].keys()) if weight_history else []
    timestamps = [entry["timestamp"] for entry in weight_history]
    for crit in criteria:
        values = [entry["weights"].get(crit, 0.0) for entry in weight_history]
        plt.plot(values, label=crit)
    plt.xlabel("Preference update index")
    plt.ylabel("Rubric weight")
    plt.title("Phase 6 rubric weight evolution")
    plt.legend(loc="upper right", fontsize="small")
    plt.tight_layout()
    plt.savefig(WEIGHT_PLOT_PATH, dpi=180)
    plt.close()
    print(f"Saved weight evolution plot to {WEIGHT_PLOT_PATH}")


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run Phase 6 rubric calibration on human preference data.")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    store = PreferenceStore()
    prefs = load_preferences(store)
    if not prefs:
        print("No preference judgments found in data/preferences.jsonl. Collect comparisons with Phase 5 first.")
        return

    if len(prefs) < 5:
        print("Warning: Phase 6 calibration is designed for 50+ comparisons; results may be noisy.")

    data = run_calibration(prefs, test_fraction=args.test_fraction, seed=args.seed)
    save_results(data)
    save_report(data)
    save_weight_plot(data["weight_history"])
    print(f"Saved Phase 6 calibration results to {RESULTS_PATH}")
    print(f"Saved Phase 6 calibration report to {REPORT_PATH}")


if __name__ == "__main__":
    main()
