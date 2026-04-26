"""
File:        apps/api/src/orderflow_api/routers/health.py
Created:     2026-04-26 17:21 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:21 EST

Change Log:
- 2026-04-26 17:21 EST | 1.0.0 | Initial Phase 0 scaffold.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from orderflow_api import __version__
from orderflow_api.cache import cache_health
from orderflow_api.config import get_settings
from orderflow_api.db import get_engine

router = APIRouter()


def _db_health() -> dict[str, Any]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        kind = "sqlite" if get_settings().effective_database_url.startswith("sqlite") else "postgres"
        return {"status": "ok", "kind": kind}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "kind": "unknown", "error": str(exc)}


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.environment,
        "dependencies": {
            "database": _db_health(),
            "cache": cache_health(),
        },
    }
