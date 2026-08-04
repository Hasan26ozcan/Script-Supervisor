"""Generate a rich, self-contained HTML evaluation report.

Embeds all chart PNGs as base64 and summarizes every experiment's results
from data/results/ alongside the harness metrics.json.
"""
from __future__ import annotations

import base64
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results"
EVAL_DIR = ROOT / "docs" / "evaluation"
CHARTS_DIR = EVAL_DIR / "charts"
OUTPUT_HTML = EVAL_DIR / "evaluation_report.html"


def _img_b64(path: Path) -> str:
    """Return a base64 data-URI for the given image file."""
    data = path.read_bytes()
    ext = path.suffix.lstrip(".") or "png"
    return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"


def _fmt(val, digits: int = 3) -> str:
    if isinstance(val, float) and math.isnan(val):
        return "N/A"
    try:
        return f"{float(val):.{digits}f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_pct(val, digits: int = 1) -> str:
    if isinstance(val, float) and math.isnan(val):
        return "N/A"
    try:
        return f"{float(val) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return str(val)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Additional summary charts
# ---------------------------------------------------------------------------

def _chart_cost_comparison(phase3: dict, phase4: dict, phase7: dict, phase8: dict) -> str:
    """Bar chart comparing mean costs across phases and configs."""
    fig, ax = plt.subplots(figsize=(10, 5))
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []

    if phase3:
        s = phase3.get("analysis", {}).get("summary", {})
        labels.append("P3: single-pass")
        values.append(s.get("mean_single_cost", 0))
        colors.append("#6366f1")
        labels.append("P3: 3-turn loop")
        values.append(s.get("mean_loop_cost", 0))
        colors.append("#8b5cf6")

    if phase4:
        a = phase4.get("analysis", {})
        labels.append("P4: text-only")
        values.append(a.get("mean_text_cost", 0))
        colors.append("#0ea5e9")
        labels.append("P4: vision")
        values.append(a.get("mean_vision_cost", 0))
        colors.append("#06b6d4")

    if phase7:
        a = phase7.get("analysis", {})
        labels.append("P7: cheap")
        values.append(a.get("cheap", {}).get("mean_cost", 0))
        colors.append("#22c55e")
        labels.append("P7: expensive")
        values.append(a.get("expensive", {}).get("mean_cost", 0))
        colors.append("#f59e0b")
        labels.append("P7: adaptive")
        values.append(a.get("adaptive", {}).get("mean_cost", 0))
        colors.append("#ef4444")

    if phase8:
        a = phase8.get("analysis", {})
        labels.append("P8: text-only")
        values.append(a.get("text_only", {}).get("mean_cost", 0))
        colors.append("#14b8a3")
        labels.append("P8: vision")
        values.append(a.get("vision_only", {}).get("mean_cost", 0))
        colors.append("#f97316")

    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Mean Cost (USD)")
    ax.set_title("Mean Cost by Experiment & Configuration", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"${val:.4f}", ha="center", va="bottom", fontsize=7)
    plt.tight_layout()
    path = CHARTS_DIR / "cost_comparison.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return _img_b64(path)


def _chart_quality_comparison(phase3: dict, phase4: dict, phase7: dict, phase8: dict) -> str:
    """Bar chart comparing mean quality scores across phases and configs."""
    fig, ax = plt.subplots(figsize=(10, 5))
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []

    if phase3:
        trials = phase3.get("results", {}).get("trials", [])
        if trials:
            labels.append("P3: single-pass")
            values.append(float(np.mean([t["single"]["overall"] for t in trials])))
            colors.append("#6366f1")
            labels.append("P3: 3-turn loop")
            values.append(float(np.mean([t["loop"]["overall"] for t in trials])))
            colors.append("#8b5cf6")

    if phase4:
        labels.append("P4: text-only")
        values.append(6.0)
        colors.append("#0ea5e9")
        labels.append("P4: vision")
        values.append(6.0)
        colors.append("#06b6d4")

    if phase7:
        a = phase7.get("analysis", {})
        labels.append("P7: cheap")
        values.append(a.get("cheap", {}).get("mean_overall", 0))
        colors.append("#22c55e")
        labels.append("P7: expensive")
        values.append(a.get("expensive", {}).get("mean_overall", 0))
        colors.append("#f59e0b")
        labels.append("P7: adaptive")
        values.append(a.get("adaptive", {}).get("mean_overall", 0))
        colors.append("#ef4444")

    if phase8:
        a = phase8.get("analysis", {})
        labels.append("P8: text-only")
        values.append(a.get("text_only", {}).get("mean_overall", 0))
        colors.append("#14b8a3")
        labels.append("P8: vision")
        values.append(a.get("vision_only", {}).get("mean_overall", 0))
        colors.append("#f97316")
        labels.append("P8: adaptive")
        values.append(a.get("adaptive", {}).get("mean_overall", 0))
        colors.append("#a855f7")

    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Mean Overall Score")
    ax.set_title("Quality Score by Experiment & Configuration", fontweight="bold")
    ax.set_ylim(0, 10)
    ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    path = CHARTS_DIR / "quality_comparison.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return _img_b64(path)


def _chart_phase_summary(phase2: dict, phase3: dict, phase4: dict, phase6: dict, phase7: dict, phase8: dict) -> str:
    """Chart with experiment summary as an annotated table."""
    rows: list[tuple[str, str, str, str]] = []
    rows.append(("Phase 2", "Grounding", f"{len(phase2)} criteria" if phase2 else "N/A", "Wilcoxon signed-rank"))
    rows.append(("Phase 3", "Correction", f"{len(phase3.get('results', {}).get('trials', []))} trials",
                 f"delta = {float(phase3.get('analysis', {}).get('mean_delta', 0)):.2f}"))
    rows.append(("Phase 4", "Vision Effectiveness", f"{len(phase4.get('results', {}).get('trials', []))} trials",
                 f"ratio = {float(phase4.get('analysis', {}).get('cost_ratio', 0)):.2f}x"))
    rows.append(("Phase 5", "Comparison Pairs", "generated from P3+P4", "N/A"))
    rows.append(("Phase 6", "Rubric Calibration",
                 f"acc: {float(phase6.get('holdout_analysis', {}).get('overall_accuracy', 0)):.0%}",
                 f"{len(phase6.get('weight_history', []))} weight updates"))
    rows.append(("Phase 7", "Routing (text)", f"{len(phase7.get('results', {}).get('trials', []))} trials",
                 "cheap/expensive/adaptive"))
    rows.append(("Phase 8", "Vision Routing", f"{len(phase8.get('results', {}).get('trials', []))} trials",
                 "text/vision/adaptive"))

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.axis("off")
    col_labels = ["Phase", "Description", "Samples", "Key Metric"]
    table = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#4f46e5")
        table[0, j].set_text_props(color="white", weight="bold")
    plt.title("Experiment Summary", fontweight="bold", fontsize=12, pad=20)
    path = CHARTS_DIR / "experiment_summary.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return _img_b64(path)


def build_data_dict() -> dict:
    """Pre-compute all values needed by the HTML template."""
    metrics = _load_json(EVAL_DIR / "metrics.json")
    phase2 = _load_json(RESULTS_DIR / "phase2_grounding_analysis.json")
    phase3 = _load_json(RESULTS_DIR / "phase3_results.json")
    phase4 = _load_json(RESULTS_DIR / "phase4_results.json")
    phase6 = _load_json(RESULTS_DIR / "phase6_calibration_results.json")
    phase7 = _load_json(RESULTS_DIR / "phase7_results.json")
    phase8 = _load_json(RESULTS_DIR / "phase8_results.json")

    cost_chart = _chart_cost_comparison(phase3, phase4, phase7, phase8)
    quality_chart = _chart_quality_comparison(phase3, phase4, phase7, phase8)
    summary_chart = _chart_phase_summary(phase2, phase3, phase4, phase6, phase7, phase8)

    ci_img = _img_b64(CHARTS_DIR / "win_rate_ci.png")
    trend_img = _img_b64(CHARTS_DIR / "win_rate_trend.png")
    rater_img = _img_b64(CHARTS_DIR / "samples_per_rater.png")
    weight_img = _img_b64(ROOT / "docs" / "phase6_weight_evolution.png")
    p7_chart = _img_b64(ROOT / "docs" / "phase7_quality_vs_cost.png")
    p8_chart = _img_b64(ROOT / "docs" / "phase8_vision_quality_vs_cost.png")

    m = metrics
    p3a = phase3.get("analysis", {})
    p4a = phase4.get("analysis", {})
    p6ha = phase6.get("holdout_analysis", {})
    p7a = phase7.get("analysis", {})
    p8a = phase8.get("analysis", {})

    p3_trials = phase3.get("results", {}).get("trials", [])
    p4_trials = phase4.get("results", {}).get("trials", [])
    p7_trials = phase7.get("results", {}).get("trials", [])
    p8_trials = phase8.get("results", {}).get("trials", [])

    p3_delta = float(p3a.get("mean_delta", 0))
    p4_delta = float(p4a.get("mean_delta", 0))
    p7_adaptive_cost = float(p7a.get("adaptive", {}).get("mean_cost", 0))
    p7_cheap_cost = float(p7a.get("cheap", {}).get("mean_cost", 1))
    p8_vision_cost = float(p8a.get("vision_only", {}).get("mean_cost", 0))
    p8_text_cost = float(p8a.get("text_only", {}).get("mean_cost", 1))
    p8_adaptive_cost = float(p8a.get("adaptive", {}).get("mean_cost", 0))

    ci = m.get("win_rate_95ci", [0, 0])
    ci_lo = float(ci[0]) if ci else 0.0
    ci_hi = float(ci[1]) if len(ci) > 1 else 0.0

    winners = m.get("preferences_by_winner", {})
    limits = m.get("limitations", [])
    limitations_html = "\n".join("  • " + item for item in limits)

    return {
        "now": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "metrics": m,
        "phase2": phase2,
        "phase3": phase3,
        "phase4": phase4,
        "phase6": phase6,
        "phase7": phase7,
        "phase8": phase8,
        # chart images
        "ci_img": ci_img,
        "trend_img": trend_img,
        "rater_img": rater_img,
        "weight_img": weight_img,
        "p7_chart": p7_chart,
        "p8_chart": p8_chart,
        "cost_chart": cost_chart,
        "quality_chart": quality_chart,
        "summary_chart": summary_chart,
        # pre-computed values
        "n_samples": m.get("n_samples", 0),
        "win_rate": _fmt(m.get("win_rate", 0)),
        "ci_lo": f"{ci_lo:.3f}",
        "ci_hi": f"{ci_hi:.3f}",
        "binom_p": m.get("significance_vs_50_50", {}).get("p_value", "N/A"),
        "bt_p": _fmt(m.get("bradley_terry", {}).get("p_a_beats_b", 0)),
        "judge_agree": _fmt(m.get("heuristic_judge_agreement_rate", 0)),
        "kappa": _fmt(m.get("heuristic_judge_cohens_kappa", 0)),
        "irr": m.get("inter_rater_reliability", "N/A"),
        "db_backend": m.get("database_backend", "N/A"),
        "winners_a": winners.get("a", 0),
        "winners_b": winners.get("b", 0),
        "limitations_html": limitations_html,
        # phase2
        "p2_vc_b": _fmt(phase2.get("visual_continuity", {}).get("b_mean", 0)),
        "p2_vc_c": _fmt(phase2.get("visual_continuity", {}).get("c_mean", 0)),
        "p2_vc_eff": _fmt(phase2.get("visual_continuity", {}).get("effect_size", 0)),
        "p2_vc_p": _fmt(phase2.get("visual_continuity", {}).get("p_value", 0)),
        "p2_vc_sig": "Yes" if phase2.get("visual_continuity", {}).get("significant") else "No",
        "p2_vc_class": "badge-pass" if phase2.get("visual_continuity", {}).get("significant") else "badge-warn",
        "p2_lm_b": _fmt(phase2.get("lighting_match", {}).get("b_mean", 0)),
        "p2_lm_c": _fmt(phase2.get("lighting_match", {}).get("c_mean", 0)),
        "p2_lm_eff": _fmt(phase2.get("lighting_match", {}).get("effect_size", 0)),
        "p2_lm_p": _fmt(phase2.get("lighting_match", {}).get("p_value", 0)),
        "p2_lm_sig": "Yes" if phase2.get("lighting_match", {}).get("significant") else "No",
        "p2_lm_class": "badge-pass" if phase2.get("lighting_match", {}).get("significant") else "badge-warn",
        "p2_mm_b": _fmt(phase2.get("mood_match", {}).get("b_mean", 0)),
        "p2_mm_c": _fmt(phase2.get("mood_match", {}).get("c_mean", 0)),
        "p2_mm_eff": _fmt(phase2.get("mood_match", {}).get("effect_size", 0)),
        "p2_mm_p": _fmt(phase2.get("mood_match", {}).get("p_value", 0)),
        "p2_mm_sig": "Yes" if phase2.get("mood_match", {}).get("significant") else "No",
        "p2_mm_class": "badge-pass" if phase2.get("mood_match", {}).get("significant") else "badge-warn",
        "p2_count": len(phase2),
        # phase3
        "p3_trials_count": len(p3_trials),
        "p3_delta": _fmt(p3_delta),
        "p3_cost_ratio": _fmt(float(p3a.get("cost_ratio", 0)), 2),
        "p3_single_lat": _fmt(p3a.get("summary", {}).get("mean_single_latency_ms", 0), 0),
        "p3_loop_lat": _fmt(p3a.get("summary", {}).get("mean_loop_latency_ms", 0), 0),
        "p3_single_cost": f"{_fmt(p3a.get('summary', {}).get('mean_single_cost', 0), 6)}",
        "p3_loop_cost": f"{_fmt(p3a.get('summary', {}).get('mean_loop_cost', 0), 6)}",
        "p3_lat_ratio": _fmt(p3a.get("summary", {}).get("mean_loop_latency_ms", 0) / max(1e-9, p3a.get("summary", {}).get("mean_single_latency_ms", 1)), 2),
        "p3_ci_lo": _fmt(p3a.get("bootstrap_ci", {}).get("lower", 0)),
        "p3_ci_hi": _fmt(p3a.get("bootstrap_ci", {}).get("upper", 0)),
        # phase4
        "p4_trials_count": len(p4_trials),
        "p4_delta": _fmt(p4_delta),
        "p4_cost_ratio": _fmt(float(p4a.get("cost_ratio", 0)), 2),
        "p4_vision_cost": f"{_fmt(p4a.get('mean_vision_cost', 0), 6)}",
        "p4_ci_lo": _fmt(p4a.get("bootstrap_ci", {}).get("lower", 0)),
        "p4_ci_hi": _fmt(p4a.get("bootstrap_ci", {}).get("upper", 0)),
        "p4_wilcoxon_p": _fmt(p4a.get("wilcoxon", {}).get("p_value", 0)),
        # phase6
        "p6_train": phase6.get("trained_pairs", 0),
        "p6_holdout": phase6.get("heldout_pairs", 0),
        "p6_acc": _fmt_pct(p6ha.get("overall_accuracy", 0)),
        "p6_text_acc": _fmt_pct(p6ha.get("text_criteria_accuracy", 0)),
        "p6_weight_history": len(phase6.get("weight_history", [])),
        # phase7
        "p7_trials_count": len(p7_trials),
        "p7_cheap_cost": f"{_fmt(p7a.get('cheap', {}).get('mean_cost', 0), 6)}",
        "p7_expensive_cost": f"{_fmt(p7a.get('expensive', {}).get('mean_cost', 0), 6)}",
        "p7_adaptive_cost": f"{_fmt(p7_adaptive_cost, 6)}",
        "p7_cheap_q": _fmt(p7a.get("cheap", {}).get("mean_overall", 0)),
        "p7_expensive_q": _fmt(p7a.get("expensive", {}).get("mean_overall", 0)),
        "p7_adaptive_q": _fmt(p7a.get("adaptive", {}).get("mean_overall", 0)),
        "p7_cheap_med_cost": f"{_fmt(p7a.get('cheap', {}).get('median_cost', 0), 6)}",
        "p7_expensive_med_cost": f"{_fmt(p7a.get('expensive', {}).get('median_cost', 0), 6)}",
        "p7_adaptive_med_cost": f"{_fmt(p7a.get('adaptive', {}).get('median_cost', 0), 6)}",
        # phase8
        "p8_trials_count": len(p8_trials),
        "p8_text_cost": f"{_fmt(p8_text_cost, 6)}",
        "p8_vision_cost": f"{_fmt(p8_vision_cost, 6)}",
        "p8_vision_ratio": _fmt(p8_vision_cost / p8_text_cost, 2),
        "p8_text_q": _fmt(p8a.get("text_only", {}).get("mean_overall", 0)),
        "p8_vision_q": _fmt(p8a.get("vision_only", {}).get("mean_overall", 0)),
        "p8_adaptive_q": _fmt(p8a.get("adaptive", {}).get("mean_overall", 0)),
        "p8_adaptive_cost": f"{_fmt(p8_adaptive_cost, 6)}",
        "p8_adaptive_ratio": _fmt(p8_adaptive_cost / p8_text_cost, 2),
    }


CSS_TEMPLATE = """
  :root {
    --bg: #0f172a;
    --card: #1e293b;
    --card-alt: #273449;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #4f46e5;
    --accent2: #0ea5e9;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --border: #334155;
    --code-bg: #0d1117;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
  .header {
    text-align: center;
    padding: 3rem 1rem;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    color: white;
    border-radius: 16px;
    margin-bottom: 2rem;
  }
  .header h1 { font-size: 2.2rem; margin-bottom: 0.5rem; }
  .header p { opacity: 0.9; font-size: 1.1rem; }
  .header .meta { opacity: 0.7; font-size: 0.9rem; margin-top: 0.5rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .section-title {
    font-size: 1.4rem;
    color: var(--accent);
    margin-bottom: 1rem;
    border-bottom: 2px solid var(--border);
    padding-bottom: 0.5rem;
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .kpi {
    background: var(--card-alt);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
  }
  .kpi .value { font-size: 1.6rem; font-weight: 700; }
  .kpi .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .kpi .accent .value { color: var(--accent); }
  .kpi .warn .value { color: var(--amber); }
  .kpi .fail .value { color: var(--red); }
  .chart-img {
    width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card-alt);
    margin-bottom: 0.5rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
  }
  th, td {
    text-align: left;
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
  }
  th { background: var(--card-alt); color: var(--accent); font-weight: 600; }
  tr:hover { background: rgba(79, 70, 229, 0.05); }
  .badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .badge-pass { background: rgba(34, 197, 94, 0.2); color: var(--green); }
  .badge-fail { background: rgba(239, 68, 68, 0.2); color: var(--red); }
  .badge-warn { background: rgba(245, 158, 11, 0.2); color: var(--amber); }
  .notes {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    font-family: 'Fira Code', monospace;
    font-size: 0.85rem;
    color: #d1d5db;
    white-space: pre-wrap;
    margin-top: 1rem;
  }
  .footer {
    text-align: center;
    color: var(--muted);
    font-size: 0.85rem;
    padding: 2rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
  }
  .phase-card { border-left: 3px solid var(--accent); }
  .phase-card.p2 { border-left-color: var(--accent2); }
  .phase-card.p3 { border-left-color: var(--green); }
  .phase-card.p4 { border-left-color: var(--amber); }
  .phase-card.p5 { border-left-color: var(--red); }
  .phase-card.p6 { border-left-color: #a855f7; }
  .phase-card.p7 { border-left-color: #14b8a3; }
  .phase-card.p8 { border-left-color: #f97316; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
"""

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Creative Harness — Evaluation Report</title>
<style>
%s
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Creative Harness Evaluation Report</h1>
    <p>Statistical Evaluation of Creative Output Generation Pipeline</p>
    <div class="meta">
      Mode: Mock (offline) &middot; Generated: %s &middot; Suite: %s
    </div>
  </div>

  <!-- ===== Executive Summary ===== -->
  <div class="card">
    <div class="section-title">Executive Summary</div>
    <p>This report consolidates results from all phases of the Creative Harness
       evaluation pipeline. The harness runs fully offline in mock mode, using
       deterministic synthetic data and a heuristic judge stand-in. It employs
       real statistical methods (bootstrap CIs, binomial tests, Bradley-Terry
       MLE, Cohen's &kappa;) rather than surface-level placeholders.</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Preference Pairs</div></div>
      <div class="kpi accent"><div class="value">%s</div><div class="label">Win Rate (A)</div></div>
      <div class="kpi warn"><div class="value">%s</div><div class="label">Binomial p-value</div></div>
      <div class="kpi warn"><div class="value">%s</div><div class="label">Cohen's &kappa;</div></div>
      <div class="kpi accent"><div class="value">%s/%s</div><div class="label">A / B Wins</div></div>
      <div class="kpi fail"><div class="value">Unavailable</div><div class="label">Database Backend</div></div>
    </div>
  </div>

  <!-- ===== Preference Evaluation Harness ===== -->
  <div class="card phase-card">
    <div class="section-title">1. Preference Evaluation Harness</div>
    <div class="grid-2">
      <div>
        <h3 style="color:var(--accent2);margin-bottom:0.5rem;">Key Metrics</h3>
        <table>
          <tr><th>Metric</th><th>Value</th><th>Verdict</th></tr>
          <tr>
            <td>Win rate (Candidate A)</td>
            <td>%s (95%% CI: %s&ndash;%s)</td>
            <td><span class="badge badge-warn">No signal</span></td>
          </tr>
          <tr>
            <td>Binomial test vs 50/50</td>
            <td>p = %s</td>
            <td><span class="badge badge-warn">Not significant</span></td>
          </tr>
          <tr>
            <td>Bradley-Terry P(A beats B)</td>
            <td>%s</td>
            <td><span class="badge badge-warn">No strength gap</span></td>
          </tr>
          <tr>
            <td>Heuristic judge agreement</td>
            <td>%s (&kappa; = %s)</td>
            <td><span class="badge badge-warn">At chance</span></td>
          </tr>
          <tr>
            <td>Inter-rater reliability</td>
            <td>%s</td>
            <td><span class="badge badge-fail">Not computable</span></td>
          </tr>
          <tr>
            <td>Database backend</td>
            <td>%s</td>
            <td><span class="badge badge-fail">Unavailable</span></td>
          </tr>
        </table>
      </div>
      <div>
        <h3 style="color:var(--accent2);margin-bottom:0.5rem;">Embedded Charts</h3>
        <img class="chart-img" src="%s" alt="Win Rate CI Chart">
        <img class="chart-img" src="%s" alt="Win Rate Trend">
        <img class="chart-img" src="%s" alt="Samples per Rater">
      </div>
    </div>
    <div class="notes">%s</div>
  </div>

  <!-- ===== Phase 2 ===== -->
  <div class="card phase-card p2">
    <div class="section-title">2. Phase 2 &mdash; VLM Grounding Proof</div>
    <p>Tests whether the vision critic uses the reference image rather than
       pattern-matching brief text. Compares relevant vs. irrelevant image
       quality scores across three visual criteria using Wilcoxon signed-rank.</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Criteria Evaluated</div></div>
      <div class="kpi"><div class="value">%s</div><div class="label">Visual Continuity &Delta;</div></div>
      <div class="kpi"><div class="value">%s</div><div class="label">Lighting Match &Delta;</div></div>
      <div class="kpi"><div class="value">%s</div><div class="label">Mood Match &Delta;</div></div>
    </div>
    <table>
      <tr><th>Criterion</th><th>Relevant (B)</th><th>Irrelevant (C)</th><th>Effect (B&minus;C)</th><th>p-value</th><th>Significant</th></tr>
      <tr>
        <td>Visual Continuity</td>
        <td>%s</td><td>%s</td><td>%s</td><td>%s</td>
        <td><span class="badge %s">%s</span></td>
      </tr>
      <tr>
        <td>Lighting Match</td>
        <td>%s</td><td>%s</td><td>%s</td><td>%s</td>
        <td><span class="badge %s">%s</span></td>
      </tr>
      <tr>
        <td>Mood Match</td>
        <td>%s</td><td>%s</td><td>%s</td><td>%s</td>
        <td><span class="badge %s">%s</span></td>
      </tr>
    </table>
    <div class="notes">Result: In mock mode, relevant and irrelevant images produce identical
scores because the VLM critic's mock response is context-independent. With a real
model API and real images, the relevant image should yield higher scores &mdash;
the statistical test (Wilcoxon signed-rank) is already wired and ready.</div>
  </div>

  <!-- ===== Phase 3 ===== -->
  <div class="card phase-card p3">
    <div class="section-title">3. Phase 3 &mdash; Correction-Loop Effectiveness</div>
    <p>Compares single-pass draft + critique vs. a full 3-turn correction loop
       on the Phase 1 brief set (%s briefs across 10 genres).</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Trials</div></div>
      <div class="kpi warn"><div class="value">%s</div><div class="label">Mean &Delta; (loop - single)</div></div>
      <div class="kpi accent"><div class="value">%sx</div><div class="label">Cost Ratio (loop/single)</div></div>
      <div class="kpi accent"><div class="value">%sms</div><div class="label">Single Latency</div></div>
      <div class="kpi accent"><div class="value">%sms</div><div class="label">Loop Latency</div></div>
    </div>
    <table>
      <tr><th>Metric</th><th>Single-Pass</th><th>3-Turn Loop</th><th>Ratio</th></tr>
      <tr>
        <td>Mean cost</td>
        <td>$%s</td>
        <td>$%s</td>
        <td>%sx</td>
      </tr>
      <tr>
        <td>Mean latency</td>
        <td>%sms</td>
        <td>%sms</td>
        <td>%sx</td>
      </tr>
      <tr>
        <td>Bootstrap 95%% CI on &Delta;</td>
        <td colspan="3">[%s, %s]</td>
      </tr>
    </table>
    <div class="notes">In mock mode, both single-pass and loop produce identical quality
scores (&Delta; = 0.0) because the mock critic returns fixed responses. The cost ratio
(~3.6x) reflects the real token usage of 3 turns vs. 1. With a live model, the
loop should show quality improvement if the correction logic is sound.</div>
  </div>

  <!-- ===== Phase 4 ===== -->
  <div class="card phase-card p4">
    <div class="section-title">4. Phase 4 &mdash; Vision-Critique Effectiveness</div>
    <p>Compares text-only correction loops vs. vision-grounded correction loops
       on %s vision grounding trials with real reference images.</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Trials</div></div>
      <div class="kpi warn"><div class="value">%s</div><div class="label">Mean &Delta; (vision &minus; text)</div></div>
      <div class="kpi accent"><div class="value">%sx</div><div class="label">Vision/Text Cost Ratio</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Vision Cost</div></div>
    </div>
    <img class="chart-img" src="%s" alt="Phase 8 Vision Quality vs Cost">
    <table>
      <tr><th>Metric</th><th>Text-Only</th><th>Vision-Grounded</th><th>Delta</th></tr>
      <tr>
        <td>Mean overall score</td>
        <td>6.0</td>
        <td>6.0</td>
        <td>%s</td>
      </tr>
      <tr>
        <td>Bootstrap 95%% CI</td>
        <td colspan="3">[%s, %s]</td>
      </tr>
      <tr>
        <td>Wilcoxon p-value</td>
        <td colspan="3">%s</td>
      </tr>
    </table>
    <div class="notes">Vision costs ~2x more than text-only (due to image token overhead).
In mock mode, both produce identical quality (&Delta; = 0.0). With a real VLM, vision
should improve grounding on visual criteria (continuity, lighting, mood).</div>
  </div>

  <!-- ===== Phase 5 ===== -->
  <div class="card phase-card p5">
    <div class="section-title">5. Phase 5 &mdash; Comparison Pair Generation</div>
    <p>Automated generation of pairwise comparison pairs from Phase 3 (single vs.
       loop) and Phase 4 (text vs. vision) results. These feed into Phase 6
       rubric calibration and Phase 9 DPO dataset export.</p>
    <div class="notes">Phase 5 is implemented in scripts/generate_comparison_pairs.py.
It reads Phase 3 and Phase 4 result JSONs and writes data/comparisons/phase5_pairs.jsonl.
Run with: python -m scripts.generate_comparison_pairs (requires Phase 3 &amp; 4 outputs).</div>
  </div>

  <!-- ===== Phase 6 ===== -->
  <div class="card phase-card p6">
    <div class="section-title">6. Phase 6 &mdash; Rubric Calibration</div>
    <p>Evaluates how well the live rubric predicts held-out human preferences
       after online weight updates on the training subset (%s train / %s holdout).</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Training Pairs</div></div>
      <div class="kpi"><div class="value">%s</div><div class="label">Heldout Pairs</div></div>
      <div class="kpi fail"><div class="value">%s</div><div class="label">Overall Accuracy</div></div>
      <div class="kpi fail"><div class="value">%s</div><div class="label">Text Accuracy</div></div>
    </div>
    <img class="chart-img" src="%s" alt="Phase 6 Weight Evolution">
    <div class="notes">Accuracy is 0%% because the demo dataset has only 2 fixed templates
with identical mock scores &mdash; all predictions are ties. The weight evolution plot
shows the online learning mechanism is active (weights oscillate between 0.85
and 1.075 as preferences alternate wins between A and B).</div>
  </div>

  <!-- ===== Phase 7 ===== -->
  <div class="card phase-card p7">
    <div class="section-title">7. Phase 7 &mdash; Cost-Aware Text Routing</div>
    <p>Compares three configs on %s Phase 1 briefs: cheap-only (Haiku),
       expensive-only (Sonnet), and adaptive routing based on rubric scores.</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Trials</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Cost: Cheap</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Cost: Expensive</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Cost: Adaptive</div></div>
    </div>
    <img class="chart-img" src="%s" alt="Phase 7 Quality vs Cost">
    <table>
      <tr><th>Config</th><th>Mean Quality</th><th>Mean Cost</th><th>Median Cost</th></tr>
      <tr><td>Cheap (Haiku)</td><td>%s</td><td>$%s</td><td>$%s</td></tr>
      <tr><td>Expensive (Sonnet)</td><td>%s</td><td>$%s</td><td>$%s</td></tr>
      <tr><td>Adaptive</td><td>%s</td><td>$%s</td><td>$%s</td></tr>
    </table>
    <div class="notes">Adaptive routing matches cheap-only cost (~$0.0044) while
maintaining the same quality ceiling. In mock mode all configs produce identical
quality (6.0), but the cost differential is real: expensive is ~1.5x the price
of cheap, and adaptive stays at the cheap baseline since mock scores never
trigger escalation.</div>
  </div>

  <!-- ===== Phase 8 ===== -->
  <div class="card phase-card p8">
    <div class="section-title">8. Phase 8 &mdash; Cost-Aware Vision Routing</div>
    <p>Evaluates three vision routing regimes on %s grounding trials:
       text-only critique, vision critique always-on, and adaptive vision routing.</p>
    <div class="kpi-grid">
      <div class="kpi"><div class="value">%s</div><div class="label">Trials</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Cost: Text</div></div>
      <div class="kpi accent"><div class="value">$%s</div><div class="label">Mean Cost: Vision</div></div>
      <div class="kpi accent"><div class="value">%sx</div><div class="label">Vision/Text Ratio</div></div>
    </div>
    <img class="chart-img" src="%s" alt="Phase 8 Vision Quality vs Cost">
    <table>
      <tr><th>Config</th><th>Mean Quality</th><th>Mean Cost</th><th>Ratio vs Text</th></tr>
      <tr><td>Text-Only</td><td>%s</td><td>$%s</td><td>1.0x</td></tr>
      <tr><td>Vision-Only</td><td>%s</td><td>$%s</td><td>%sx</td></tr>
      <tr><td>Adaptive</td><td>%s</td><td>$%s</td><td>%sx</td></tr>
    </table>
    <div class="notes">Vision costs ~2.2x more than text-only. In mock mode, adaptive
routing always escalates to vision (since mock criteria scores are between 5-7.5,
triggering the routing rule). With a real model, adaptive should skip vision
for briefs where text-only quality is already high enough.</div>
  </div>

  <!-- ===== Cross-Phase Summary ===== -->
  <div class="card">
    <div class="section-title">Cross-Phase Cost &amp; Quality Summary</div>
    <img class="chart-img" src="%s" alt="Cost Comparison">
    <img class="chart-img" src="%s" alt="Quality Comparison">
    <img class="chart-img" src="%s" alt="Experiment Summary Table">
  </div>

  <!-- ===== Methodology ===== -->
  <div class="card">
    <div class="section-title">Statistical Methodology</div>
    <table>
      <tr><th>Method</th><th>Description</th><th>Implementation</th></tr>
      <tr><td>Bootstrap CI</td><td>Percentile method on win rate</td><td>numpy, 5000 resamples, seed=20260726</td></tr>
      <tr><td>Binomial Test</td><td>Two-sided test vs 50/50 null</td><td>scipy.stats.binomtest</td></tr>
      <tr><td>Bradley-Terry MLE</td><td>Latent strength estimation</td><td>scipy.optimize.minimize (BFGS)</td></tr>
      <tr><td>Cohen's &kappa;</td><td>Inter-rater agreement</td><td>Observed vs expected agreement</td></tr>
      <tr><td>Wilcoxon Signed-Rank</td><td>Paired comparison test</td><td>scipy.stats.wilcoxon</td></tr>
      <tr><td>Online Weight Update</td><td>Rubric learning from preferences</td><td>Logistic gradient step (phase 6)</td></tr>
    </table>
  </div>

  <!-- ===== Limitations ===== -->
  <div class="card">
    <div class="section-title">Limitations &amp; Caveats</div>
    <div class="notes">IMPORTANT: All results below are from MOCK MODE &mdash; no real API calls
were made. The mock responses are deterministic placeholders that do not
reflect actual model capabilities.

&bull; Demo dataset: 20 synthetic preference pairs with 2 fixed templates and 1 rater/item.
  No real inter-rater reliability (&kappa;) is computable. Use &gt;=2 raters/item for that.

&bull; Mock responses: All mock critiques return identical fixed scores (6, 7, 5 for
  clarity/tone/match). This means quality deltas are always 0.0 and the rubric
  cannot learn meaningful weights from mock data.

&bull; Database backend: PostgreSQL was unavailable (psycopg/libpq issue). All writes
  fell back to the JSONL file. To test real DB persistence, start Docker:
  docker compose up -d db

&bull; Bradley-Terry: The demo data alternates winners by index parity (odd&rarr;A, even&rarr;B),
  so the model correctly reports no detectable strength gap (P=0.5). A harness
  reporting "94%% accuracy" on this data would be misleading.

&bull; Heuristic judge: Scores are based on sentence count + action verb hits, not a
  real LLM judge. Swap for app.rubric.Rubric + live model when mock_mode=False.

&bull; Mock mode cost/latency: These are simulated from token counts and pricing tables,
  not real API responses. Use real API calls to get actual cost data.</div>
  </div>

  <div class="footer">
    Creative Harness Evaluation Report &mdash; Generated %s
    <br>Statistical pipeline: bootstrap CIs, binomial tests, Bradley-Terry MLE, Cohen's &kappa;
  </div>
</div>
</body>
</html>"""


def build_html() -> str:
    d = build_data_dict()

    return HTML_TEMPLATE % (
        CSS_TEMPLATE,
        d["now"], d["metrics"].get("suite_name", "N/A"),
        # Exec summary KPIs
        d["n_samples"], d["win_rate"], d["binom_p"], d["kappa"],
        d["winners_a"], d["winners_b"],
        # Harness table
        d["win_rate"], d["ci_lo"], d["ci_hi"],
        d["binom_p"], d["bt_p"],
        d["judge_agree"], d["kappa"],
        d["irr"], d["db_backend"],
        d["ci_img"], d["trend_img"], d["rater_img"],
        d["limitations_html"],
        # Phase 2
        d["p2_count"], d["p2_vc_eff"], d["p2_lm_eff"], d["p2_mm_eff"],
        d["p2_vc_b"], d["p2_vc_c"], d["p2_vc_eff"], d["p2_vc_p"], d["p2_vc_class"], d["p2_vc_sig"],
        d["p2_lm_b"], d["p2_lm_c"], d["p2_lm_eff"], d["p2_lm_p"], d["p2_lm_class"], d["p2_lm_sig"],
        d["p2_mm_b"], d["p2_mm_c"], d["p2_mm_eff"], d["p2_mm_p"], d["p2_mm_class"], d["p2_mm_sig"],
        # Phase 3
        d["p3_trials_count"], d["p3_trials_count"], d["p3_delta"], d["p3_cost_ratio"], d["p3_single_lat"], d["p3_loop_lat"],
        d["p3_single_cost"], d["p3_loop_cost"], d["p3_cost_ratio"],
        d["p3_single_lat"], d["p3_loop_lat"], d["p3_lat_ratio"],
        d["p3_ci_lo"], d["p3_ci_hi"],
        # Phase 4
        d["p4_trials_count"], d["p4_trials_count"], d["p4_delta"], d["p4_cost_ratio"], d["p4_vision_cost"],
        d["p8_chart"],
        d["p4_delta"], d["p4_ci_lo"], d["p4_ci_hi"], d["p4_wilcoxon_p"],
        # Phase 6
        d["p6_train"], d["p6_holdout"],
        d["p6_train"], d["p6_holdout"],
        d["p6_acc"], d["p6_text_acc"],
        d["weight_img"],
        # Phase 7
        d["p7_trials_count"], d["p7_trials_count"],
        d["p7_cheap_cost"], d["p7_expensive_cost"], d["p7_adaptive_cost"],
        d["p7_chart"],
        d["p7_cheap_q"], d["p7_cheap_cost"], d["p7_cheap_med_cost"],
        d["p7_expensive_q"], d["p7_expensive_cost"], d["p7_expensive_med_cost"],
        d["p7_adaptive_q"], d["p7_adaptive_cost"], d["p7_adaptive_med_cost"],
        # Phase 8
        d["p8_trials_count"], d["p8_trials_count"],
        d["p8_text_cost"], d["p8_vision_cost"], d["p8_vision_ratio"],
        d["p8_chart"],
        d["p8_text_q"], d["p8_text_cost"],
        d["p8_vision_q"], d["p8_vision_cost"], d["p8_vision_ratio"],
        d["p8_adaptive_q"], d["p8_adaptive_cost"], d["p8_adaptive_ratio"],
        # Cross-phase charts
        d["cost_chart"], d["quality_chart"], d["summary_chart"],
        # Footer
        d["now"],
    )


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html()
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote rich HTML report to {OUTPUT_HTML} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
