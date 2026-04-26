"""
File:        tests/unit/test_health.py
Created:     2026-04-26 17:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:23 EST
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["dependencies"]["database"]["status"] == "ok"
    assert body["dependencies"]["cache"]["status"] == "ok"


def test_health_database_kind_is_sqlite_in_tests(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["dependencies"]["database"]["kind"] == "sqlite"


def test_health_cache_kind_is_fakeredis_in_tests(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["dependencies"]["cache"]["kind"] == "fakeredis"
