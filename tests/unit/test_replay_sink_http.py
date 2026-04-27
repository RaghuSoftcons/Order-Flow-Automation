"""
File:        tests/unit/test_replay_sink_http.py
Created:     2026-04-26 18:55 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:55 EST

End-to-end: synthetic source → HTTPSink → /ingest/event (TestClient) → registry.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.models import User
from orderflow_api.services.registry import get_registry
from orderflow_shared.replay.sink import HTTPSink
from orderflow_shared.replay.synthetic import SyntheticConfig, SyntheticSource


@pytest.fixture
def admin_key(db_session: Session) -> str:
    plaintext = generate_api_key()
    user = User(
        email="admin@x.com",
        display_name="Admin",
        api_key_hash=hash_api_key(plaintext),
        prop_tier="apex_100k",
        is_admin=True,
    )
    db_session.add(user)
    db_session.commit()
    return plaintext


def test_http_sink_pushes_events_to_test_client(client: TestClient, admin_key: str) -> None:
    """HTTPSink talks to the running TestClient via httpx using the same in-process app."""
    # Wire HTTPSink's client to the TestClient by reusing the app via httpx's MockTransport
    transport = httpx.WSGITransport(app=None)  # placeholder; we'll override below

    class TestClientTransport(httpx.BaseTransport):
        def __init__(self, tc: TestClient) -> None:
            self._tc = tc

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            method = request.method
            url = request.url.path
            if request.url.query:
                url = f"{url}?{request.url.query.decode()}"
            resp = self._tc.request(
                method,
                url,
                headers={k: v for k, v in request.headers.items()},
                content=request.content,
            )
            return httpx.Response(resp.status_code, headers=dict(resp.headers), content=resp.content)

    sink = HTTPSink(
        base_url="http://testserver",
        api_key=admin_key,
        client=httpx.Client(transport=TestClientTransport(client)),
    )

    events = list(SyntheticSource(config=SyntheticConfig(duration_seconds=1.0, seed=99)))
    assert events
    for event in events:
        sink.push(event)

    assert sink.failed == 0
    assert sink.sent == len(events)

    es_book = get_registry().get("ES")
    assert es_book.best_bid() is not None
    assert es_book.best_ask() is not None


def test_http_sink_records_failure_on_bad_auth(client: TestClient) -> None:
    class TestClientTransport(httpx.BaseTransport):
        def __init__(self, tc: TestClient) -> None:
            self._tc = tc

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            resp = self._tc.request(
                request.method,
                request.url.path,
                headers={k: v for k, v in request.headers.items()},
                content=request.content,
            )
            return httpx.Response(resp.status_code, headers=dict(resp.headers), content=resp.content)

    sink = HTTPSink(
        base_url="http://testserver",
        api_key="ofa_invalid",
        client=httpx.Client(transport=TestClientTransport(client)),
    )
    event = next(iter(SyntheticSource(config=SyntheticConfig(duration_seconds=0.5, seed=1))))
    sink.push(event)
    assert sink.failed == 1
    assert sink.sent == 0
    assert sink._last_error is not None


def test_databento_source_raises_clear_error_when_sdk_missing() -> None:
    from orderflow_shared.replay.databento_source import DatabentoMBP10Source

    src = DatabentoMBP10Source(file_path="nonexistent.dbn")
    # Iterating should raise the install hint
    with pytest.raises(RuntimeError, match="Databento SDK not installed"):
        next(iter(src))


def test_replay_cli_help_runs() -> None:
    """CLI argparse builds without error."""
    import sys

    from orderflow_shared.replay.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    # argparse exits 0 on --help
    assert exc_info.value.code == 0
