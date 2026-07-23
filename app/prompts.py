"""Prompt registry for versioned prompt templates.

Instead of hardcoded strings in agent_loop.py, we load prompts from YAML files
in the prompts/ directory. This enables prompt versioning and makes it easy
to A/B test different prompt formulations.
"""
from __future__ import annotations

import yaml
from functools import lru_cache
from pathlib import Path
from typing import Literal

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=128)
def get_prompt(task: Literal["draft", "critique", "revise"], version: str = "v1") -> str:
    """
    Get a prompt template by task and version.

    Args:
        task: The task type ("draft", "critique", or "revise")
        version: The version string (defaults to "v1")

    Returns:
        The prompt template string

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / task / f"{version}.yaml"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8").strip()


def list_available_prompts() -> dict[str, list[str]]:
    """
    List all available prompts by task and version.

    Returns:
        Dictionary mapping task types to lists of available versions
    """
    result = {}
    for task_dir in PROMPTS_DIR.iterdir():
        if task_dir.is_dir():
            versions = [f.stem for f in task_dir.glob("*.yaml")]
            if versions:
                result[task_dir.name] = sorted(versions)
    return result