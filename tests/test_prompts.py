"""Tests for the prompt registry (app/prompts.py)."""
import pytest


def test_get_prompt_returns_string(monkeypatch):
    """get_prompt returns the raw YAML content for a known task/version."""
    from app.prompts import get_prompt

    text = get_prompt("draft")
    assert isinstance(text, str)
    assert len(text) > 0
    assert "You are a shot-list generator" in text


def test_get_prompt_critique(monkeypatch):
    """critique prompt contains the expected rubric criteria."""
    from app.prompts import get_prompt

    text = get_prompt("critique")
    assert "clarity" in text
    assert "tone_match" in text
    assert "actionability" in text


def test_get_prompt_vision_critique(monkeypatch):
    """vision_critique prompt exists and is valid YAML content."""
    from app.prompts import get_prompt

    text = get_prompt("vision_critique")
    assert isinstance(text, str)
    assert len(text) > 0


def test_get_prompt_raises_file_not_found(monkeypatch):
    """get_prompt raises FileNotFoundError for a non-existent task."""
    from app.prompts import get_prompt

    with pytest.raises(FileNotFoundError):
        get_prompt("nonexistent_task")


def test_get_prompt_unsupported_version(monkeypatch):
    """get_prompt raises FileNotFoundError for a version that doesn't exist."""
    from app.prompts import get_prompt

    with pytest.raises(FileNotFoundError):
        get_prompt("draft", version="v999")


def test_list_available_prompts_returns_dict(monkeypatch):
    """list_available_prompts returns a dict mapping task names to version lists."""
    from app.prompts import list_available_prompts

    result = list_available_prompts()
    assert isinstance(result, dict)
    assert "draft" in result
    assert "critique" in result
    assert "revise" in result


def test_list_available_prompts_versions_are_sorted(monkeypatch):
    """list_available_prompts returns version lists in sorted order."""
    from app.prompts import list_available_prompts

    result = list_available_prompts()
    for versions in result.values():
        assert versions == sorted(versions)


def test_get_prompt_caching(monkeypatch):
    """get_prompt uses lru_cache so repeated calls return the same object."""
    from app.prompts import get_prompt

    first = get_prompt("draft")
    second = get_prompt("draft")
    assert first is second


def test_prompt_registry_has_all_required_tasks(monkeypatch):
    """All task types used by the correction loop should have prompts."""
    from app.prompts import list_available_prompts

    tasks = list_available_prompts()
    for required in ("draft", "critique", "revise"):
        assert required in tasks, f"Missing prompt task: {required}"
