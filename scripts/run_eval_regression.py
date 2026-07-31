"""Run the eval regression suite as a CI gate.

Loads a fixed golden dataset, runs the evaluation harness, and compares
every metric against a thresholds config. Exits non-zero if any metric
regresses below its minimum — making eval quality a hard CI gate, not
just a passive report.

Usage:
    python -m scripts.run_eval_regression \
        --dataset eval/golden_qa.jsonl \
        --threshold-config eval/thresholds.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from app.evaluation_harness import run_evaluation_suite
from app.schemas import PreferencePair


def _load_golden_dataset(path: Path) -> list[PreferencePair]:
    """Load golden QA pairs from a JSONL file into PreferencePair objects."""
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")

    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        raise ValueError(f"Golden dataset is empty: {path}")

    pairs = []
    for rec in records:
        pairs.append(
            PreferencePair(
                pair_id=rec.get("pair_id", ""),
                brief=rec["brief"],
                candidate_a=rec["candidate_a"],
                candidate_b=rec["candidate_b"],
                winner=rec["winner"],
                rater=rec.get("rater", "golden"),
                notes=rec.get("notes", ""),
            )
        )
    return pairs


def _load_thresholds(path: Path) -> dict[str, dict[str, float]]:
    """Load minimum thresholds from a YAML config file."""
    if not path.exists():
        raise FileNotFoundError(f"Threshold config not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        thresholds = yaml.safe_load(fh)

    if not isinstance(thresholds, dict):
        raise ValueError(f"Threshold config must be a mapping, got {type(thresholds)}")
    return thresholds


def _check_metric(
    name: str,
    actual: float | None,
    threshold_cfg: dict[str, float],
) -> bool:
    """Compare a single metric against its threshold. Returns True if passed."""
    if actual is None:
        print(f"  FAIL  {name}: metric is None (cannot compare)")
        return False

    min_val = threshold_cfg.get("min")
    if min_val is None:
        print(f"  SKIP  {name}: no 'min' threshold configured")
        return True

    passed = actual >= min_val
    status = "PASS" if passed else "FAIL"
    print(f"  {status}  {name}: {actual:.4f} (threshold >= {min_val})")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run eval regression suite and fail CI if metrics regress."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("eval/golden_qa.jsonl"),
        help="Path to the golden QA JSONL dataset (default: eval/golden_qa.jsonl)",
    )
    parser.add_argument(
        "--threshold-config",
        type=Path,
        default=Path("eval/thresholds.yaml"),
        help="Path to the thresholds YAML config (default: eval/thresholds.yaml)",
    )
    parser.add_argument(
        "--suite-name",
        type=str,
        default="ci-regression",
        help="Suite name for the evaluation report (default: ci-regression)",
    )
    args = parser.parse_args()

    print(f"Loading golden dataset: {args.dataset}")
    preferences = _load_golden_dataset(args.dataset)
    print(f"  Loaded {len(preferences)} golden pairs")

    print(f"Loading thresholds: {args.threshold_config}")
    thresholds = _load_thresholds(args.threshold_config)

    print(f"Running evaluation suite: {args.suite_name}")
    result = run_evaluation_suite(
        preferences,
        suite_name=args.suite_name,
        include_demo_dataset=False,
    )

    metrics = result["metrics"]
    print("\n=== Eval Regression Results ===\n")

    all_passed = True

    # Map threshold keys to metric keys in the evaluation harness output
    checks = [
        ("win_rate", "win_rate", thresholds.get("win_rate")),
        ("heuristic_judge_agreement", "heuristic_judge_agreement_rate", thresholds.get("heuristic_judge_agreement")),
        ("bradley_terry_p_a_beats_b", "bradley_terry", thresholds.get("bradley_terry_p_a_beats_b")),
    ]

    for label, metric_key, cfg in checks:
        if cfg is None:
            print(f"  SKIP  {label}: no threshold config found")
            continue

        actual = metrics.get(metric_key)

        # bradley_terry is a dict, extract p_a_beats_b
        if isinstance(actual, dict):
            actual = actual.get("p_a_beats_b")

        if not _check_metric(label, actual, cfg):
            all_passed = False

    print()
    if all_passed:
        print("All eval metrics passed the regression thresholds.")
        return 0
    else:
        print("REGRESSION DETECTED: one or more metrics fell below threshold.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
