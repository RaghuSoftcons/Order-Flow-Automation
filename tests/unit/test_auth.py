"""
File:        tests/unit/test_auth.py
Created:     2026-04-26 17:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:23 EST
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.models import User


def _make_user(
    session: Session,
    email: str = "raghu@softcons.net",
    tier: str = "apex_100k",
    is_admin: bool = True,
    disabled: bool = False,
) -> str:
    plaintext = generate_api_key()
    user = User(
        email=email,
        display_name=email.split("@")[0],
        api_key_hash=hash_api_key(plaintext),
        prop_tier=tier,
        is_admin=is_admin,
        disabled=disabled,
    )
    session.add(user)
    session.commit()
    return plaintext


def test_me_requires_api_key(client: TestClient) -> None:
    resp = client.get("/me")
    assert resp.status_code == 401
    assert "missing" in resp.json()["detail"].lower()


def test_me_rejects_unknown_key(client: TestClient) -> None:
    resp = client.get("/me", headers={"X-API-Key": "ofa_doesnotexist"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_me_accepts_valid_key(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session)
    resp = client.get("/me", headers={"X-API-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "raghu@softcons.net"
    assert body["prop_tier"] == "apex_100k"
    assert body["is_admin"] is True
    assert body["risk_template"] is not None
    assert body["risk_template"]["account_size_usd"] == 100_000


def test_me_rejects_disabled_user(client: TestClient, db_session: Session) -> None:
    key = _make_user(db_session, email="disabled@x.com", disabled=True)
    resp = client.get("/me", headers={"X-API-Key": key})
    assert resp.status_code == 401


def test_hash_api_key_is_deterministic() -> None:
    a = hash_api_key("plaintext", salt="salt-x")
    b = hash_api_key("plaintext", salt="salt-x")
    assert a == b
    c = hash_api_key("plaintext", salt="salt-y")
    assert a != c


def test_generate_api_key_is_unique_and_prefixed() -> None:
    keys = {generate_api_key() for _ in range(50)}
    assert len(keys) == 50
    assert all(k.startswith("ofa_") for k in keys)
