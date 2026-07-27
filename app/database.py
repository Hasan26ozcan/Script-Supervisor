"""Database session helpers for the Creative Harness."""
from __future__ import annotations

from app.db import create_sessionmaker, init_db

SessionLocal, engine = create_sessionmaker()

# Ensure the database schema exists on startup when PostgreSQL is reachable.
try:
    init_db()
except Exception:  # pragma: no cover - offline environments should still boot
    pass
