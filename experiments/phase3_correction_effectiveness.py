"""Experiments/phase3_correction_effectiveness.py

Phase 3: Text correction-loop effectiveness study.

Compare the quality and cost of a single-pass pipeline against a full 3-turn
correction loop using the Phase 1 brief set. This script computes paired deltas,
bootstrap 95% confidence intervals, and simple cost ratios.
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


DATA_DIR = Path("data")
BRIEFS_PATH = DATA_DIR / "briefs" / "phase1_briefs.json"
RESULTS_DIR = DATA_DIR / "results"
REPORT_PATH = Path("PHASE3_CORRECTION_EFFECTIVENESS.md")


@dataclass
class BriefEntry:
    id: str
    title: str
    brief: str


def load_phase1_briefs() -> list[BriefEntry]:
    if not BRIEFS_PATH.exists():
        raise FileNotFoundError(f"Phase 1 briefs not found: {BRIEFS_PATH}")

    with BRIEFS_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return [BriefEntry(id=item["id"], title=item["title"], brief=item["brief"]) for item in raw]


def bootstrap_mean_ci(deltas: list[float], n_samples: int = 5000, alpha: float = 0.05) -> tuple[float, float]:
    if not deltas:
        return 0.0, 0.0
    boots = np.random.choice(deltas, size=(n_samples, len(deltas)), replace=True)
    means = boots.mean(axis=1)
    lower = float(np.percentile(means, 100 * alpha / 2))
    upper = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return lower, upper


async def run_single_pass(gateway: ModelGateway, rubric: Rubric, brief: str):
    loop = CorrectionLoop(
        gateway=gateway,
        rubric=rubric,
        max_turns=1,
        threshold=999.0,
        plateau_epsilon=-1.0,
    )
    return await loop.run(brief)


async def run_three_turn_loop(gateway: ModelGateway, rubric: Rubric, brief: str):
    loop = CorrectionLoop(
        gateway=gateway,
        rubric=rubric,
        max_turns=3,
        threshold=999.0,
        plateau_epsilon=-1.0,
    )
    return await loop.run(brief)


async def evaluate_briefs(briefs: list[BriefEntry]) -> dict:
    results = []
    for item in briefs:
        print(f"Running Phase 3 trial: {item.id} ({item.title})")
        gateway = ModelGateway(GatewayLedger())
        rubric = Rubric()

        single = await run_single_pass(gateway, rubric, item.brief)
        # Create a fresh gateway/rubric for the loop so metrics are independent.
        loop_gateway = ModelGateway(GatewayLedger())
        loop_rubric = Rubric()
        full_loop = await run_three_turn_loop(loop_gateway, loop_rubric, item.brief)

        results.append({
            "id": item.id,
            "title": item.title,
            "brief": item.brief,
            "single": {
                "overall": single.steps[0].critique.overall if single.steps else 0.0,
                "cost_usd": single.total_cost_usd,
                "latency_ms": single.total_latency_ms,
                "turns": len(single.steps),
                "final_output": single.final_output or "",
            },
            "loop": {
                "overall": full_loop.steps[-1].critique.overall if full_loop.steps else 0.0,
                "cost_usd": full_loop.total_cost_usd,
                "latency_ms": full_loop.total_latency_ms,
                "turns": len(full_loop.steps),
                "final_output": full_loop.final_output or "",
            },
            "delta": (full_loop.steps[-1].critique.overall if full_loop.steps else 0.0)
                     - (single.steps[0].critique.overall if single.steps else 0.0),
        })

    return {"trials": results}


def analyze(results: dict) -> dict:
    trials = results["trials"]
    deltas = [item["delta"] for item in trials]
    costs_single = [item["single"]["cost_usd"] for item in trials]
    costs_loop = [item["loop"]["cost_usd"] for item in trials]

    mean_delta = float(np.mean(deltas)) if deltas else 0.0
    median_delta = float(np.median(deltas)) if deltas else 0.0
    ci_lower, ci_upper = bootstrap_mean_ci(deltas)

    if len(deltas) > 1:
        t_stat, t_p = stats.ttest_rel([item["loop"]["overall"] for item in trials], [item["single"]["overall"] for item in trials])
        wilcoxon_stat, wilcoxon_p = stats.wilcoxon([item["loop"]["overall"] for item in trials], [item["single"]["overall"] for item in trials])
    else:
        t_stat = float("nan")
        t_p = float("nan")
        wilcoxon_stat = float("nan")
        wilcoxon_p = float("nan")

    cost_ratio = float(np.mean(costs_loop) / np.mean(costs_single)) if costs_single and np.mean(costs_single) > 0 else 0.0

    return {
        "mean_delta": mean_delta,
        "median_delta": median_delta,
        "bootstrap_ci": {"lower": ci_lower, "upper": ci_upper},
        "t_test": {"statistic": float(t_stat), "p_value": float(t_p)},
        "wilcoxon": {"statistic": float(wilcoxon_stat), "p_value": float(wilcoxon_p)},
        "cost_ratio": cost_ratio,
        "summary": {
            "mean_single_cost": float(np.mean(costs_single)) if costs_single else 0.0,
            "mean_loop_cost": float(np.mean(costs_loop)) if costs_loop else 0.0,
            "mean_single_latency_ms": float(np.mean([item["single"]["latency_ms"] for item in trials])) if trials else 0.0,
            "mean_loop_latency_ms": float(np.mean([item["loop"]["latency_ms"] for item in trials])) if trials else 0.0,
        },
    }


def save_results(results: dict, analysis: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "phase3_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "analysis": analysis}, f, indent=2)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 3 Correction Effectiveness\n\n")
        f.write("This report compares a single-pass draft + critique flow against a full 3-turn correction loop on the Phase 1 brief set.\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Mean loop vs single-pass delta: {analysis['mean_delta']:.3f}\n")
        f.write(f"- Median delta: {analysis['median_delta']:.3f}\n")
        f.write(f"- Bootstrap 95% CI on mean delta: [{analysis['bootstrap_ci']['lower']:.3f}, {analysis['bootstrap_ci']['upper']:.3f}]\n")
        f.write(f"- Paired t-test p-value: {analysis['t_test']['p_value']:.4f}\n")
        f.write(f"- Wilcoxon signed-rank p-value: {analysis['wilcoxon']['p_value']:.4f}\n")
        f.write(f"- Mean cost ratio (loop / single): {analysis['cost_ratio']:.3f}x\n")
        f.write("\n## Notes\n\n")
        f.write("- The experiment uses the Phase 1 brief set from `data/briefs/phase1_briefs.json`.\n")
        f.write("- Single-pass is implemented as a one-turn run followed by its critique.\n")
        f.write("- Full correction loop is allowed up to 3 turns with plateau detection disabled so the loop completes through the turn limit.\n")
        f.write("- This script is intentionally runnable in mock mode for local integration testing.\n")

    print(f"Saved results to {RESULTS_DIR / 'phase3_results.json'}")
    print(f"Saved report to {REPORT_PATH}")


async def main() -> None:
    configure_logging()
    briefs = load_phase1_briefs()
    results = await evaluate_briefs(briefs)
    analysis = analyze(results)
    save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())
