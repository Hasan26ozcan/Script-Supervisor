"""Tests for the vision-grounded critique path (mock mode).

Verifies: when reference images are supplied, the loop actually routes
through call_vision (not call), the resulting critique is tagged
modality="vision", and the visual-specific rubric criteria show up in the
scores -- not the text-only criteria.
"""

import base64

from app.agent_loop import CorrectionLoop
from app.gateway import GatewayLedger, ModelGateway
from app.rubric import Rubric
from app.schemas import ReferenceImage

# Smallest possible valid PNG (1x1 transparent pixel), just so a real file
# exists on disk for the path-based ReferenceImage to point at.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _make_ref_image(tmp_path, caption="location scout: rainy alley at night"):
    img_path = tmp_path / "ref.png"
    img_path.write_bytes(_TINY_PNG)
    return ReferenceImage(path=str(img_path), caption=caption)


def _fresh_loop(tmp_path, **kwargs):
    rubric = Rubric(weights_path=tmp_path / "weights.json")
    gateway = ModelGateway(GatewayLedger())
    return CorrectionLoop(gateway=gateway, rubric=rubric, **kwargs)


async def test_run_without_reference_images_uses_text_critique(tmp_path):
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("A quiet kitchen scene, early morning.")
    assert trace.reference_images == []
    assert trace.steps[0].critique.modality == "text"
    criteria_used = {s.criterion for s in trace.steps[0].critique.scores}
    assert criteria_used <= {"clarity", "tone_match", "actionability"}


async def test_run_with_reference_images_uses_vision_critique(tmp_path):
    ref = _make_ref_image(tmp_path)
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("A quiet kitchen scene, early morning.", reference_images=[ref])

    assert len(trace.reference_images) == 1
    assert trace.reference_images[0].caption == ref.caption
    assert trace.steps[0].critique.modality == "vision"
    criteria_used = {s.criterion for s in trace.steps[0].critique.scores}
    assert criteria_used <= {"visual_continuity", "lighting_match", "mood_match"}
    assert criteria_used  # actually scored something, not empty


async def test_vision_call_is_logged_with_image_token_overhead(tmp_path):
    ref = _make_ref_image(tmp_path)
    loop = _fresh_loop(tmp_path, max_turns=1)
    trace = await loop.run("A tense hallway scene.", reference_images=[ref])

    vision_calls = [c for c in loop.gateway.ledger.calls if c.task == "visual_critique"]
    assert len(vision_calls) == 1
    # mock mode adds a per-image token cost so cost accounting reflects
    # that vision calls are genuinely more expensive, not free
    assert vision_calls[0].prompt_tokens > 300
    assert trace.total_cost_usd > 0
