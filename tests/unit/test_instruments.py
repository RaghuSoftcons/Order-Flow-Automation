"""
File:        tests/unit/test_instruments.py
Created:     2026-04-26 18:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:23 EST
"""

from __future__ import annotations

import pytest

from orderflow_shared.instruments import INSTRUMENT_SPECS, lookup_instrument


@pytest.mark.parametrize("symbol", ["ES", "NQ", "GC", "SPY", "QQQ"])
def test_all_required_symbols_present(symbol: str) -> None:
    spec = lookup_instrument(symbol)
    assert spec is not None
    assert spec.symbol == symbol
    assert spec.tick_size > 0
    assert spec.tick_value_usd > 0
    assert spec.contract_multiplier > 0


def test_lookup_is_case_insensitive() -> None:
    assert lookup_instrument("es") is lookup_instrument("ES")
    assert lookup_instrument("Es") is lookup_instrument("ES")


def test_unknown_symbol_returns_none() -> None:
    assert lookup_instrument("XYZ") is None


def test_es_tick_economics() -> None:
    es = lookup_instrument("ES")
    assert es is not None
    assert es.tick_size == 0.25
    assert es.tick_value_usd == 12.50
    # 1 point on ES = 4 ticks = $50 (4 × 12.50)
    assert es.tick_value_usd / es.tick_size * 1.0 == 50.0


def test_etfs_have_no_eth_session() -> None:
    spy = lookup_instrument("SPY")
    qqq = lookup_instrument("QQQ")
    assert spy is not None and qqq is not None
    assert spy.eth_open_et == ""
    assert qqq.eth_open_et == ""


def test_futures_have_eth_session() -> None:
    for sym in ("ES", "NQ", "GC"):
        spec = lookup_instrument(sym)
        assert spec is not None
        assert spec.eth_open_et != ""


def test_to_dict_round_trip() -> None:
    es = lookup_instrument("ES")
    assert es is not None
    d = es.to_dict()
    assert d["symbol"] == "ES"
    assert d["asset_class"] == "future"
    assert d["tick_size"] == 0.25


def test_template_count() -> None:
    assert len(INSTRUMENT_SPECS) == 5  # ES, NQ, GC, SPY, QQQ
