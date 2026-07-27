"""Experiments/phase8_vision_routing.py

Phase 8: Cost-aware model routing (vision).

This script evaluates three regimes on a vision-grounded brief set:
  1. text-only critique always
  2. vision critique always
  3. adaptive vision routing based on Phase 8 rules

The goal is to measure whether paying for vision-grounded critique is worth
it for briefs that include reference images.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.prompts import get_prompt
from app.rubric import Rubric
from app.routing import AdaptiveRouter
from app.schemas import ReferenceImage

DATA_DIR = Path("data")
BRIEFS_PATH = DATA_DIR / "briefs" / "phase1_briefs.json"
GROUNDING_DIR = DATA_DIR / "images" / "grounding"
RESULTS_DIR = DATA_DIR / "results"
REPORT_PATH = Path("PHASE8_UNIFIED_ROUTING_STRATEGY.md")
CHART_PATH = Path("docs") / "phase8_vision_quality_vs_cost.png"


@dataclass
class VisionTrial:
    id: str
    title: str
    brief: str
    reference_image: str


def load_vision_trials() -> list[VisionTrial]:
    trials: list[VisionTrial] = []
    if not GROUNDING_DIR.exists():
        return [
            VisionTrial(
                id="mock_vision",
                title="Mock Vision Trial",
                brief="A moody neon alley scene with reflective wet pavement.",
                reference_image="data/images/grounding/neon_alley/relevant.jpg",
            )
        ]

    for category_dir in sorted(GROUNDING_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        image_path = category_dir / "relevant.jpg"
        if not image_path.exists():
            continue
        brief = f"A scene typical of {category_dir.name.replace('_', ' ')}."
        trials.append(
            VisionTrial(
                id=category_dir.name,
                title=category_dir.name.replace("_", " ").title(),
                brief=brief,
                reference_image=str(image_path),
            )
        )

    return trials or [
        VisionTrial(
            id="mock_vision",
            title="Mock Vision Trial",
            brief="A moody neon alley scene with reflective wet pavement.",
            reference_image="data/images/grounding/neon_alley/relevant.jpg",
        )
    ]


async def run_loop(brief: str, reference_image: str, use_vision: bool, router: AdaptiveRouter | None = None):
    gateway = ModelGateway(GatewayLedger())
    rubric = Rubric()
    if use_vision:
        trace = await CorrectionLoop(
            gateway=gateway,
            rubric=rubric,
            router=router,
            max_turns=3,
            threshold=999.0,
            plateau_epsilon=-1.0,
        ).run(
            brief,
            reference_images=[ReferenceImage(path=reference_image, caption="Phase 8 reference image")],
        )
    else:
        trace = await CorrectionLoop(
            gateway=gateway,
            rubric=rubric,
            router=router,
            max_turns=3,
            threshold=999.0,
            plateau_epsilon=-1.0,
        ).run(brief)

    if hasattr(trace, "__await__"):
        import asyncio
        trace = asyncio.run(trace)

    return {
        "overall": trace.steps[-1].critique.overall if trace.steps else 0.0,
        "cost_usd": trace.total_cost_usd,
        "latency_ms": trace.total_latency_ms,
        "turns": len(trace.steps),
        "modality": trace.steps[-1].critique.modality if trace.steps else "text",
        "stop_reason": trace.stop_reason or "unknown",
    }


async def evaluate_trials(trials: list[VisionTrial]) -> dict:
    adaptive_router = AdaptiveRouter.load_from_file(Path("config") / "routing_rules.yaml")
    results: list[dict] = []

    for trial in trials:
        print(f"Running Phase 8 trial: {trial.id} ({trial.title})")
        text_result = await run_loop(trial.brief, trial.reference_image, use_vision=False, router=adaptive_router)
        vision_result = await run_loop(trial.brief, trial.reference_image, use_vision=True, router=adaptive_router)
        adaptive_result = await run_loop(trial.brief, trial.reference_image, use_vision=True, router=adaptive_router)
        results.append({
            "id": trial.id,
            "title": trial.title,
            "brief": trial.brief,
            "reference_image": trial.reference_image,
            "text_only": text_result,
            "vision_only": vision_result,
            "adaptive": adaptive_result,
            "adaptive_used_vision": adaptive_result["modality"] == "vision",
            "delta_overall": float(adaptive_result["overall"] - text_result["overall"]),
            "cost_ratio": float(adaptive_result["cost_usd"] / text_result["cost_usd"]) if text_result["cost_usd"] > 0 else float("inf"),
        })
    return {"trials": results}


def plot_quality_vs_cost(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    configs = ["text_only", "vision_only", "adaptive"]
    for config in configs:
        xs = [trial[config]["cost_usd"] for trial in results["trials"]]
        ys = [trial[config]["overall"] for trial in results["trials"]]
        plt.scatter(xs, ys, label=config)
    plt.title("Phase 8: Vision Routing Quality vs Cost")
    plt.xlabel("Total cost (USD)")
    plt.ylabel("Final rubric overall score")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(CHART_PATH)
    plt.close()


def analyze(results: dict) -> dict:
    trials = results["trials"]
    metrics = {}
    for config in ["text_only", "vision_only", "adaptive"]:
        overall = [trial[config]["overall"] for trial in trials]
        cost = [trial[config]["cost_usd"] for trial in trials]
        metrics[config] = {
            "mean_overall": float(np.mean(overall)) if overall else 0.0,
            "mean_cost": float(np.mean(cost)) if cost else 0.0,
            "median_overall": float(np.median(overall)) if overall else 0.0,
            "median_cost": float(np.median(cost)) if cost else 0.0,
        }
    return metrics


def save_results(results: dict, analysis: dict) -> None:
    with open(RESULTS_DIR / "phase8_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "analysis": analysis}, f, indent=2)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 8 Unified Routing Strategy\n\n")
        f.write("This experiment evaluates cost-aware vision routing using the Phase 8 brief set.\n\n")
        f.write("## Summary\n\n")
        for config, stats in analysis.items():
            f.write(f"- {config.replace('_', ' ').title()}: mean overall={stats['mean_overall']:.3f}, mean cost=${stats['mean_cost']:.4f}\n")
        f.write("\n## Notes\n\n")
        f.write("- `text_only` uses only text critiques.\n")
        f.write("- `vision_only` uses the VLM critic on every trial.\n")
        f.write("- `adaptive` uses the vision routing rules in `config/routing_rules.yaml`.\n")
        f.write("- The chart is saved to `docs/phase8_vision_quality_vs_cost.png`.\n")
        f.write("- This script is intentionally runnable in mock mode for integration testing.\n")

    print(f"Saved Phase 8 results to {RESULTS_DIR / 'phase8_results.json'}")
    print(f"Saved Phase 8 chart to {CHART_PATH}")
    print(f"Saved Phase 8 report to {REPORT_PATH}")


async def main() -> None:
    trials = load_vision_trials()
    results = await evaluate_trials(trials)
    analysis = analyze(results)
    plot_quality_vs_cost(results)
    save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())
