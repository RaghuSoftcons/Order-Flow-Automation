"""
File:        tests/unit/test_replay_synthetic.py
Created:     2026-04-26 18:54 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:54 EST
"""

from __future__ import annotations

from orderflow_api.services.orderbook.events import DepthEvent, TradeEvent
from orderflow_shared.replay.synthetic import SyntheticConfig, SyntheticSource


def test_default_source_produces_events() -> None:
    source = SyntheticSource(config=SyntheticConfig(duration_seconds=2.0))
    events = list(source)
    assert len(events) > 0
    assert any(isinstance(e, DepthEvent) for e in events)
    assert any(isinstance(e, TradeEvent) for e in events)


def test_events_are_chronological() -> None:
    source = SyntheticSource(config=SyntheticConfig(duration_seconds=5.0))
    events = list(source)
    timestamps = [e.ts_utc for e in events]
    assert timestamps == sorted(timestamps)


def test_seed_determines_output() -> None:
    src1 = SyntheticSource(config=SyntheticConfig(duration_seconds=3.0, seed=42))
    src2 = SyntheticSource(config=SyntheticConfig(duration_seconds=3.0, seed=42))
    e1 = list(src1)
    e2 = list(src2)
    assert len(e1) == len(e2)
    # Trades have random aggressor/size; check they line up
    trades1 = [(e.size, e.aggressor) for e in e1 if isinstance(e, TradeEvent)]
    trades2 = [(e.size, e.aggressor) for e in e2 if isinstance(e, TradeEvent)]
    assert trades1 == trades2


def test_different_seeds_diverge() -> None:
    src1 = SyntheticSource(config=SyntheticConfig(duration_seconds=3.0, seed=1))
    src2 = SyntheticSource(config=SyntheticConfig(duration_seconds=3.0, seed=2))
    trades1 = [(e.size, e.aggressor) for e in src1 if isinstance(e, TradeEvent)]
    trades2 = [(e.size, e.aggressor) for e in src2 if isinstance(e, TradeEvent)]
    assert trades1 != trades2


def test_depth_events_have_configured_levels() -> None:
    cfg = SyntheticConfig(duration_seconds=1.0, levels_per_side=5)
    source = SyntheticSource(config=cfg)
    depth_events = [e for e in source if isinstance(e, DepthEvent)]
    assert depth_events
    for de in depth_events:
        assert len(de.bids) == 5
        assert len(de.asks) == 5


def test_depth_top_size_is_largest() -> None:
    source = SyntheticSource(config=SyntheticConfig(duration_seconds=1.0, levels_per_side=5))
    depth = next(e for e in source if isinstance(e, DepthEvent))
    sizes_bids = [lvl.size for lvl in depth.bids]
    assert sizes_bids[0] >= sizes_bids[-1]  # near-touch bigger than far


def test_symbol_propagates_to_events() -> None:
    source = SyntheticSource(config=SyntheticConfig(symbol="NQ", duration_seconds=1.0))
    for event in source:
        assert event.symbol == "NQ"
        assert "NQ" in event.contract


def test_prices_round_to_tick_size() -> None:
    source = SyntheticSource(config=SyntheticConfig(symbol="ES", duration_seconds=2.0, seed=7))
    for event in source:
        if isinstance(event, DepthEvent):
            for lvl in event.bids + event.asks:
                # ES tick = 0.25; price * 4 must be integer
                assert abs(lvl.price * 4 - round(lvl.price * 4)) < 1e-9
        else:
            assert abs(event.price * 4 - round(event.price * 4)) < 1e-9


def test_event_count_scales_with_duration() -> None:
    short = list(SyntheticSource(config=SyntheticConfig(duration_seconds=1.0)))
    long = list(SyntheticSource(config=SyntheticConfig(duration_seconds=10.0)))
    assert len(long) > len(short) * 5  # roughly 10x


def test_trade_size_distribution_includes_sweeps() -> None:
    """With non-zero sweep_probability and enough events, we should see at least one large trade."""
    cfg = SyntheticConfig(
        duration_seconds=30.0,
        trade_event_rate_hz=10.0,
        sweep_probability=0.10,
        seed=123,
    )
    trades = [e for e in SyntheticSource(config=cfg) if isinstance(e, TradeEvent)]
    sweeps = [t for t in trades if t.size >= 20]
    assert len(sweeps) >= 1
