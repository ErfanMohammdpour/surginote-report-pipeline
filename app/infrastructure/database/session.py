from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings, ensure_data_dir
from app.infrastructure.database.models import Base

ROOT = Path(__file__).resolve().parents[3]


def resolve_database_url(url: str) -> str:
    """Anchor relative sqlite paths to project root (pre-task/2)."""
    if url.startswith("sqlite:///./"):
        rel = url.removeprefix("sqlite:///./")
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return url


def build_engine():
    ensure_data_dir()
    url = resolve_database_url(settings.database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)


def create_all() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
