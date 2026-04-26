"""
File:        tests/unit/test_metrics.py
Created:     2026-04-26 18:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:23 EST
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orderflow_api.services.orderbook import (
    DepthEvent,
    DepthLevel,
    OrderBook,
    TradeEvent,
    compute_metrics,
)
from orderflow_api.services.orderbook.metrics import (
    book_pressure,
    imbalance,
    largest_resting,
    recent_sweep_stats,
)


def _ts(seconds: float = 0) -> datetime:
    return datetime.fromtimestamp(1_777_898_400 + seconds, tz=timezone.utc)


def _book_with(
    bids: list[tuple[float, int]],
    asks: list[tuple[float, int]],
    trades: list[tuple[float, int, str, float]] | None = None,
) -> OrderBook:
    book = OrderBook(symbol="ES")
    book.apply_depth(
        DepthEvent(
            symbol="ES",
            contract="ES 06-26",
            ts_utc=_ts(0),
            bids=[DepthLevel(price=p, size=s, orders=1) for p, s in bids],
            asks=[DepthLevel(price=p, size=s, orders=1) for p, s in asks],
        )
    )
    for price, size, aggressor, ts_off in trades or []:
        book.apply_trade(
            TradeEvent(
                symbol="ES",
                contract="ES 06-26",
                ts_utc=_ts(ts_off),
                price=price,
                size=size,
                aggressor=aggressor,  # type: ignore[arg-type]
            )
        )
    return book


# --- imbalance ---


def test_imbalance_balanced_book_returns_zero() -> None:
    book = _book_with(bids=[(100, 50)], asks=[(101, 50)])
    assert imbalance(book, n=5) == 0.0


def test_imbalance_bid_heavy_returns_positive() -> None:
    book = _book_with(bids=[(100, 100)], asks=[(101, 25)])
    assert imbalance(book, n=5) == pytest.approx(0.6)


def test_imbalance_ask_heavy_returns_negative() -> None:
    book = _book_with(bids=[(100, 25)], asks=[(101, 100)])
    assert imbalance(book, n=5) == pytest.approx(-0.6)


def test_imbalance_empty_book_returns_none() -> None:
    book = OrderBook(symbol="ES")
    assert imbalance(book) is None


def test_imbalance_only_uses_top_n() -> None:
    book = _book_with(
        bids=[(100, 10), (99, 10), (98, 10), (97, 10), (96, 10), (95, 1000)],
        asks=[(101, 10), (102, 10), (103, 10), (104, 10), (105, 10)],
    )
    # Top 5 each: 50 vs 50 → 0
    assert imbalance(book, n=5) == 0.0


# --- largest_resting ---


def test_largest_resting_picks_max_size() -> None:
    book = _book_with(bids=[(100, 50), (99, 200), (98, 75)], asks=[(101, 30)])
    largest = largest_resting(book, "bid", n=10)
    assert largest is not None
    assert largest["price"] == 99
    assert largest["size"] == 200


def test_largest_resting_returns_none_for_empty_side() -> None:
    book = _book_with(bids=[], asks=[(101, 30)])
    assert largest_resting(book, "bid") is None


# --- book_pressure ---


def test_book_pressure_decays_with_distance() -> None:
    book = _book_with(bids=[(100, 100), (99, 100)], asks=[(101, 100)])
    # mid = 100.5
    # bid pressure: 100/(1+0.5) + 100/(1+1.5) = 66.67 + 40 = 106.67
    # ask pressure: 100/(1+0.5) = 66.67
    pb = book_pressure(book, "bid", n=10)
    pa = book_pressure(book, "ask", n=10)
    assert pb is not None and pa is not None
    assert pb > pa  # extra bid level adds pressure


def test_book_pressure_returns_none_for_empty_book() -> None:
    book = OrderBook(symbol="ES")
    assert book_pressure(book, "bid") is None


# --- sweep stats ---


def test_recent_sweep_no_trades() -> None:
    book = _book_with(bids=[(100, 50)], asks=[(101, 50)])
    stats = recent_sweep_stats(book, window_seconds=5, now=_ts(0))
    assert stats == {
        "recent_sweep_count": 0,
        "recent_sweep_volume": 0,
        "recent_buy_volume": 0,
        "recent_sell_volume": 0,
    }


def test_recent_sweep_flags_oversized_trades() -> None:
    book = _book_with(
        bids=[(100, 50)],
        asks=[(101, 50)],
        trades=[
            (101, 1, "buy", 0),
            (101, 1, "buy", 1),
            (101, 1, "buy", 2),
            (101, 1, "buy", 3),
            (101, 50, "buy", 4),  # 50x larger than median
        ],
    )
    stats = recent_sweep_stats(book, window_seconds=10, now=_ts(5))
    assert stats["recent_sweep_count"] == 1
    assert stats["recent_sweep_volume"] == 50
    assert stats["recent_buy_volume"] == 54


def test_recent_sweep_volume_split_by_aggressor() -> None:
    book = _book_with(
        bids=[(100, 50)],
        asks=[(101, 50)],
        trades=[
            (101, 5, "buy", 0),
            (100, 8, "sell", 1),
            (101, 3, "buy", 2),
        ],
    )
    stats = recent_sweep_stats(book, window_seconds=10, now=_ts(3))
    assert stats["recent_buy_volume"] == 8
    assert stats["recent_sell_volume"] == 8


# --- compute_metrics integration ---


def test_compute_metrics_returns_full_dict() -> None:
    book = _book_with(bids=[(100, 50), (99, 25)], asks=[(101, 75), (102, 30)])
    m = compute_metrics(book, now=_ts(0))
    assert m["symbol"] == "ES"
    assert m["contract"] == "ES 06-26"
    assert m["best_bid"] == 100
    assert m["best_ask"] == 101
    assert m["mid"] == 100.5
    assert m["spread"] == 1.0
    assert m["imbalance_top5"] == pytest.approx((75 - 105) / (75 + 105))
    assert m["largest_resting_bid"]["price"] == 100
    assert m["largest_resting_ask"]["price"] == 101
    assert m["book_pressure_bids"] is not None
    assert m["book_pressure_asks"] is not None
    assert m["book_pressure_ratio"] is not None
    assert m["recent_sweep_count_5s"] == 0


def test_compute_metrics_handles_empty_book() -> None:
    book = OrderBook(symbol="ES")
    m = compute_metrics(book, now=_ts(0))
    assert m["best_bid"] is None
    assert m["best_ask"] is None
    assert m["mid"] is None
    assert m["imbalance_top5"] is None
    assert m["largest_resting_bid"] is None
    assert m["recent_sweep_count_5s"] == 0
