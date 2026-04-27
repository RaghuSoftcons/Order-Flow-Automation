"""
File:        apps/api/src/orderflow_api/routers/orderbook.py
Created:     2026-04-26 18:31 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:31 EST

Change Log:
- 2026-04-26 18:31 EST | 1.0.0 | Phase 1B: REST endpoints for order book reads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from orderflow_api.auth import require_user
from orderflow_api.models import User
from orderflow_api.services.orderbook.metrics import compute_metrics
from orderflow_api.services.registry import get_registry
from orderflow_shared.instruments import lookup_instrument

router = APIRouter()


def _serialize_book(symbol: str, levels: int) -> dict[str, Any]:
    book = get_registry().get(symbol)
    return {
        "symbol": book.symbol,
        "contract": book.contract,
        "last_update_ts": book.last_update_ts.isoformat() if book.last_update_ts else None,
        "feed_age_seconds": (
            (datetime.now(timezone.utc) - book.last_update_ts).total_seconds()
            if book.last_update_ts
            else None
        ),
        "bids": [lvl.to_dict() for lvl in book.top_bids(levels)],
        "asks": [lvl.to_dict() for lvl in book.top_asks(levels)],
        "manual_only_notice": "No orders are placed by this endpoint.",
    }


@router.get("/orderbook")
def orderbook(
    symbol: str = Query(..., min_length=1, max_length=10),
    levels: int = Query(10, ge=1, le=20),
    _user: User = Depends(require_user),
) -> dict[str, Any]:
    sym = symbol.upper()
    if lookup_instrument(sym) is None:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {sym}")
    return _serialize_book(sym, levels)


@router.get("/liquidity-snapshot")
def liquidity_snapshot(
    symbol: str = Query(..., min_length=1, max_length=10),
    _user: User = Depends(require_user),
) -> dict[str, Any]:
    """Compact, AI-friendly metrics view. Phase 2's Claude tools call this."""
    sym = symbol.upper()
    if lookup_instrument(sym) is None:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {sym}")
    book = get_registry().get(sym)
    metrics = compute_metrics(book)
    return {
        "metrics": dict(metrics),
        "manual_only_notice": "No orders are placed by this endpoint.",
    }


@router.get("/instrument")
def instrument(
    symbol: str = Query(..., min_length=1, max_length=10),
    _user: User = Depends(require_user),
) -> dict[str, Any]:
    spec = lookup_instrument(symbol)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {symbol.upper()}")
    return spec.to_dict()
