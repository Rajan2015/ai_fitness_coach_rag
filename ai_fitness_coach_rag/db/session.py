"""SQLAlchemy engine/session factory for the Postgres (Neon) data layer."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.db.models import Base


def _psycopg2_url(url: str) -> str:
    """Force the psycopg2 driver explicitly (SQLAlchemy may otherwise probe for psycopg3)."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


engine = create_engine(_psycopg2_url(config["database"]["url"]), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    """Create all known tables when the application starts."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI-style dependency yielding a request-scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
