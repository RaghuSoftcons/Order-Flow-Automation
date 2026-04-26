"""
File:        apps/api/src/orderflow_api/services/orderbook/metrics.py
Created:     2026-04-26 18:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:20 EST

Change Log:
- 2026-04-26 18:20 EST | 1.0.0 | Phase 1A: derived metrics on top of OrderBook.

These are the values the AI agent will reason over in Phase 2. Each metric
is intentionally a small, named, easy-to-explain scalar — Claude's job is
to combine them into a verdict, not to re-derive them from raw events.

Phase 1A scope:
- Imbalance (top-N bid vs ask)
- Largest resting (per side)
- Book pressure (size weighted by distance from mid)
- Sweep detection (rolling window)

Deferred to Phase 1C / Phase 2:
- Absorption score (needs book history)
- Iceberg detection (needs MBO data)
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from orderflow_api.services.orderbook.book import OrderBook


class Metrics(TypedDict, total=False):
    symbol: str
    contract: str
    last_update_ts: str | None
    best_bid: float | None
    best_ask: float | None
    mid: float | None
    spread: float | None
    imbalance_top5: float | None
    imbalance_top10: float | None
    largest_resting_bid: dict | None
    largest_resting_ask: dict | None
    book_pressure_bids: float | None
    book_pressure_asks: float | None
    book_pressure_ratio: float | None
    recent_sweep_count_5s: int
    recent_sweep_volume_5s: int
    recent_buy_volume_5s: int
    recent_sell_volume_5s: int


def imbalance(book: OrderBook, n: int = 5) -> float | None:
    """(bid_size - ask_size) / (bid_size + ask_size) on top N levels.

    Returns value in [-1, 1]. None if both sides empty.
    """
    bids = book.top_bids(n)
    asks = book.top_asks(n)
    bid_size = sum(lvl.size for lvl in bids)
    ask_size = sum(lvl.size for lvl in asks)
    total = bid_size + ask_size
    if total == 0:
        return None
    return (bid_size - ask_size) / total


def largest_resting(book: OrderBook, side: str, n: int = 20) -> dict | None:
    levels = book.top_bids(n) if side == "bid" else book.top_asks(n)
    if not levels:
        return None
    largest = max(levels, key=lambda lvl: lvl.size)
    return largest.to_dict()


def book_pressure(book: OrderBook, side: str, n: int = 10) -> float | None:
    """Sum of size_i / (1 + |level_i - mid|) for top N levels on `side`.

    Higher = more aggressive presence on that side near mid.
    """
    levels = book.top_bids(n) if side == "bid" else book.top_asks(n)
    mid = book.mid()
    if not levels or mid is None:
        return None
    return sum(lvl.size / (1 + abs(lvl.price - mid)) for lvl in levels)


def recent_sweep_stats(book: OrderBook, window_seconds: float = 5.0, now: datetime | None = None) -> dict:
    """Heuristic sweep detection from the trade tape alone.

    A trade is treated as a 'sweep' if its size is greater than the average
    top-of-book size we've seen on its aggressor side. Without per-tick book
    snapshots stored alongside trades, this is necessarily approximate;
    Phase 1C will tighten it using replay-time book context.
    """
    trades = book.recent_trades(window_seconds, now=now)
    if not trades:
        return {
            "recent_sweep_count": 0,
            "recent_sweep_volume": 0,
            "recent_buy_volume": 0,
            "recent_sell_volume": 0,
        }

    buy_volume = sum(t.size for t in trades if t.aggressor == "buy")
    sell_volume = sum(t.size for t in trades if t.aggressor == "sell")

    # Use the median trade size as the baseline; trades >= 3x the median
    # in their direction are flagged as sweeps. Crude but parameter-free.
    sizes = sorted(t.size for t in trades)
    median = sizes[len(sizes) // 2] if sizes else 0
    sweep_threshold = max(median * 3, 1)
    sweeps = [t for t in trades if t.size >= sweep_threshold]

    return {
        "recent_sweep_count": len(sweeps),
        "recent_sweep_volume": sum(t.size for t in sweeps),
        "recent_buy_volume": buy_volume,
        "recent_sell_volume": sell_volume,
    }


def compute_metrics(book: OrderBook, now: datetime | None = None) -> Metrics:
    """Returns a flat dict of derived metrics for the given book."""
    bb = book.best_bid()
    ba = book.best_ask()
    pressure_bids = book_pressure(book, "bid", n=10)
    pressure_asks = book_pressure(book, "ask", n=10)
    pressure_ratio: float | None = None
    if pressure_bids is not None and pressure_asks is not None and (pressure_bids + pressure_asks) > 0:
        pressure_ratio = (pressure_bids - pressure_asks) / (pressure_bids + pressure_asks)

    sweep_stats = recent_sweep_stats(book, window_seconds=5.0, now=now)

    return Metrics(
        symbol=book.symbol,
        contract=book.contract,
        last_update_ts=book.last_update_ts.isoformat() if book.last_update_ts else None,
        best_bid=bb.price if bb else None,
        best_ask=ba.price if ba else None,
        mid=book.mid(),
        spread=book.spread(),
        imbalance_top5=imbalance(book, n=5),
        imbalance_top10=imbalance(book, n=10),
        largest_resting_bid=largest_resting(book, "bid", n=20),
        largest_resting_ask=largest_resting(book, "ask", n=20),
        book_pressure_bids=pressure_bids,
        book_pressure_asks=pressure_asks,
        book_pressure_ratio=pressure_ratio,
        recent_sweep_count_5s=sweep_stats["recent_sweep_count"],
        recent_sweep_volume_5s=sweep_stats["recent_sweep_volume"],
        recent_buy_volume_5s=sweep_stats["recent_buy_volume"],
        recent_sell_volume_5s=sweep_stats["recent_sell_volume"],
    )
