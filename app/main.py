"""FastAPI app tying the harness together.

Endpoints:
  POST /run       -> run the correction loop on a brief, return full trace
  POST /compare    -> record a human pairwise preference, updates rubric weights
  GET  /traces/{id} -> fetch a stored trace
  GET  /rubric      -> current rubric weights (so drift is visible over time)
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent_loop import CorrectionLoop
from app.config import settings
from app.database import *  # noqa: F403 -- ensure database initialization
from app.evaluation_harness import run_evaluation_suite
from app.gateway import ModelGateway
from app.mem0 import Mem0Manager
from app.preference_store import PreferenceStore
from app.prompts import get_prompt
from app.rubric import Rubric
from app.schemas import (
    ComparisonPair,
    PreferencePair,
    ReferenceImage,
    RunTrace,
)

app = FastAPI(title="Creative Harness")

data_dir = Path(settings.data_dir)
data_dir.mkdir(parents=True, exist_ok=True)
app.mount("/data", StaticFiles(directory=data_dir), name="data")

TRACES_DIR = Path(settings.traces_dir)
TRACES_DIR.mkdir(parents=True, exist_ok=True)

rubric = Rubric()
pref_store = PreferenceStore()
mem0_manager = Mem0Manager()


class ReferenceImageIn(BaseModel):
    path: str  # must already exist on disk (e.g. uploaded separately)
    caption: str = ""


class RunRequest(BaseModel):
    brief: str
    max_turns: int = 3
    reference_images: list[ReferenceImageIn] = []


class CompareRequest(BaseModel):
    pair_id: str | None = None
    brief: str
    prompt: str | None = None
    candidate_a: str
    candidate_b: str
    winner: str  # "a" | "b" | "tie"
    rater: str = "anonymous"
    notes: str = ""


class EvaluationRequest(BaseModel):
    suite_name: str = "live-evaluation"
    include_demo_dataset: bool = True


@app.post("/run", response_model=RunTrace)
async def run_loop(req: RunRequest) -> RunTrace:
    loop = CorrectionLoop(rubric=rubric, max_turns=req.max_turns)
    refs = [ReferenceImage(path=r.path, caption=r.caption) for r in req.reference_images]
    trace = await loop.run(req.brief, reference_images=refs)
    (TRACES_DIR / f"{trace.run_id}.json").write_text(trace.model_dump_json(indent=2))
    return trace


@app.get("/traces/{run_id}", response_model=RunTrace)
def get_trace(run_id: str) -> RunTrace:
    path = TRACES_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, "trace not found")
    return json.loads(path.read_text())


@app.post("/compare")
async def compare(req: CompareRequest) -> dict:
    pref_data = {
        "brief": req.brief,
        "prompt": req.prompt or f"Brief: {req.brief}\n\nShot list:\n",
        "candidate_a": req.candidate_a,
        "candidate_b": req.candidate_b,
        "winner": req.winner,
        "rater": req.rater,
        "notes": req.notes,
    }
    if req.pair_id:
        pref_data["pair_id"] = req.pair_id
    pref = PreferencePair(**pref_data)  # type: ignore[arg-type]
    pref_store.add(pref)

    # Store this human judged pair for Mem0-style compression pair tracking.
    comp_pair = ComparisonPair(
        pair_id=pref.pair_id,
        source="compare_api",
        brief=req.brief,
        candidate_a=req.candidate_a,
        candidate_b=req.candidate_b,
        reference_image=None,
    )
    mem0_manager.ingest_comparison_pair(comp_pair, req.winner)  # type: ignore[arg-type]

    # Re-score both candidates against the rubric so the preference can
    # actually move weights (needs criteria scores, not just raw text).
    gw = ModelGateway()
    critique_system = get_prompt("critique")
    prompt_a = f"Brief: {req.brief}\n\nShot list:\n{req.candidate_a}"
    prompt_b = f"Brief: {req.brief}\n\nShot list:\n{req.candidate_b}"
    call_a = await gw.call("critique", critique_system, prompt_a)
    call_b = await gw.call("critique", critique_system, prompt_b)
    scores_a, _ = rubric.parse_critique_text(call_a.text)
    scores_b, _ = rubric.parse_critique_text(call_b.text)
    rubric.update_from_preference(pref, scores_a, scores_b)
    return {"status": "recorded", "pair_id": pref.pair_id, "updated_weights": rubric.weights}


@app.post("/evaluation/run")
def run_evaluation(req: EvaluationRequest | None = None) -> dict:
    from training.generate_fake_preferences import build_fake_preferences

    preferences = pref_store.all() or build_fake_preferences()
    result = run_evaluation_suite(
        preferences=preferences,
        workspace_root=Path.cwd(),
        suite_name=req.suite_name if req else "live-evaluation",
        include_demo_dataset=(req.include_demo_dataset if req else True),
    )
    return result


@app.get("/rubric")
def get_rubric() -> dict:
    return {"criteria": rubric.criteria, "weights": rubric.weights}


@app.get("/rubric/history")
def get_rubric_history() -> dict:
    return {"weight_history": rubric.weight_history}


@app.get("/comparison-pairs")
def get_comparison_pairs() -> list[dict]:
    path = Path(settings.comparison_pairs_path)
    if not path.exists():
        return []
    pairs: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pairs.append(json.loads(line))
    return pairs


@app.get("/mem0/entries")
def get_mem0_entries() -> list[dict]:
    return [entry.model_dump() for entry in mem0_manager.store.entries.values()]


@app.get("/mem0/stale")
def get_mem0_stale_entries() -> list[dict]:
    return [entry.model_dump() for entry in mem0_manager.store.find_stale_entries()]


@app.post("/mem0/validate")
async def validate_mem0_entries() -> dict:
    results = await mem0_manager.validate_all()
    summary = {
        "total": len(results),
        "stale": sum(1 for r in results if r.stale),
        "active": sum(1 for r in results if not r.stale),
    }
    return {"summary": summary, "details": [r.model_dump() for r in results]}


@app.post("/mem0/refresh")
def refresh_mem0_entries() -> dict:
    refreshed = mem0_manager.refresh_stale()
    return {"refreshed": [entry.model_dump() for entry in refreshed]}


@app.get("/compare-ui", response_class=HTMLResponse)
def compare_ui() -> HTMLResponse:
    html_path = Path(__file__).resolve().parent / "templates" / "compare.html"
    if not html_path.exists():
        raise HTTPException(404, "Comparison UI not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
def health_check() -> dict:
    """Simple readiness check for Docker and orchestration health checks."""
    mode = "mock" if settings.mock_mode else "live"
    return {"status": "ok", "service": "creative-harness", "mode": mode}
