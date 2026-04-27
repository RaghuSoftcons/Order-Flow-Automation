"""
File:        apps/api/src/orderflow_api/routers/feed.py
Created:     2026-04-26 18:32 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:32 EST

Change Log:
- 2026-04-26 18:32 EST | 1.0.0 | Phase 1B: feed health endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from orderflow_api.auth import require_user
from orderflow_api.models import User
from orderflow_api.services.registry import get_registry

router = APIRouter()

# Stale threshold (seconds) before we consider a feed unhealthy.
STALE_THRESHOLD_SECONDS = 10.0


@router.get("/health/feed")
def feed_health(_user: User = Depends(require_user)) -> dict[str, Any]:
    registry = get_registry()
    ages = registry.feed_age_seconds()
    per_symbol = {}
    overall_status = "ok"
    for sym, age in ages.items():
        if age is None:
            status = "no_data"
            if overall_status == "ok":
                overall_status = "no_data"
        elif age > STALE_THRESHOLD_SECONDS:
            status = "stale"
            overall_status = "stale"
        else:
            status = "fresh"
        per_symbol[sym] = {"status": status, "age_seconds": age}
    return {
        "status": overall_status,
        "stale_threshold_seconds": STALE_THRESHOLD_SECONDS,
        "symbols": per_symbol,
    }
