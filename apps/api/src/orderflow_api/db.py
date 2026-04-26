"""
File:        apps/api/src/orderflow_api/db.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.

SQLAlchemy engine + session factory. Uses SQLite locally, Postgres on Railway.
Switch is automatic based on DATABASE_URL env var.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from orderflow_api.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().effective_database_url
        connect_args: dict[str, object] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def init_db() -> None:
    """Create all tables. Idempotent. Called on app startup."""
    from orderflow_api import models  # noqa: F401  (register models with Base)

    Base.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a SQLAlchemy session, closes on request end."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Test helper: forces engine recreation on next call."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
