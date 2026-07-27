"""Preference persistence using PostgreSQL as the primary backend.

The project still supports JSONL export/import for DPO training and legacy
migration, but preference data is written to and read from SQL by default.
When PostgreSQL is unavailable, the store transparently falls back to the
JSONL file used by the training and evaluation scripts so the pipeline remains
operational in local/offline environments.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, PreferencePairModel, create_sessionmaker
from app.schemas import PreferencePair

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class PreferenceStore:
    def __init__(self, database_url: str | None = None):
        resolved_url = database_url or os.environ.get("HARNESS_DATABASE_URL") or settings.database_url
        self.session_local, self.engine = create_sessionmaker(resolved_url)
        self.session: Session = self.session_local()
        self._db_available = True
        self._fallback_path = Path(settings.preferences_path)
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_records: list[PreferencePair] = []
        self._load_fallback_records()

        try:
            Base.metadata.create_all(bind=self.engine)
        except Exception as exc:  # pragma: no cover - exercised in offline environments
            self._db_available = False
            self._db_error = str(exc)

    def add(self, pref: PreferencePair) -> None:
        model = PreferencePairModel(
            pair_id=pref.pair_id,
            created_at=pref.created_at,
            brief=pref.brief,
            prompt=pref.prompt,
            candidate_a=pref.candidate_a,
            candidate_b=pref.candidate_b,
            winner=pref.winner,
            rater=pref.rater,
            notes=pref.notes,
        )
        try:
            self.session.merge(model)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            self._db_available = False
            self._fallback_records.append(pref)
            self._write_fallback_records()
            return
        except Exception:  # pragma: no cover - fallback for offline environments
            self._db_available = False
            self._fallback_records.append(pref)
            self._write_fallback_records()
            return

        self._fallback_records.append(pref)
        self._write_fallback_records()

    def all(self) -> list[PreferencePair]:
        if self._db_available:
            try:
                stmt = select(PreferencePairModel).order_by(PreferencePairModel.created_at.asc())
                rows = self.session.execute(stmt).scalars().all()
                return [self._row_to_pref(row) for row in rows]
            except Exception:  # pragma: no cover - fallback for offline environments
                self._db_available = False

        if self._fallback_records:
            return self._fallback_records
        return self._load_fallback_records()

    def migrate_from_jsonl(self, jsonl_path: str | Path) -> int:
        source = Path(jsonl_path)
        if not source.exists():
            raise FileNotFoundError(f"Preference JSONL file not found: {source}")

        count = 0
        with source.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                pref = PreferencePair(**data)
                self.add(pref)
                count += 1
        return count

    def _row_to_pref(self, row: PreferencePairModel) -> PreferencePair:
        return PreferencePair(
            pair_id=row.pair_id,
            created_at=row.created_at,
            brief=row.brief,
            prompt=row.prompt,
            candidate_a=row.candidate_a,
            candidate_b=row.candidate_b,
            winner=row.winner,
            rater=row.rater,
            notes=row.notes,
        )

    def _load_fallback_records(self) -> list[PreferencePair]:
        if not self._fallback_path.exists():
            return []

        records: list[PreferencePair] = []
        with self._fallback_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(PreferencePair(**json.loads(line)))
        self._fallback_records = records
        return records

    def _write_fallback_records(self) -> None:
        content = "".join(pref.model_dump_json() + "\n" for pref in self._fallback_records)
        self._fallback_path.write_text(content, encoding="utf-8")

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> PreferenceStore:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
