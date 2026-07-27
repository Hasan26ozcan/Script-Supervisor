"""Tests for the Inspect AI adapter (evals/inspect_preference_task.py).

Skips cleanly if `inspect-ai` is not installed, since it is an optional
dependency (`pip install inspect-ai` / the `eval` extra) kept out of the
core API server's dependency footprint.
"""
from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("inspect_ai") is None,
    reason="inspect-ai is an optional dependency; install it to run this eval adapter",
)


def test_records_to_samples_covers_all_20_and_preserves_targets() -> None:
    from evals.inspect_preference_task import _load_records, _records_to_samples

    records = _load_records()
    assert len(records) == 20

    samples = _records_to_samples(records)
    assert len(samples) == 20
    targets = {s.target for s in samples}
    assert targets <= {"A", "B", "TIE"}


def test_swap_flips_winner_and_relabels_id() -> None:
    from evals.inspect_preference_task import _load_records, _records_to_samples

    records = _load_records()
    normal = _records_to_samples(records)
    swapped = _records_to_samples(records, swap=True)

    for n, s in zip(normal, swapped):
        assert s.id == f"{n.id}_swapped"
        if n.target != "TIE":
            assert s.target != n.target  # A/B flips under swap
        else:
            assert s.target == "TIE"


def test_bias_checked_task_includes_both_orderings() -> None:
    from evals.inspect_preference_task import script_supervisor_preference_eval_bias_checked

    t = script_supervisor_preference_eval_bias_checked()
    assert len(t.dataset) == 40  # 20 original + 20 swapped
