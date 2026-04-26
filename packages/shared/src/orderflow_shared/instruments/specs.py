"""
File:        packages/shared/src/orderflow_shared/instruments/specs.py
Created:     2026-04-26 18:21 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:21 EST

Change Log:
- 2026-04-26 18:21 EST | 1.0.0 | Phase 1A: ES/NQ/GC/SPY/QQQ instrument specs.

Tick sizes, tick values, session times. Times in US Eastern (CME Globex
trading sessions). All-times in HH:MM 24h Eastern.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    asset_class: str  # "future" | "etf"
    description: str
    tick_size: float
    tick_value_usd: float
    contract_multiplier: float
    rth_open_et: str   # e.g. "09:30"
    rth_close_et: str
    eth_open_et: str   # CME futures only; "" for equities
    eth_close_et: str
    timezone: str = "America/New_York"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


INSTRUMENT_SPECS: dict[str, InstrumentSpec] = {
    "ES": InstrumentSpec(
        symbol="ES",
        asset_class="future",
        description="E-mini S&P 500 futures",
        tick_size=0.25,
        tick_value_usd=12.50,
        contract_multiplier=50.0,
        rth_open_et="09:30",
        rth_close_et="16:00",
        eth_open_et="18:00",
        eth_close_et="17:00",
    ),
    "NQ": InstrumentSpec(
        symbol="NQ",
        asset_class="future",
        description="E-mini Nasdaq-100 futures",
        tick_size=0.25,
        tick_value_usd=5.00,
        contract_multiplier=20.0,
        rth_open_et="09:30",
        rth_close_et="16:00",
        eth_open_et="18:00",
        eth_close_et="17:00",
    ),
    "GC": InstrumentSpec(
        symbol="GC",
        asset_class="future",
        description="Gold futures",
        tick_size=0.10,
        tick_value_usd=10.00,
        contract_multiplier=100.0,
        rth_open_et="08:20",
        rth_close_et="13:30",
        eth_open_et="18:00",
        eth_close_et="17:00",
    ),
    "SPY": InstrumentSpec(
        symbol="SPY",
        asset_class="etf",
        description="SPDR S&P 500 ETF",
        tick_size=0.01,
        tick_value_usd=0.01,
        contract_multiplier=1.0,
        rth_open_et="09:30",
        rth_close_et="16:00",
        eth_open_et="",
        eth_close_et="",
    ),
    "QQQ": InstrumentSpec(
        symbol="QQQ",
        asset_class="etf",
        description="Invesco QQQ Trust (Nasdaq-100 ETF)",
        tick_size=0.01,
        tick_value_usd=0.01,
        contract_multiplier=1.0,
        rth_open_et="09:30",
        rth_close_et="16:00",
        eth_open_et="",
        eth_close_et="",
    ),
}


def lookup_instrument(symbol: str) -> InstrumentSpec | None:
    return INSTRUMENT_SPECS.get(symbol.upper())
