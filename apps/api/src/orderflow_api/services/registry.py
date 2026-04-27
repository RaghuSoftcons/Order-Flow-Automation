"""
File:        apps/api/src/orderflow_api/services/registry.py
Created:     2026-04-26 18:30 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:30 EST

Change Log:
- 2026-04-26 18:30 EST | 1.0.0 | Phase 1B: process-local OrderBookRegistry singleton.

The singleton is intentionally per-process (in-memory). Phase 0–2 runs as a
single Railway service so this is fine. Phase 3 splits services and we move
the live book to Redis; this module's API stays the same so callers don't
have to change.
"""

from __future__ import annotations

from orderflow_api.services.orderbook.book import OrderBookRegistry

DEFAULT_SYMBOLS = ("ES", "NQ", "GC", "SPY", "QQQ")

_registry: OrderBookRegistry | None = None


def get_registry() -> OrderBookRegistry:
    global _registry
    if _registry is None:
        _registry = OrderBookRegistry(symbols=DEFAULT_SYMBOLS)
    return _registry


def reset_registry_for_tests() -> None:
    global _registry
    _registry = None
