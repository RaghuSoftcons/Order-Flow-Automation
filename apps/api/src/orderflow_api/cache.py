"""
File:        apps/api/src/orderflow_api/cache.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.

Redis client factory. Uses real Redis (Railway plugin) when REDIS_URL is set,
otherwise falls back to fakeredis (in-process, dev only).

Phase 0 just exposes the client; Phase 1 uses it for live order book state
and pubsub fan-out.
"""

from __future__ import annotations

from typing import Any

from orderflow_api.config import get_settings

_client: Any = None


def get_cache() -> Any:
    """Returns a redis-compatible client (real Redis or fakeredis)."""
    global _client
    if _client is None:
        settings = get_settings()
        if settings.use_fakeredis:
            import fakeredis

            _client = fakeredis.FakeStrictRedis(decode_responses=True)
        else:
            import redis

            _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def reset_cache_for_tests() -> None:
    global _client
    _client = None


def cache_health() -> dict[str, Any]:
    """Returns a small dict for /health endpoint reporting."""
    try:
        client = get_cache()
        client.ping()
        kind = "fakeredis" if get_settings().use_fakeredis else "redis"
        return {"status": "ok", "kind": kind}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "kind": "unknown", "error": str(exc)}
