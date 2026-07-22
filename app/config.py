"""Centralized configuration via pydantic-settings.

Everything that used to be a scattered `os.environ.get(...)` call across
gateway.py, main.py, etc. lives here instead -- one place to see every
knob the harness exposes, one place to add validation, and a `.env` file
works out of the box for local dev without extra plumbing.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HARNESS_", env_file=".env", extra="ignore")

    mock_mode: bool = Field(default=True, description="If true, no real API calls are made.")
    anthropic_api_key: str | None = Field(
        default=None, description="Required when mock_mode=False."
    )

    # correction loop defaults
    max_turns: int = 3
    plateau_epsilon: float = 0.3
    quality_threshold: float = 8.0

    # storage locations -- kept as plain paths (not a database) deliberately
    # for phase 0-6; swapping to Postgres is a phase-7+ concern once trace
    # volume actually justifies it.
    data_dir: str = "data"
    traces_dir: str = "data/traces"
    preferences_path: str = "data/preferences.jsonl"
    rubric_weights_path: str = "data/rubric_weights.json"

    # observability -- optional Langfuse export of every gateway call.
    # Langfuse is MIT-licensed and self-hostable, which matters here since
    # trace data may include unpublished creative briefs.
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    log_level: str = "INFO"


settings = Settings()
