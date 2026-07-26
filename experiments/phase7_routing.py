"""Experiments/phase7_routing.py

Phase 7: Cost-aware model routing (text).

This script compares three regimes on the Phase 1 brief set:
  1. cheap default only
  2. expensive-only baseline
  3. adaptive escalation based on Phase 7 routing rules

The point is not to prove a specific model wins, but to make the cost-
quality tradeoff visible and grounded in the same brief set the harness
uses throughout Phase 3/4/5.
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
from app.gateway import GatewayLedger, ModelGateway, TASK_DEFAULT_MODEL
from app.rubric import Rubric
from app.routing import AdaptiveRouter

DATA_DIR = Path("data")
BRIEFS_PATH = DATA_DIR / "briefs" / "phase1_briefs.json"
RESULTS_DIR = DATA_DIR / "results"
REPORT_PATH = Path("PHASE7_ROUTING_FINDINGS.md")
CHART_PATH = Path("docs") / "phase7_quality_vs_cost.png"


@dataclass
class BriefEntry:
    id: str
    title: str
    brief: str


def load_phase1_briefs() -> list[BriefEntry]:
    with BRIEFS_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [BriefEntry(id=item["id"], title=item["title"], brief=item["brief"]) for item in raw]


async def run_config(config_name: str, brief: str, router: AdaptiveRouter | None = None, model_overrides: dict[str, str] | None = None):
    gateway = ModelGateway(GatewayLedger())
    rubric = Rubric()
    loop = CorrectionLoop(
        gateway=gateway,
        rubric=rubric,
        router=router,
        model_overrides=model_overrides,
        max_turns=3,
        threshold=999.0,
        plateau_epsilon=-1.0,
    )
    trace = await loop.run(brief)
    return {
        "config": config_name,
        "overall": trace.steps[-1].critique.overall if trace.steps else 0.0,
        "cost_usd": trace.total_cost_usd,
        "latency_ms": trace.total_latency_ms,
        "turns": len(trace.steps),
        "trace": trace.model_dump()
    }


async def evaluate_briefs(briefs: list[BriefEntry]) -> dict:
    adaptive_router = AdaptiveRouter.load_from_file(Path("config") / "routing_rules.yaml")
    results = []
    for item in briefs:
        print(f"Running Phase 7 trial: {item.id} ({item.title})")
        cheap = await run_config("cheap", item.brief, model_overrides={
            "draft": TASK_DEFAULT_MODEL["draft"],
            "critique": TASK_DEFAULT_MODEL["critique"],
            "revise": TASK_DEFAULT_MODEL["revise"],
        })
        expensive = await run_config("expensive", item.brief, model_overrides={
            "draft": TASK_DEFAULT_MODEL.get("critique", TASK_DEFAULT_MODEL["draft"]),
            "critique": TASK_DEFAULT_MODEL.get("critique", TASK_DEFAULT_MODEL["draft"]),
            "revise": TASK_DEFAULT_MODEL.get("critique", TASK_DEFAULT_MODEL["draft"]),
        })
        adaptive = await run_config("adaptive", item.brief, router=adaptive_router)
        results.append({
            "id": item.id,
            "title": item.title,
            "brief": item.brief,
            "cheap": cheap,
            "expensive": expensive,
            "adaptive": adaptive,
        })
    return {"trials": results}


def plot_quality_vs_cost(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    configs = ["cheap", "expensive", "adaptive"]
    for config in configs:
        xs = [trial[config]["cost_usd"] for trial in results["trials"]]
        ys = [trial[config]["overall"] for trial in results["trials"]]
        plt.scatter(xs, ys, label=config)
    plt.title("Phase 7: Quality vs Cost by Routing Regime")
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
    for config in ["cheap", "expensive", "adaptive"]:
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
    with open(RESULTS_DIR / "phase7_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "analysis": analysis}, f, indent=2)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 7 Routing Findings\n\n")
        f.write("This experiment compares cheap-only, expensive-only, and adaptive model routing on the Phase 1 brief set.\n\n")
        f.write("## Summary\n\n")
        for config, stats in analysis.items():
            f.write(f"- {config.title()}: mean overall={stats['mean_overall']:.3f}, mean cost=${stats['mean_cost']:.4f}\n")
        f.write("\n## Notes\n\n")
        f.write("- The adaptive regime uses the rules in `config/routing_rules.yaml`.\n")
        f.write("- The chart `docs/phase7_quality_vs_cost.png` plots each brief as a point.\n")
        f.write("- This script is intentionally runnable in mock mode for local integration testing.\n")

    print(f"Saved Phase 7 results to {RESULTS_DIR / 'phase7_results.json'}")
    print(f"Saved Phase 7 chart to {CHART_PATH}")
    print(f"Saved Phase 7 report to {REPORT_PATH}")


async def main() -> None:
    briefs = load_phase1_briefs()
    results = await evaluate_briefs(briefs)
    analysis = analyze(results)
    plot_quality_vs_cost(results)
    save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())
