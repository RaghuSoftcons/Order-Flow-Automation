"""
File:        packages/shared/src/orderflow_shared/replay/synthetic.py
Created:     2026-04-26 18:50 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:50 EST

Change Log:
- 2026-04-26 18:50 EST | 1.0.0 | Phase 1C: deterministic synthetic event source.

Generates plausible-looking depth + trade events for a symbol. Good enough
for end-to-end testing of the order book engine, derived metrics, and the
Phase 2 AI tools, without paying for live data.

Determinism: pass `seed` to get reproducible output. Two runs with the same
seed produce byte-identical event streams (useful for regression tests).

What this is NOT: a market simulator. Prices walk randomly with a configurable
drift; depth shapes are heuristic; sweeps are sprinkled in. A real Databento
tape (Phase 1C optional adapter) gives you actual market microstructure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterator

from orderflow_api.services.orderbook.events import DepthEvent, DepthLevel, Event, TradeEvent
from orderflow_shared.instruments import lookup_instrument


@dataclass
class SyntheticConfig:
    symbol: str = "ES"
    contract: str = ""  # autofilled in __post_init__ if empty
    start_price: float = 5285.00
    duration_seconds: float = 60.0
    depth_event_rate_hz: float = 4.0   # ~250ms cadence
    trade_event_rate_hz: float = 2.0
    levels_per_side: int = 10
    base_top_size: int = 80
    volatility_per_second: float = 0.05  # std-dev of drift in price units / sec
    sweep_probability: float = 0.05      # fraction of trades that are oversized sweeps
    seed: int = 42


@dataclass
class SyntheticSource:
    """Produces a deterministic stream of DepthEvent and TradeEvent.

    Iterating yields events in chronological order with monotonic ts_utc.
    Each iteration completes in O(N) time, no I/O, no clock waits.
    """

    config: SyntheticConfig = field(default_factory=SyntheticConfig)

    def __post_init__(self) -> None:
        if not self.config.contract:
            self.config.contract = f"{self.config.symbol} 06-26"
        spec = lookup_instrument(self.config.symbol)
        self._tick_size = spec.tick_size if spec else 0.25

    def _round_to_tick(self, price: float) -> float:
        return round(price / self._tick_size) * self._tick_size

    def _make_depth(self, mid: float, ts: datetime) -> DepthEvent:
        cfg = self.config
        bids: list[DepthLevel] = []
        asks: list[DepthLevel] = []
        for i in range(cfg.levels_per_side):
            offset = (i + 1) * self._tick_size
            # Decay size with distance from mid (top-of-book is largest)
            size_factor = max(0.2, 1.0 - i * 0.08)
            size = max(1, int(cfg.base_top_size * size_factor))
            orders = max(1, size // 4)
            bids.append(DepthLevel(price=self._round_to_tick(mid - offset), size=size, orders=orders))
            asks.append(DepthLevel(price=self._round_to_tick(mid + offset), size=size, orders=orders))
        return DepthEvent(
            symbol=cfg.symbol, contract=cfg.contract, ts_utc=ts, bids=bids, asks=asks
        )

    def _make_trade(self, mid: float, ts: datetime, rng: random.Random) -> TradeEvent:
        cfg = self.config
        aggressor = rng.choice(["buy", "sell"])
        # Trade prices cluster at the touch
        price = self._round_to_tick(mid + (self._tick_size / 2 if aggressor == "buy" else -self._tick_size / 2))
        is_sweep = rng.random() < cfg.sweep_probability
        size = rng.randint(20, 80) if is_sweep else rng.randint(1, 6)
        return TradeEvent(
            symbol=cfg.symbol, contract=cfg.contract, ts_utc=ts,
            price=price, size=size, aggressor=aggressor,  # type: ignore[arg-type]
        )

    def __iter__(self) -> Iterator[Event]:
        cfg = self.config
        rng = random.Random(cfg.seed)
        start = datetime.now(timezone.utc).replace(microsecond=0)
        depth_step = 1.0 / cfg.depth_event_rate_hz
        trade_step = 1.0 / cfg.trade_event_rate_hz

        events: list[tuple[float, str]] = []
        t = 0.0
        while t < cfg.duration_seconds:
            events.append((t, "depth"))
            t += depth_step
        t = 0.0
        while t < cfg.duration_seconds:
            events.append((t, "trade"))
            t += trade_step
        events.sort(key=lambda x: x[0])

        mid = cfg.start_price
        for offset, kind in events:
            mid_drift = rng.gauss(0, cfg.volatility_per_second * max(0.01, depth_step))
            mid = self._round_to_tick(mid + mid_drift)
            ts = start + timedelta(seconds=offset)
            if kind == "depth":
                yield self._make_depth(mid, ts)
            else:
                yield self._make_trade(mid, ts, rng)
