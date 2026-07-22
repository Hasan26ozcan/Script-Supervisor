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
from pydantic import BaseModel

from app.agent_loop import CRITIQUE_SYSTEM, CorrectionLoop
from app.config import settings
from app.gateway import ModelGateway
from app.preference_store import PreferenceStore
from app.rubric import Rubric
from app.schemas import PreferencePair, ReferenceImage, RunTrace

app = FastAPI(title="Creative Harness")

TRACES_DIR = Path(settings.traces_dir)
TRACES_DIR.mkdir(parents=True, exist_ok=True)

rubric = Rubric()
pref_store = PreferenceStore()


class ReferenceImageIn(BaseModel):
    path: str  # must already exist on disk (e.g. uploaded separately)
    caption: str = ""


class RunRequest(BaseModel):
    brief: str
    max_turns: int = 3
    reference_images: list[ReferenceImageIn] = []


class CompareRequest(BaseModel):
    brief: str
    candidate_a: str
    candidate_b: str
    winner: str  # "a" | "b" | "tie"
    rater: str = "anonymous"
    notes: str = ""


@app.post("/run", response_model=RunTrace)
def run_loop(req: RunRequest) -> RunTrace:
    loop = CorrectionLoop(rubric=rubric, max_turns=req.max_turns)
    refs = [ReferenceImage(path=r.path, caption=r.caption) for r in req.reference_images]
    trace = loop.run(req.brief, reference_images=refs)
    (TRACES_DIR / f"{trace.run_id}.json").write_text(trace.model_dump_json(indent=2))
    return trace


@app.get("/traces/{run_id}", response_model=RunTrace)
def get_trace(run_id: str) -> RunTrace:
    path = TRACES_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, "trace not found")
    return json.loads(path.read_text())


@app.post("/compare")
def compare(req: CompareRequest) -> dict:
    pref = PreferencePair(
        brief=req.brief,
        candidate_a=req.candidate_a,
        candidate_b=req.candidate_b,
        winner=req.winner,  # type: ignore[arg-type]
        rater=req.rater,
        notes=req.notes,
    )
    pref_store.add(pref)

    # Re-score both candidates against the rubric so the preference can
    # actually move weights (needs criteria scores, not just raw text).
    gw = ModelGateway()
    prompt_a = f"Brief: {req.brief}\n\nShot list:\n{req.candidate_a}"
    prompt_b = f"Brief: {req.brief}\n\nShot list:\n{req.candidate_b}"
    scores_a, _ = rubric.parse_critique_text(gw.call("critique", CRITIQUE_SYSTEM, prompt_a).text)
    scores_b, _ = rubric.parse_critique_text(gw.call("critique", CRITIQUE_SYSTEM, prompt_b).text)
    rubric.update_from_preference(pref, scores_a, scores_b)
    return {"status": "recorded", "pair_id": pref.pair_id, "updated_weights": rubric.weights}


@app.get("/rubric")
def get_rubric() -> dict:
    return {"criteria": rubric.criteria, "weights": rubric.weights}
