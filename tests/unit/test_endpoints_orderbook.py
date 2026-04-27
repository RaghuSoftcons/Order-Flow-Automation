"""
File:        tests/unit/test_endpoints_orderbook.py
Created:     2026-04-26 18:35 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:35 EST
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.models import User
from orderflow_api.services.orderbook.events import DepthEvent, DepthLevel
from orderflow_api.services.registry import get_registry


def _make_user(session: Session, is_admin: bool = True) -> str:
    plaintext = generate_api_key()
    user = User(
        email="raghu@softcons.net",
        display_name="Raghu",
        api_key_hash=hash_api_key(plaintext),
        prop_tier="apex_100k",
        is_admin=is_admin,
    )
    session.add(user)
    session.commit()
    return plaintext


def _seed_es_book() -> None:
    from datetime import datetime, timezone

    get_registry().apply(
        DepthEvent(
            symbol="ES",
            contract="ES 06-26",
            ts_utc=datetime.now(timezone.utc),
            bids=[DepthLevel(price=5285.00, size=100, orders=5), DepthLevel(price=5284.75, size=50, orders=3)],
            asks=[DepthLevel(price=5285.25, size=75, orders=4), DepthLevel(price=5285.50, size=80, orders=5)],
        )
    )


def test_orderbook_requires_auth(client: TestClient) -> None:
    resp = client.get("/orderbook?symbol=ES")
    assert resp.status_code == 401


def test_orderbook_unknown_symbol_returns_404(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/orderbook?symbol=XYZ", headers={"X-API-Key": key})
    assert resp.status_code == 404


def test_orderbook_returns_seeded_book(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    _seed_es_book()
    resp = client.get("/orderbook?symbol=ES&levels=2", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "ES"
    assert body["contract"] == "ES 06-26"
    assert len(body["bids"]) == 2
    assert body["bids"][0]["price"] == 5285.00
    assert body["asks"][0]["price"] == 5285.25
    assert body["feed_age_seconds"] is not None
    assert body["feed_age_seconds"] < 5
    assert "manual_only_notice" in body


def test_orderbook_empty_symbol_returns_empty_lists(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/orderbook?symbol=NQ", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["bids"] == []
    assert body["asks"] == []
    assert body["last_update_ts"] is None


def test_orderbook_levels_clamped_to_max(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    _seed_es_book()
    resp = client.get("/orderbook?symbol=ES&levels=21", headers={"X-API-Key": key})
    assert resp.status_code == 422  # Pydantic Query(le=20) rejects


def test_liquidity_snapshot_returns_metrics(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    _seed_es_book()
    resp = client.get("/liquidity-snapshot?symbol=ES", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    metrics = body["metrics"]
    assert metrics["symbol"] == "ES"
    assert metrics["best_bid"] == 5285.00
    assert metrics["best_ask"] == 5285.25
    assert metrics["mid"] == 5285.125
    assert metrics["imbalance_top5"] is not None


def test_liquidity_snapshot_empty_book_safe(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/liquidity-snapshot?symbol=NQ", headers={"X-API-Key": key})
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    assert metrics["best_bid"] is None
    assert metrics["imbalance_top5"] is None


def test_instrument_returns_spec(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/instrument?symbol=ES", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "ES"
    assert body["asset_class"] == "future"
    assert body["tick_size"] == 0.25


def test_instrument_unknown_returns_404(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/instrument?symbol=XYZ", headers={"X-API-Key": key})
    assert resp.status_code == 404


def test_feed_health_no_data_state(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/health/feed", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "no_data"
    assert "ES" in body["symbols"]
    assert body["symbols"]["ES"]["status"] == "no_data"


def test_feed_health_fresh_after_seed(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    _seed_es_book()
    resp = client.get("/health/feed", headers={"X-API-Key": key})
    body = resp.json()
    assert body["symbols"]["ES"]["status"] == "fresh"
    # NQ still has no data
    assert body["symbols"]["NQ"]["status"] == "no_data"
