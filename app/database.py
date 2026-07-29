"""Database session helpers for the Creative Harness."""
from __future__ import annotations

from app.db import create_sessionmaker, init_db

try:
    SessionLocal, engine = create_sessionmaker()
except Exception:  # pragma: no cover - offline environments may lack psycopg
    SessionLocal, engine = None, None  # type: ignore[misc,assignment]

# Ensure the database schema exists on startup when PostgreSQL is reachable.
if engine is not None:
    try:
        init_db()
    except Exception:  # pragma: no cover - offline environments should still boot
        pass
