"""
File:        packages/shared/src/orderflow_shared/replay/sink.py
Created:     2026-04-26 18:51 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:51 EST

Change Log:
- 2026-04-26 18:51 EST | 1.0.0 | Phase 1C: HTTP and WebSocket sinks for replay.

Two sinks for pushing events into the running service:

- HTTPSink:      one POST per event to /ingest/event. Synchronous; easy to
                 test with FastAPI TestClient; fine for slow rates.
- WebSocketSink: persistent connection to /ws/nt-ingest. Lower per-event
                 overhead; required for high-frequency replay or production.

Both accept a stream of `Event` (the discriminated union from
orderflow_api.services.orderbook.events).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

import httpx

from orderflow_api.services.orderbook.events import Event


class Sink(Protocol):
    def push(self, event: Event) -> None: ...
    def close(self) -> None: ...


@dataclass
class HTTPSink:
    """Synchronous POST-per-event sink.

    Useful for tests, low-volume replay, and ad-hoc seeding. Use WebSocketSink
    when pumping more than ~10 events/sec.
    """

    base_url: str
    api_key: str
    timeout_seconds: float = 5.0
    client: httpx.Client | None = None
    sent: int = 0
    failed: int = 0
    _last_error: str | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout_seconds)

    def push(self, event: Event) -> None:
        assert self.client is not None
        try:
            resp = self.client.post(
                f"{self.base_url.rstrip('/')}/ingest/event",
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
                content=event.model_dump_json(),
            )
            if resp.status_code == 200:
                self.sent += 1
            else:
                self.failed += 1
                self._last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            self._last_error = str(exc)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None


@dataclass
class WebSocketSink:
    """Async-backed persistent WebSocket connection to /ws/nt-ingest.

    Use via `await WebSocketSink(...).run(events)` from an asyncio event loop.
    The sync `push()` / `close()` methods are NOT supported; use `run` instead.
    """

    url: str
    api_key: str
    sent: int = 0
    failed: int = 0
    _last_error: str | None = None

    def _connect_url(self) -> str:
        sep = "&" if "?" in self.url else "?"
        return f"{self.url}{sep}api_key={self.api_key}"

    async def run(self, events: Iterable[Event], pace_realtime: bool = False) -> dict[str, Any]:
        from datetime import datetime, timezone

        import websockets

        url = self._connect_url()
        first_ts: datetime | None = None
        wall_start = datetime.now(timezone.utc)
        async with websockets.connect(url) as ws:
            for event in events:
                if pace_realtime:
                    if first_ts is None:
                        first_ts = event.ts_utc
                    target_offset = (event.ts_utc - first_ts).total_seconds()
                    elapsed = (datetime.now(timezone.utc) - wall_start).total_seconds()
                    sleep_for = target_offset - elapsed
                    if sleep_for > 0:
                        await asyncio.sleep(sleep_for)
                await ws.send(event.model_dump_json())
                ack_raw = await ws.recv()
                ack = json.loads(ack_raw)
                if ack.get("type") == "ack":
                    self.sent += 1
                else:
                    self.failed += 1
                    self._last_error = ack_raw
        return {"sent": self.sent, "failed": self.failed, "last_error": self._last_error}

    def close(self) -> None:
        pass

    def push(self, event: Event) -> None:
        raise NotImplementedError("WebSocketSink only supports the async run() method")
