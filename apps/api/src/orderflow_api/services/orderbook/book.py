"""
File:        apps/api/src/orderflow_api/services/orderbook/book.py
Created:     2026-04-26 18:19 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:19 EST

Change Log:
- 2026-04-26 18:19 EST | 1.0.0 | Phase 1A: in-memory L2 order book.

Per-symbol book state. Uses MBP (price-aggregated) updates from depth events
and a rolling tape of recent trades.

Performance notes:
- Floats as price keys (rounded to tick) — fine for our scale (3 traders,
  30s snapshot cadence). Switch to int-tick keys if/when latency matters.
- Trade tape is a deque with a soft max — keeps last N trades in memory.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from orderflow_api.services.orderbook.events import DepthEvent, TradeEvent


@dataclass(frozen=True)
class PriceLevel:
    price: float
    size: int
    orders: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return {"price": self.price, "size": self.size, "orders": self.orders}


@dataclass(frozen=True)
class Trade:
    price: float
    size: int
    aggressor: str  # "buy" | "sell"
    ts_utc: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "price": self.price,
            "size": self.size,
            "aggressor": self.aggressor,
            "ts_utc": self.ts_utc.isoformat(),
        }


@dataclass
class OrderBook:
    symbol: str
    contract: str = ""
    bids: dict[float, PriceLevel] = field(default_factory=dict)
    asks: dict[float, PriceLevel] = field(default_factory=dict)
    last_update_ts: datetime | None = None
    trade_tape: deque[Trade] = field(default_factory=lambda: deque(maxlen=10_000))

    def apply_depth(self, event: DepthEvent) -> None:
        """Replace book snapshot with the depth event's contents.

        Depth events from MDP-3 are typically full top-N snapshots; we treat
        them as authoritative replacements rather than merging.
        """
        if event.symbol != self.symbol:
            raise ValueError(f"book is {self.symbol!r}, got depth for {event.symbol!r}")
        self.contract = event.contract
        self.bids = {
            level.price: PriceLevel(price=level.price, size=level.size, orders=level.orders)
            for level in event.bids
            if level.size > 0
        }
        self.asks = {
            level.price: PriceLevel(price=level.price, size=level.size, orders=level.orders)
            for level in event.asks
            if level.size > 0
        }
        self.last_update_ts = event.ts_utc

    def apply_trade(self, event: TradeEvent) -> None:
        if event.symbol != self.symbol:
            raise ValueError(f"book is {self.symbol!r}, got trade for {event.symbol!r}")
        self.contract = event.contract
        self.trade_tape.append(
            Trade(
                price=event.price,
                size=event.size,
                aggressor=event.aggressor,
                ts_utc=event.ts_utc,
            )
        )
        self.last_update_ts = event.ts_utc

    def top_bids(self, n: int = 10) -> list[PriceLevel]:
        return sorted(self.bids.values(), key=lambda lvl: lvl.price, reverse=True)[:n]

    def top_asks(self, n: int = 10) -> list[PriceLevel]:
        return sorted(self.asks.values(), key=lambda lvl: lvl.price)[:n]

    def best_bid(self) -> PriceLevel | None:
        if not self.bids:
            return None
        return max(self.bids.values(), key=lambda lvl: lvl.price)

    def best_ask(self) -> PriceLevel | None:
        if not self.asks:
            return None
        return min(self.asks.values(), key=lambda lvl: lvl.price)

    def mid(self) -> float | None:
        bb = self.best_bid()
        ba = self.best_ask()
        if bb is None or ba is None:
            return None
        return (bb.price + ba.price) / 2

    def spread(self) -> float | None:
        bb = self.best_bid()
        ba = self.best_ask()
        if bb is None or ba is None:
            return None
        return ba.price - bb.price

    def recent_trades(self, window_seconds: float, now: datetime | None = None) -> list[Trade]:
        if not self.trade_tape:
            return []
        cutoff = (now or datetime.now(timezone.utc)).timestamp() - window_seconds
        return [t for t in self.trade_tape if t.ts_utc.timestamp() >= cutoff]

    def is_empty(self) -> bool:
        return not self.bids and not self.asks


class OrderBookRegistry:
    """Holds one OrderBook per symbol. Thread-unsafe by design (single owner)."""

    def __init__(self, symbols: Iterable[str]) -> None:
        self._books: dict[str, OrderBook] = {sym: OrderBook(symbol=sym) for sym in symbols}

    def get(self, symbol: str) -> OrderBook:
        if symbol not in self._books:
            self._books[symbol] = OrderBook(symbol=symbol)
        return self._books[symbol]

    def symbols(self) -> list[str]:
        return list(self._books.keys())

    def apply(self, event: DepthEvent | TradeEvent) -> None:
        book = self.get(event.symbol)
        if isinstance(event, DepthEvent):
            book.apply_depth(event)
        else:
            book.apply_trade(event)

    def feed_age_seconds(self, now: datetime | None = None) -> dict[str, float | None]:
        """Per-symbol seconds since last update (None if never updated)."""
        now_ts = (now or datetime.now(timezone.utc)).timestamp()
        out: dict[str, float | None] = {}
        for sym, book in self._books.items():
            out[sym] = (now_ts - book.last_update_ts.timestamp()) if book.last_update_ts else None
        return out
