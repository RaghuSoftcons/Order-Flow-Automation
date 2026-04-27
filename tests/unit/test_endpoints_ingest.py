"""
File:        tests/unit/test_endpoints_ingest.py
Created:     2026-04-26 18:36 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:36 EST
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.models import User
from orderflow_api.services.registry import get_registry


def _make_user(
    session: Session,
    email: str = "raghu@softcons.net",
    is_admin: bool = True,
) -> str:
    plaintext = generate_api_key()
    user = User(
        email=email,
        display_name=email.split("@")[0],
        api_key_hash=hash_api_key(plaintext),
        prop_tier="apex_100k",
        is_admin=is_admin,
    )
    session.add(user)
    session.commit()
    return plaintext


def _depth_payload() -> dict:
    return {
        "type": "depth",
        "symbol": "ES",
        "contract": "ES 06-26",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "bids": [{"price": 5285.0, "size": 100, "orders": 5}],
        "asks": [{"price": 5285.25, "size": 75, "orders": 4}],
    }


def _trade_payload() -> dict:
    return {
        "type": "trade",
        "symbol": "ES",
        "contract": "ES 06-26",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "price": 5285.25,
        "size": 7,
        "aggressor": "buy",
    }


# --- HTTP POST /ingest/event ---


def test_ingest_event_requires_admin(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=False)
    resp = client.post("/ingest/event", json=_depth_payload(), headers={"X-API-Key": key})
    assert resp.status_code == 403


def test_ingest_event_rejects_no_auth(client: TestClient) -> None:
    resp = client.post("/ingest/event", json=_depth_payload())
    assert resp.status_code == 401


def test_ingest_event_admin_can_post_depth(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=True)
    resp = client.post("/ingest/event", json=_depth_payload(), headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["event_type"] == "depth"
    book = get_registry().get("ES")
    assert book.best_bid().price == 5285.0


def test_ingest_event_admin_can_post_trade(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=True)
    resp = client.post("/ingest/event", json=_trade_payload(), headers={"X-API-Key": key})
    assert resp.status_code == 200
    book = get_registry().get("ES")
    assert len(book.trade_tape) == 1


def test_ingest_event_rejects_malformed(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=True)
    bad = {"type": "depth"}  # missing required fields
    resp = client.post("/ingest/event", json=bad, headers={"X-API-Key": key})
    assert resp.status_code == 422


# --- WebSocket /ws/nt-ingest ---


def test_ws_rejects_no_api_key(client: TestClient) -> None:
    import pytest
    from starlette.testclient import WebSocketDisconnect as StarletteWSD

    with pytest.raises((StarletteWSD, Exception)):
        with client.websocket_connect("/ws/nt-ingest"):
            pass


def test_ws_rejects_non_admin_key(client: TestClient, db_session: Session) -> None:
    import pytest
    from starlette.testclient import WebSocketDisconnect as StarletteWSD

    key = _make_user(db_session, is_admin=False)
    with pytest.raises((StarletteWSD, Exception)):
        with client.websocket_connect(f"/ws/nt-ingest?api_key={key}"):
            pass


def test_ws_admin_streams_events(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=True)
    with client.websocket_connect(f"/ws/nt-ingest?api_key={key}") as ws:
        ws.send_json(_depth_payload())
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        assert ack["symbol"] == "ES"
        assert ack["event_type"] == "depth"

        ws.send_json(_trade_payload())
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        assert ack["event_type"] == "trade"

    book = get_registry().get("ES")
    assert book.best_bid().price == 5285.0
    assert len(book.trade_tape) == 1


def test_ws_returns_nack_on_invalid_event(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, is_admin=True)
    with client.websocket_connect(f"/ws/nt-ingest?api_key={key}") as ws:
        ws.send_json({"type": "depth"})  # invalid
        nack = ws.receive_json()
        assert nack["type"] == "nack"
        assert "errors" in nack
