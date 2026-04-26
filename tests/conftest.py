"""
File:        tests/conftest.py
Created:     2026-04-26 17:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:23 EST

Change Log:
- 2026-04-26 17:23 EST | 1.0.0 | Initial Phase 0 scaffold.

Shared pytest fixtures. Pattern follows Codex projects:
- Each test gets a fresh in-memory SQLite database
- Each test gets a fresh fakeredis instance
- TestClient drives the FastAPI app in-process — no real server, no real network
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from orderflow_api import db as db_module
from orderflow_api import cache as cache_module
from orderflow_api.config import get_settings
from orderflow_api.db import Base
from orderflow_api.main import create_app


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    """Force Settings to re-read environment on every test (in case tests set env vars)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def in_memory_engine(monkeypatch: pytest.MonkeyPatch):
    """In-memory SQLite, fresh per test, with all tables created."""
    # StaticPool keeps a single connection alive so tables created here are
    # visible to all subsequent sessions. Without it, SQLite ":memory:" gives
    # each connection its own empty database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    monkeypatch.setattr(db_module, "_engine", engine, raising=False)
    monkeypatch.setattr(db_module, "_SessionLocal", SessionLocal, raising=False)
    yield engine
    db_module.reset_engine_for_tests()


@pytest.fixture
def db_session(in_memory_engine) -> Iterator[Session]:
    SessionLocal = sessionmaker(bind=in_memory_engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fresh_cache(monkeypatch: pytest.MonkeyPatch):
    """Fresh fakeredis per test."""
    import fakeredis

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(cache_module, "_client", client, raising=False)
    yield client
    cache_module.reset_cache_for_tests()


@pytest.fixture
def client(in_memory_engine, fresh_cache) -> Iterator[TestClient]:
    """FastAPI TestClient with isolated DB + cache."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
