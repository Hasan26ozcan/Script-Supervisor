"""Generate Phase 5 pairwise comparison examples from existing experimental traces."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config import settings


DATA_DIR = Path("data")
PHASE3_RESULTS = DATA_DIR / "results" / "phase3_results.json"
PHASE4_RESULTS = DATA_DIR / "results" / "phase4_results.json"
PHASE5_PAIRS = Path(settings.comparison_pairs_path)


@dataclass
class ComparisonPair:
    pair_id: str
    source: str
    brief: str
    candidate_a: str
    candidate_b: str
    reference_image: str | None = None


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase3_pairs(results: dict) -> list[ComparisonPair]:
    pairs: list[ComparisonPair] = []
    for trial in results.get("results", {}).get("trials", []):
        brief = trial["title"]
        single = trial["single"]["final_output"] if "final_output" in trial["single"] else trial["single"].get("output", "")
        loop = trial["loop"]["final_output"] if "final_output" in trial["loop"] else trial["loop"].get("output", "")
        if not single or not loop:
            continue
        pairs.append(ComparisonPair(
            pair_id=f"phase3-{trial['id']}-single-vs-loop",
            source="phase3",
            brief=trial["brief"],
            candidate_a=single,
            candidate_b=loop,
        ))
    return pairs


def build_phase4_pairs(results: dict) -> list[ComparisonPair]:
    pairs: list[ComparisonPair] = []
    for trial in results.get("results", {}).get("trials", []):
        brief = trial["title"]
        text = trial["text_only"]["final_output"]
        vision = trial["vision"]["final_output"]
        if not text or not vision:
            continue
        pairs.append(ComparisonPair(
            pair_id=f"phase4-{trial['id']}-text-vs-vision",
            source="phase4",
            brief=trial["brief"],
            candidate_a=text,
            candidate_b=vision,
            reference_image=trial.get("reference_image"),
        ))
    return pairs


def generate_pairs(output: Path) -> list[ComparisonPair]:
    pairs: list[ComparisonPair] = []
    if PHASE3_RESULTS.exists():
        phase3 = load_json(PHASE3_RESULTS)
        pairs.extend(build_phase3_pairs(phase3))
    if PHASE4_RESULTS.exists():
        phase4 = load_json(PHASE4_RESULTS)
        pairs.extend(build_phase4_pairs(phase4))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair.__dict__, ensure_ascii=False) + "\n")
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 5 comparison pair JSONL from experiment outputs.")
    parser.add_argument("--output", type=Path, default=PHASE5_PAIRS)
    args = parser.parse_args()
    pairs = generate_pairs(args.output)
    print(f"Wrote {len(pairs)} comparison pairs to {args.output}")


if __name__ == "__main__":
    main()
