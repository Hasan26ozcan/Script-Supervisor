"""Experiments/phase2_grounding.py

Grounding experiment for Phase 2: VLM grounding proof.
Tests whether the vision critic actually uses the reference image
rather than just pattern-matching the brief text.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats

from app.gateway import ModelGateway
from app.logging_config import setup_logging
from app.prompts import get_prompt


@dataclass
class GroundingTrial:
    """Single trial in the grounding experiment."""
    brief: str
    reference_image: str  # path to relevant image
    irrelevant_image: str  # path to irrelevant image


def load_grounding_trials() -> list[GroundingTrial]:
    """Load grounding trials from data/images/grounding/ directory.

    Expects directory structure:
    data/images/grounding/
        category1/
            relevant.jpg
            irrelevant.jpg
        category2/
            relevant.jpg
            irrelevant.jpg
        ...
    """
    trials = []
    ground_dir = Path("data/images/grounding")

    if not ground_dir.exists():
        print(f"Warning: {ground_dir} does not exist. Using mock data.")
        # Return mock trials for testing
        return [
            GroundingTrial(
                brief="A tense confrontation in a dimly lit warehouse at night.",
                reference_image="data/images/grounding/warehouse/relevant.jpg",
                irrelevant_image="data/images/grounding/warehouse/irrelevant.jpg"
            ),
            GroundingTrial(
                brief="Two people sharing a quiet moment during golden hour on a city street.",
                reference_image="data/images/grounding/golden_hour_street/relevant.jpg",
                irrelevant_image="data/images/grounding/golden_hour_street/irrelevant.jpg"
            ),
            GroundingTrial(
                brief="A bright fluorescent office space with cubicles and harsh lighting.",
                reference_image="data/images/grounding/fluorescent_office/relevant.jpg",
                irrelevant_image="data/images/grounding/fluorescent_office/irrelevant.jpg"
            ),
        ]

    # Define briefs for each category (matching the categories mentioned in the roadmap)
    category_briefs = {
        "warehouse": "A tense confrontation in a dimly lit warehouse at night.",
        "golden_hour_street": "Two people sharing a quiet moment during golden hour on a city street.",
        "fluorescent_office": "A bright fluorescent office space with cubicles and harsh lighting.",
        "neon_alley": "A colorful neon alley at night with reflective wet pavement.",
        "forest_clearing": "A sunlit forest clearing with rays of light breaking through the canopy.",
        "hospital_corridor": "A long hospital corridor with fluorescent lighting and distant beeping monitors.",
        "subway_car": "A crowded subway car during rush hour with passengers holding onto straps.",
        "rooftop_sunset": "A rooftop overlooking a city skyline at sunset with warm golden light."
    }

    # Walk through category directories
    for category_dir in ground_dir.iterdir():
        if category_dir.is_dir():
            relevant = category_dir / "relevant.jpg"
            irrelevant = category_dir / "irrelevant.jpg"

            if relevant.exists() and irrelevant.exists():
                # Get the specific brief for this category
                brief = category_briefs.get(
                    category_dir.name,
                    f"A scene typical of {category_dir.name.replace('_', ' ')}."
                )
                trials.append(GroundingTrial(
                    brief=brief,
                    reference_image=str(relevant),
                    irrelevant_image=str(irrelevant)
                ))

    return trials


async def run_grounding_experiment(trials: list[GroundingTrial]) -> dict[str, list[dict]]:
    """Run the grounding experiment: (a) no image, (b) relevant image, (c) irrelevant image.

    Returns:
        Dictionary with keys "a", "b", "c" each containing list of critique results.
    """
    gateway = ModelGateway()
    results = {"a": [], "b": [], "c": []}

    # Get prompts
    critique_system = get_prompt("critique")
    try:
        vision_critique_system = get_prompt("vision_critique")
    except FileNotFoundError:
        # Fallback to regular critique if vision_critique not available
        vision_critique_system = get_prompt("critique")

    for trial in trials:
        print(f"Processing trial: {trial.brief[:50]}...")

        # Generate a fixed draft for all conditions (to isolate vision effect)
        # In a real experiment, we might generate a draft per condition,
        # but for grounding we want to hold the draft constant.
        draft = (
            "Shot 1: Establishing wide shot showing the setting.\n"
            "Shot 2: Medium shot on characters interacting.\n"
            "Shot 3: Close-up on important details or facial expressions.\n"
        )

        # Condition (a): no reference image (text-only critique)
        text_prompt = f"Brief: {trial.brief}\n\nShot list:\n{draft}"
        critique_a = await gateway.call_structured(
            "critique", critique_system, text_prompt, schema=dict  # Using dict for flexibility
        )
        results["a"].append(critique_a)

        # Condition (b): relevant reference image
        vision_prompt_b = (
            f"Brief: {trial.brief}\n\n"
            f"Reference image: {Path(trial.reference_image).name}\n\n"
            f"Shot list:\n{draft}"
        )
        critique_b = await gateway.call_vision(
            "visual_critique",
            vision_critique_system,
            vision_prompt_b,
            [trial.reference_image]
        )
        results["b"].append(critique_b)

        # Condition (c): irrelevant reference image
        vision_prompt_c = (
            f"Brief: {trial.brief}\n\n"
            f"Reference image: {Path(trial.irrelevant_image).name} (irrelevant)\n\n"
            f"Shot list:\n{draft}"
        )
        critique_c = await gateway.call_vision(
            "visual_critique",
            vision_critique_system,
            vision_prompt_c,
            [trial.irrelevant_image]
        )
        results["c"].append(critique_c)

    return results


def extract_scores(results: dict[str, list[dict]], criterion: str) -> tuple[list[float], list[float], list[float]]:
    """Extract scores for a specific criterion from experimental results.

    Returns:
        Tuple of (score_list_a, score_list_b, score_list_c) for the given criterion.
    """
    def get_criterion_score(critique_dict: dict) -> float:
        # Extract the text content from the critique
        text = critique_dict.get("text", "") if isinstance(critique_dict, dict) else str(critique_dict)

        # Look for pattern like "criterion: score/10 - rationale"
        pattern = rf"{criterion}:\s*(\d+(?:\.\d+)?)/10\s*[-–]\s*.*"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Fallback: try to find just the number before "/10"
        pattern2 = rf"{criterion}:\s*(\d+(?:\.\d+)?)/10"
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            return float(match2.group(1))

        return 0.0  # Default if not found

    a_scores = [get_criterion_score(critique) for critique in results["a"]]
    b_scores = [get_criterion_score(critique) for critique in results["b"]]
    c_scores = [get_criterion_score(critique) for critique in results["c"]]

    return a_scores, b_scores, c_scores


def analyze_results(results: dict[str, list[dict]]) -> dict:
    """Analyze the experimental results using statistical tests.

    Returns:
        Dictionary with analysis results including p-values and effect sizes.
    """
    criteria = ["visual_continuity", "lighting_match", "mood_match"]
    analysis = {}

    for criterion in criteria:
        a_scores, b_scores, c_scores = extract_scores(results, criterion)

        # Compare B (relevant) vs C (irrelevant) - this tests grounding
        if len(b_scores) > 1 and len(c_scores) > 1:
            # Wilcoxon signed-rank test (paired comparison)
            stat, p_value = stats.wilcoxon(b_scores, c_scores)

            # Effect size: mean difference
            b_mean = np.mean(b_scores)
            c_mean = np.mean(c_scores)
            effect_size = b_mean - c_mean

            analysis[criterion] = {
                "b_mean": float(b_mean),
                "c_mean": float(c_mean),
                "effect_size": float(effect_size),
                "p_value": float(p_value),
                "statistic": float(stat),
                "significant": p_value < 0.05
            }
        else:
            # Not enough data for statistical test
            b_mean = np.mean(b_scores) if b_scores else 0.0
            c_mean = np.mean(c_scores) if c_scores else 0.0
            effect_size = b_mean - c_mean

            analysis[criterion] = {
                "b_mean": float(b_mean),
                "c_mean": float(c_mean),
                "effect_size": float(effect_size),
                "p_value": None,
                "statistic": None,
                "significant": None,
                "note": "Insufficient data for statistical test"
            }

    return analysis


async def main():
    """Main function to run the grounding experiment."""
    # Setup logging
    setup_logging()

    print("Loading grounding trials...")
    trials = load_grounding_trials()
    print(f"Loaded {len(trials)} trials")

    if len(trials) == 0:
        print("No trials loaded. Please add image pairs to data/images/grounding/")
        return

    print("Running grounding experiment...")
    results = await run_grounding_experiment(trials)

    print("Analyzing results...")
    analysis = analyze_results(results)

    # Print results
    print("\n=== GROUNDING EXPERIMENT RESULTS ===")
    for criterion, metrics in analysis.items():
        print(f"\n{criterion}:")
        print(f"  Relevant image (B):   {metrics['b_mean']:.2f}")
        print(f"  Irrelevant image (C): {metrics['c_mean']:.2f}")
        print(f"  Effect size (B-C):    {metrics['effect_size']:.2f}")
        if metrics["p_value"] is not None:
            print(f"  p-value:              {metrics['p_value']:.4f}")
            print(f"  Significant (p<0.05): {metrics['significant']}")
        else:
            print(f"  Note: {metrics.get('note', 'No p-value available')}")

    # Save detailed results
    results_dir = Path("data/results")
    results_dir.mkdir(exist_ok=True)

    # Save raw results
    with open(results_dir / "phase2_grounding_raw.json", "w") as f:
        # Convert results to serializable format
        serializable_results = {
            "a": [r if isinstance(r, dict) else r.dict() if hasattr(r, 'dict') else str(r) for r in results["a"]],
            "b": [r if isinstance(r, dict) else r.dict() if hasattr(r, 'dict') else str(r) for r in results["b"]],
            "c": [r if isinstance(r, dict) else r.dict() if hasattr(r, 'dict') else str(r) for r in results["c"]]
        }
        json.dump(serializable_results, f, indent=2)

    # Save analysis
    with open(results_dir / "phase2_grounding_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\nResults saved to {results_dir}/")


if __name__ == "__main__":
    asyncio.run(main())