"""Experiments/phase4_vision_effectiveness.py

Phase 4: Vision-critique effectiveness study.

Compare two full correction loops on the same brief set:
  (a) text-only critique throughout
  (b) vision-grounded critique throughout

This script computes paired quality deltas, cost ratios, and saves a summary
report and raw results for later analysis.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats

from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.logging_config import configure_logging
from app.rubric import Rubric
from app.schemas import ReferenceImage


DATA_DIR = Path("data")
BRIEFS_PATH = DATA_DIR / "briefs" / "phase1_briefs.json"
GROUNDING_DIR = DATA_DIR / "images" / "grounding"
RESULTS_DIR = DATA_DIR / "results"
REPORT_PATH = Path("PHASE4_VISION_EFFECTIVENESS.md")


@dataclass
class VisionTrial:
    id: str
    title: str
    brief: str
    reference_image: str


def load_vision_trials() -> list[VisionTrial]:
    if not GROUNDING_DIR.exists():
        print(f"Warning: grounding directory not found at {GROUNDING_DIR}. Using mock trials.")
        return _mock_vision_trials()

    category_briefs = {
        "warehouse": "A tense confrontation in a dimly lit warehouse at night.",
        "golden_hour_street": "Two people sharing a quiet moment during golden hour on a city street.",
        "fluorescent_office": "A bright fluorescent office space with cubicles and harsh lighting.",
        "neon_alley": "A colorful neon alley at night with reflective wet pavement.",
        "forest_clearing": "A sunlit forest clearing with rays of light breaking through the canopy.",
        "hospital_corridor": "A long hospital corridor with fluorescent lighting and distant beeping monitors.",
        "subway_car": "A crowded subway car during rush hour with passengers holding onto straps.",
        "rooftop_sunset": "A rooftop overlooking a city skyline at sunset with warm golden light.",
    }

    trials: list[VisionTrial] = []
    for category_dir in sorted(GROUNDING_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        relevant = category_dir / "relevant.jpg"
        if not relevant.exists():
            continue

        brief = category_briefs.get(category_dir.name, f"A scene typical of {category_dir.name.replace('_', ' ')}.")
        trials.append(
            VisionTrial(
                id=category_dir.name,
                title=category_dir.name.replace("_", " ").title(),
                brief=brief,
                reference_image=str(relevant),
            )
        )
    if not trials:
        return _mock_vision_trials()
    return trials


def _mock_vision_trials() -> list[VisionTrial]:
    return [
        VisionTrial(
            id="mock_warehouse",
            title="Mock Warehouse",
            brief="A tense confrontation in a dimly lit warehouse at night.",
            reference_image="data/images/grounding/warehouse/relevant.jpg",
        ),
    ]


def bootstrap_mean_ci(deltas: list[float], n_samples: int = 5000, alpha: float = 0.05) -> tuple[float, float]:
    if not deltas:
        return 0.0, 0.0
    boots = np.random.choice(deltas, size=(n_samples, len(deltas)), replace=True)
    means = boots.mean(axis=1)
    lower = float(np.percentile(means, 100 * alpha / 2))
    upper = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return lower, upper


async def run_text_only_loop(brief: str) -> dict[str, float | int | str]:
    gateway = ModelGateway(GatewayLedger())
    rubric = Rubric()
    loop = CorrectionLoop(
        gateway=gateway,
        rubric=rubric,
        max_turns=3,
        threshold=999.0,
        plateau_epsilon=-1.0,
    )
    trace = await loop.run(brief)
    return {
        "overall": trace.steps[-1].critique.overall if trace.steps else 0.0,
        "cost_usd": trace.total_cost_usd,
        "latency_ms": trace.total_latency_ms,
        "turns": len(trace.steps),
        "stop_reason": trace.stop_reason or "unknown",
        "final_output": trace.final_output or "",
    }


async def run_vision_loop(brief: str, reference_image: str) -> dict[str, float | int | str]:
    gateway = ModelGateway(GatewayLedger())
    rubric = Rubric()
    loop = CorrectionLoop(
        gateway=gateway,
        rubric=rubric,
        max_turns=3,
        threshold=999.0,
        plateau_epsilon=-1.0,
    )
    trace = await loop.run(
        brief,
        reference_images=[ReferenceImage(path=reference_image, caption="Reference image")],
    )
    return {
        "overall": trace.steps[-1].critique.overall if trace.steps else 0.0,
        "cost_usd": trace.total_cost_usd,
        "latency_ms": trace.total_latency_ms,
        "turns": len(trace.steps),
        "stop_reason": trace.stop_reason or "unknown",
        "final_output": trace.final_output or "",
    }


async def run_experiment(trials: list[VisionTrial]) -> dict:
    results: list[dict] = []
    for trial in trials:
        print(f"Running Phase 4 trial: {trial.id} - {trial.title}")
        text_result = await run_text_only_loop(trial.brief)
        vision_result = await run_vision_loop(trial.brief, trial.reference_image)
        results.append(
            {
                "id": trial.id,
                "title": trial.title,
                "brief": trial.brief,
                "reference_image": trial.reference_image,
                "text_only": text_result,
                "vision": vision_result,
                "delta_overall": float(vision_result["overall"] - text_result["overall"]),
                "cost_ratio": float(vision_result["cost_usd"] / text_result["cost_usd"]) if text_result["cost_usd"] > 0 else float("inf"),
            }
        )
    return {"trials": results}


def analyze(results: dict) -> dict:
    trials = results["trials"]
    deltas = [trial["delta_overall"] for trial in trials]
    text_costs = [trial["text_only"]["cost_usd"] for trial in trials]
    vision_costs = [trial["vision"]["cost_usd"] for trial in trials]

    mean_delta = float(np.mean(deltas)) if deltas else 0.0
    median_delta = float(np.median(deltas)) if deltas else 0.0
    ci_lower, ci_upper = bootstrap_mean_ci(deltas)
    cost_ratio = float(np.mean(vision_costs) / np.mean(text_costs)) if text_costs and np.mean(text_costs) > 0 else 0.0

    if len(deltas) > 1:
        stat, p_value = stats.wilcoxon(deltas)
    else:
        stat, p_value = float("nan"), float("nan")

    return {
        "mean_delta": mean_delta,
        "median_delta": median_delta,
        "bootstrap_ci": {"lower": ci_lower, "upper": ci_upper},
        "wilcoxon": {"statistic": float(stat), "p_value": float(p_value)},
        "mean_text_cost": float(np.mean(text_costs)) if text_costs else 0.0,
        "mean_vision_cost": float(np.mean(vision_costs)) if vision_costs else 0.0,
        "cost_ratio": cost_ratio,
    }


def save_results(results: dict, analysis: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "phase4_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "analysis": analysis}, f, indent=2)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 4 Vision Effectiveness\n\n")
        f.write("This report compares text-only correction loops against vision-grounded correction loops using the Phase 4 trial set.\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Mean vision minus text overall delta: {analysis['mean_delta']:.3f}\n")
        f.write(f"- Median delta: {analysis['median_delta']:.3f}\n")
        f.write(f"- Bootstrap 95% CI: [{analysis['bootstrap_ci']['lower']:.3f}, {analysis['bootstrap_ci']['upper']:.3f}]\n")
        f.write(f"- Wilcoxon signed-rank p-value: {analysis['wilcoxon']['p_value']:.4f}\n")
        f.write(f"- Mean text-only cost: ${analysis['mean_text_cost']:.4f}\n")
        f.write(f"- Mean vision cost: ${analysis['mean_vision_cost']:.4f}\n")
        f.write(f"- Mean cost ratio (vision/text): {analysis['cost_ratio']:.3f}x\n")
        f.write("\n## Notes\n\n")
        f.write("- The script runs two full correction loops per trial.\n")
        f.write("- Text-only uses no reference images. Vision uses a single relevant reference image for each brief.\n")
        f.write("- This is a within-brief paired evaluation.\n")

    print(f"Saved Phase 4 analysis to {REPORT_PATH}")


async def main() -> None:
    configure_logging()
    trials = load_vision_trials()
    print(f"Loaded {len(trials)} Phase 4 trials")
    results = await run_experiment(trials)
    analysis = analyze(results)
    save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())
