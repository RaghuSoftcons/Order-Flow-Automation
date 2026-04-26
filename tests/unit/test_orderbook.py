"""
File:        tests/unit/test_orderbook.py
Created:     2026-04-26 18:22 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:22 EST
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orderflow_api.services.orderbook import (
    DepthEvent,
    DepthLevel,
    OrderBook,
    TradeEvent,
)
from orderflow_api.services.orderbook.book import OrderBookRegistry


def _ts(seconds: float = 0) -> datetime:
    return datetime(2026, 4, 27, 14, 30, 0, tzinfo=timezone.utc).fromtimestamp(
        1_777_898_400 + seconds, tz=timezone.utc
    )


def _make_depth(
    symbol: str = "ES",
    bids: list[tuple[float, int, int]] | None = None,
    asks: list[tuple[float, int, int]] | None = None,
    ts_offset: float = 0,
) -> DepthEvent:
    return DepthEvent(
        symbol=symbol,
        contract=f"{symbol} 06-26",
        ts_utc=_ts(ts_offset),
        bids=[DepthLevel(price=p, size=s, orders=o) for p, s, o in (bids or [])],
        asks=[DepthLevel(price=p, size=s, orders=o) for p, s, o in (asks or [])],
    )


def _make_trade(
    symbol: str = "ES",
    price: float = 5285.25,
    size: int = 5,
    aggressor: str = "buy",
    ts_offset: float = 0,
) -> TradeEvent:
    return TradeEvent(
        symbol=symbol,
        contract=f"{symbol} 06-26",
        ts_utc=_ts(ts_offset),
        price=price,
        size=size,
        aggressor=aggressor,  # type: ignore[arg-type]
    )


# --- OrderBook ---


def test_book_starts_empty() -> None:
    book = OrderBook(symbol="ES")
    assert book.is_empty()
    assert book.best_bid() is None
    assert book.best_ask() is None
    assert book.mid() is None
    assert book.spread() is None


def test_apply_depth_populates_book() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(bids=[(5285.00, 100, 5), (5284.75, 50, 3)], asks=[(5285.25, 75, 4)]))
    assert not book.is_empty()
    assert book.best_bid().price == 5285.00
    assert book.best_ask().price == 5285.25
    assert book.mid() == 5285.125
    assert book.spread() == 0.25
    assert book.contract == "ES 06-26"


def test_apply_depth_replaces_snapshot() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(bids=[(5285.00, 100, 5)], asks=[(5285.25, 75, 4)]))
    book.apply_depth(_make_depth(bids=[(5286.00, 200, 8)], asks=[(5286.25, 150, 6)]))
    assert book.best_bid().price == 5286.00
    assert 5285.00 not in book.bids
    assert book.best_ask().price == 5286.25


def test_apply_depth_drops_zero_size_levels() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(bids=[(5285.00, 100, 5), (5284.75, 0, 0)], asks=[]))
    assert 5285.00 in book.bids
    assert 5284.75 not in book.bids


def test_apply_depth_rejects_wrong_symbol() -> None:
    book = OrderBook(symbol="ES")
    with pytest.raises(ValueError, match="ES"):
        book.apply_depth(_make_depth(symbol="NQ"))


def test_top_bids_sorted_descending() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(bids=[(5284.75, 50, 3), (5285.00, 100, 5), (5284.50, 25, 2)]))
    top = book.top_bids(n=3)
    assert [lvl.price for lvl in top] == [5285.00, 5284.75, 5284.50]


def test_top_asks_sorted_ascending() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(asks=[(5285.50, 100, 5), (5285.25, 50, 3), (5285.75, 25, 2)]))
    top = book.top_asks(n=3)
    assert [lvl.price for lvl in top] == [5285.25, 5285.50, 5285.75]


def test_top_n_limits_results() -> None:
    book = OrderBook(symbol="ES")
    book.apply_depth(_make_depth(bids=[(5285.00 - i * 0.25, 10, 1) for i in range(15)]))
    assert len(book.top_bids(n=5)) == 5
    assert len(book.top_bids(n=20)) == 15  # only 15 levels exist


def test_apply_trade_appends_to_tape() -> None:
    book = OrderBook(symbol="ES")
    book.apply_trade(_make_trade(price=5285.25, size=12, ts_offset=0))
    book.apply_trade(_make_trade(price=5285.25, size=8, aggressor="sell", ts_offset=1))
    assert len(book.trade_tape) == 2
    assert book.trade_tape[0].size == 12
    assert book.trade_tape[1].aggressor == "sell"


def test_apply_trade_updates_last_update_ts() -> None:
    book = OrderBook(symbol="ES")
    book.apply_trade(_make_trade(ts_offset=10))
    assert book.last_update_ts == _ts(10)


def test_recent_trades_window() -> None:
    book = OrderBook(symbol="ES")
    book.apply_trade(_make_trade(size=1, ts_offset=0))
    book.apply_trade(_make_trade(size=2, ts_offset=3))
    book.apply_trade(_make_trade(size=3, ts_offset=8))
    recent = book.recent_trades(window_seconds=5, now=_ts(8))
    sizes = sorted(t.size for t in recent)
    assert sizes == [2, 3]


def test_apply_trade_rejects_wrong_symbol() -> None:
    book = OrderBook(symbol="ES")
    with pytest.raises(ValueError):
        book.apply_trade(_make_trade(symbol="NQ"))


# --- Registry ---


def test_registry_routes_events_by_symbol() -> None:
    registry = OrderBookRegistry(symbols=["ES", "NQ"])
    registry.apply(_make_depth(symbol="ES", bids=[(5285.00, 100, 5)]))
    registry.apply(_make_depth(symbol="NQ", asks=[(20100.0, 50, 4)]))
    assert registry.get("ES").best_bid().price == 5285.00
    assert registry.get("NQ").best_ask().price == 20100.0


def test_registry_creates_book_on_demand() -> None:
    registry = OrderBookRegistry(symbols=["ES"])
    registry.apply(_make_depth(symbol="GC", bids=[(2300.00, 5, 1)]))
    assert "GC" in registry.symbols()


def test_registry_feed_age_returns_none_when_unset() -> None:
    registry = OrderBookRegistry(symbols=["ES", "NQ"])
    ages = registry.feed_age_seconds(now=_ts(100))
    assert ages == {"ES": None, "NQ": None}


def test_registry_feed_age_computes_seconds() -> None:
    registry = OrderBookRegistry(symbols=["ES"])
    registry.apply(_make_depth(symbol="ES", bids=[(5285.00, 100, 5)], ts_offset=0))
    ages = registry.feed_age_seconds(now=_ts(7))
    assert ages["ES"] == pytest.approx(7.0, abs=0.01)
