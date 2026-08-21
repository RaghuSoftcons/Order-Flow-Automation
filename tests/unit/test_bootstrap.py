"""
File:        tests/unit/test_bootstrap.py
Created:     2026-08-17 19:03 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-08-17 19:03 EST
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orderflow_api.config import get_settings


@pytest.fixture
def bootstrap_token(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-bootstrap-token-abc123"
    monkeypatch.setenv("BOOTSTRAP_TOKEN", token)
    get_settings.cache_clear()
    return token


def test_bootstrap_returns_404_when_token_env_unset(client: TestClient) -> None:
    resp = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": "anything"})
    assert resp.status_code == 404


def test_bootstrap_rejects_missing_header(client: TestClient, bootstrap_token: str) -> None:
    resp = client.post("/admin/bootstrap")
    assert resp.status_code == 401


def test_bootstrap_rejects_wrong_token(client: TestClient, bootstrap_token: str) -> None:
    resp = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": "wrong-value"})
    assert resp.status_code == 401


def test_bootstrap_seeds_three_users_first_call(client: TestClient, bootstrap_token: str) -> None:
    resp = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": bootstrap_token})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 3
    created = [r for r in body["results"] if r["status"] == "created"]
    assert len(created) == 3
    admin = next(r for r in created if r["is_admin"])
    assert admin["api_key"].startswith("ofa_")
    assert "notice" in body


def test_bootstrap_is_idempotent(client: TestClient, bootstrap_token: str) -> None:
    r1 = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": bootstrap_token})
    assert r1.status_code == 200
    r2 = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": bootstrap_token})
    assert r2.status_code == 200
    for row in r2.json()["results"]:
        assert row["status"] == "exists"
        assert "api_key" not in row  # existing users don't leak a new key


def test_admin_key_from_bootstrap_works_on_me(client: TestClient, bootstrap_token: str) -> None:
    resp = client.post("/admin/bootstrap", headers={"X-Bootstrap-Token": bootstrap_token})
    admin_row = next(r for r in resp.json()["results"] if r.get("is_admin"))
    key = admin_row["api_key"]
    me = client.get("/me", headers={"X-API-Key": key})
    assert me.status_code == 200
    assert me.json()["is_admin"] is True
