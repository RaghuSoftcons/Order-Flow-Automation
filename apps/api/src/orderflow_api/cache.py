"""
File:        apps/api/src/orderflow_api/cache.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.
- 2026-04-26 18:00 EST | 1.0.1 | Production fix: fakeredis is dev-only.
  When REDIS_URL is unset and fakeredis is unavailable, return None and
  report "not_configured" in /health instead of crashing.

Redis client factory.
- If REDIS_URL is set: uses real Redis (Railway Redis plugin in prod)
- Else if fakeredis is installed (dev/test): uses in-process fakeredis
- Else: returns None; /health reports "not_configured"

Phase 0 doesn't use the cache for anything critical; Phase 1 will require
either Redis plugin attached or fakeredis available.
"""

from __future__ import annotations

from typing import Any

from orderflow_api.config import get_settings

_client: Any = None
_unavailable_reason: str | None = None


def get_cache() -> Any:
    """Returns a redis-compatible client, or None if no cache backend is available."""
    global _client, _unavailable_reason
    if _client is not None:
        return _client
    settings = get_settings()
    if settings.redis_url:
        import redis

        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return _client
    try:
        import fakeredis  # type: ignore[import-not-found]

        _client = fakeredis.FakeStrictRedis(decode_responses=True)
        return _client
    except ImportError:
        _unavailable_reason = "REDIS_URL not set and fakeredis not installed (prod build)"
        return None


def reset_cache_for_tests() -> None:
    global _client, _unavailable_reason
    _client = None
    _unavailable_reason = None


def cache_health() -> dict[str, Any]:
    """Returns a small dict for /health endpoint reporting."""
    client = get_cache()
    if client is None:
        return {"status": "not_configured", "kind": "none", "reason": _unavailable_reason}
    try:
        client.ping()
        kind = "fakeredis" if get_settings().use_fakeredis else "redis"
        return {"status": "ok", "kind": kind}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "kind": "unknown", "error": str(exc)}
