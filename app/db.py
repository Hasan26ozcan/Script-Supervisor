"""Primary SQL database integration for preference storage and evaluation artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class PreferencePairModel(Base):
    __tablename__ = "preferences"

    pair_id = Column(String, primary_key=True, index=True)
    created_at = Column(String, nullable=False)
    brief = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False)
    candidate_a = Column(Text, nullable=False)
    candidate_b = Column(Text, nullable=False)
    winner = Column(String, nullable=False)
    rater = Column(String, nullable=False)
    notes = Column(Text, nullable=False)


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"

    run_id = Column(String, primary_key=True, index=True)
    created_at = Column(String, nullable=False)
    suite_name = Column(String, nullable=False, index=True)
    dataset_name = Column(String, nullable=False)
    n_samples = Column(Integer, nullable=False)
    holdout_size = Column(Integer, nullable=False)
    accuracy = Column(Float, nullable=False)
    report_markdown_path = Column(Text, nullable=False)
    report_html_path = Column(Text, nullable=False)
    metrics_json_path = Column(Text, nullable=False)
    charts_json = Column(Text, nullable=False)


def create_engine_for_url(database_url: str | None = None):
    url = database_url or settings.database_url
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        url,
        future=True,
        echo=settings.database_echo,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def create_sessionmaker(database_url: str | None = None):
    engine = create_engine_for_url(database_url)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    return local_session, engine


def init_db(database_url: str | None = None) -> None:
    _, engine = create_sessionmaker(database_url)
    Base.metadata.create_all(bind=engine)
