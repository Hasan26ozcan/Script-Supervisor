"""Shared test fixtures for the Creative Harness test suite.

Provides reusable tmp_path-based fixtures for databases, file
systems, and mock app state so that individual test files don't
reimplement the same setup logic.
"""

import pytest


@pytest.fixture
def mock_mode_env(monkeypatch):
    """Ensure HARNESS_MOCK_MODE=1 for every test that needs it."""
    monkeypatch.setenv("HARNESS_MOCK_MODE", "1")


@pytest.fixture
def tmp_database_url(tmp_path):
    """Return a SQLite database URL that lives inside *tmp_path*."""
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def empty_rubric(tmp_path):
    """Return a Rubric backed by a temporary weights file."""
    from app.rubric import Rubric

    return Rubric(weights_path=tmp_path / "weights.json")


@pytest.fixture
def fresh_gateway():
    """Return a ModelGateway with a clean in-memory ledger."""
    from app.gateway import GatewayLedger, ModelGateway

    return ModelGateway(GatewayLedger())
