"""
File:        apps/api/src/orderflow_api/main.py
Created:     2026-04-26 17:21 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:21 EST

Change Log:
- 2026-04-26 17:21 EST | 1.0.0 | Initial Phase 0 scaffold.

FastAPI entry. Phase 0 mounts /health (public) and /me (auth-protected).
Future phases add /orderbook (Phase 1), /claude/* (Phase 2), /execute/* (Phase 3+).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from orderflow_api import __version__
from orderflow_api.config import get_settings
from orderflow_api.db import init_db
from orderflow_api.logging import configure_logging, get_logger
from orderflow_api.routers import feed, health, ingest, me, orderbook


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("orderflow_api")
    logger.info(
        "startup",
        version=__version__,
        environment=settings.environment,
        db=settings.effective_database_url.split("://")[0],
        cache="fakeredis" if settings.use_fakeredis else "redis",
    )
    init_db()
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Order Flow Automation",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(me.router, tags=["user"])
    app.include_router(orderbook.router, tags=["orderbook"])
    app.include_router(feed.router, tags=["health"])
    app.include_router(ingest.router, tags=["ingest"])
    return app


app = create_app()
