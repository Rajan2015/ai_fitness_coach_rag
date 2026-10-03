"""SQLAlchemy engine/session factory for the SQLite data layer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.db.models import Base

_db_path = Path(config["database"]["path"]).resolve()
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{_db_path}", connect_args={"check_same_thread": False}
)
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
