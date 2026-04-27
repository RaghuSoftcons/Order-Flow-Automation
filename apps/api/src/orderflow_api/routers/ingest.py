"""
File:        apps/api/src/orderflow_api/routers/ingest.py
Created:     2026-04-26 18:33 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:33 EST

Change Log:
- 2026-04-26 18:33 EST | 1.0.0 | Phase 1B: WebSocket endpoint for NT bridge events.

The NT bridge (and the Phase 1C replay harness) connect here and stream
DepthEvent / TradeEvent JSON messages. We validate, route into the registry,
and ack each message.

Auth: API key via the `api_key` query parameter (WebSockets don't reliably
support custom headers across all clients). The NinjaScript client will
include `?api_key=...`. Only admin users are accepted as ingest sources.

There is also an HTTP POST `/ingest/event` for one-off testing without WS.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from orderflow_api.auth import hash_api_key, require_admin
from orderflow_api.db import get_session
from orderflow_api.logging import get_logger
from orderflow_api.models import User
from orderflow_api.services.orderbook.events import EventEnvelope
from orderflow_api.services.registry import get_registry

logger = get_logger("ingest")

router = APIRouter()


def _resolve_admin(api_key: str | None, session: Session) -> User | None:
    if not api_key:
        return None
    user = session.scalar(select(User).where(User.api_key_hash == hash_api_key(api_key)))
    if user is None or user.disabled or not user.is_admin:
        return None
    return user


@router.websocket("/ws/nt-ingest")
async def ws_nt_ingest(websocket: WebSocket, api_key: str | None = None) -> None:
    # Auth must happen before .accept() to avoid 1006 with no reason on client.
    session_iter = get_session()
    session = next(session_iter)
    try:
        user = _resolve_admin(api_key, session)
    finally:
        session.close()

    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="invalid api key or not admin")
        return

    await websocket.accept()
    logger.info("ws_connect", user_id=user.id)
    registry = get_registry()
    accepted = 0
    rejected = 0
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                envelope = EventEnvelope.model_validate_json(raw)
            except ValidationError as err:
                rejected += 1
                await websocket.send_json({"type": "nack", "errors": json.loads(err.json())})
                continue
            event = envelope.root
            registry.apply(event)
            accepted += 1
            await websocket.send_json({"type": "ack", "symbol": event.symbol, "event_type": event.type})
    except WebSocketDisconnect:
        logger.info("ws_disconnect", user_id=user.id, accepted=accepted, rejected=rejected)


@router.post("/ingest/event")
def ingest_event_http(
    payload: dict,
    _admin: User = Depends(require_admin),
) -> dict[str, Any]:
    """Single-event HTTP ingest. Convenience for ad-hoc testing without a WS client."""
    try:
        envelope = EventEnvelope.model_validate(payload)
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=json.loads(err.json()))
    event = envelope.root
    get_registry().apply(event)
    return {"status": "ok", "symbol": event.symbol, "event_type": event.type}
