"""
File:        packages/shared/src/orderflow_shared/replay/databento_source.py
Created:     2026-04-26 18:52 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:52 EST

Change Log:
- 2026-04-26 18:52 EST | 1.0.0 | Phase 1C: optional Databento DBN adapter.

Adapter that converts Databento MBP-10 records into our DepthEvent /
TradeEvent schema. The `databento` SDK is an optional install — this module
imports it lazily so the rest of the project works fine without it.

Install when you want to replay real CME tape:
    pip install databento
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from orderflow_api.services.orderbook.events import DepthEvent, DepthLevel, Event, TradeEvent


@dataclass
class DatabentoMBP10Source:
    """Reads a Databento DBN file containing MBP-10 records.

    Supported schema: `mbp-10` (10 levels each side, price-aggregated).
    For MBO data the field layout differs; this adapter would need extension.
    """

    file_path: str
    symbol_map: dict[str, str] | None = None  # raw symbol → normalized (e.g. "ESM6" → "ES")

    def __iter__(self) -> Iterator[Event]:
        try:
            import databento as db  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Databento SDK not installed. Install with: pip install databento"
            ) from exc

        store = db.DBNStore.from_file(self.file_path)
        for record in store:
            event = self._convert(record)
            if event is not None:
                yield event

    def _normalize_symbol(self, raw: str) -> str:
        if self.symbol_map and raw in self.symbol_map:
            return self.symbol_map[raw]
        # Default: strip month/year suffix (e.g. "ESM6" → "ES")
        for length in (4, 3, 2):
            if len(raw) > length and raw[:length].isalpha():
                return raw[:length]
        return raw

    def _convert(self, record) -> Event | None:  # noqa: ANN001
        # Databento records have a `record_type` we discriminate on.
        rec_type = getattr(record, "record_type", None) or getattr(record, "rtype", None)
        symbol = getattr(record, "symbol", None) or getattr(record, "raw_symbol", "UNKNOWN")
        norm_symbol = self._normalize_symbol(symbol)
        ts_ns = getattr(record, "ts_event", None) or getattr(record, "ts_recv", 0)
        ts = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc) if ts_ns else datetime.now(timezone.utc)

        # Trade record
        if str(rec_type).lower() in ("trade", "1") or hasattr(record, "price") and hasattr(record, "size") and not hasattr(record, "bid_px_00"):
            aggressor = "buy" if getattr(record, "side", "B") in ("B", "buy") else "sell"
            return TradeEvent(
                symbol=norm_symbol, contract=symbol, ts_utc=ts,
                price=float(getattr(record, "price", 0)) / 1e9,  # Databento price is fixed-point
                size=int(getattr(record, "size", 0)),
                aggressor=aggressor,  # type: ignore[arg-type]
            )

        # MBP-10 record (10 bid + 10 ask levels)
        if hasattr(record, "bid_px_00"):
            bids: list[DepthLevel] = []
            asks: list[DepthLevel] = []
            for i in range(10):
                bid_px = getattr(record, f"bid_px_{i:02d}", 0)
                bid_sz = getattr(record, f"bid_sz_{i:02d}", 0)
                bid_ct = getattr(record, f"bid_ct_{i:02d}", 0)
                ask_px = getattr(record, f"ask_px_{i:02d}", 0)
                ask_sz = getattr(record, f"ask_sz_{i:02d}", 0)
                ask_ct = getattr(record, f"ask_ct_{i:02d}", 0)
                if bid_sz > 0:
                    bids.append(DepthLevel(price=float(bid_px) / 1e9, size=int(bid_sz), orders=int(bid_ct)))
                if ask_sz > 0:
                    asks.append(DepthLevel(price=float(ask_px) / 1e9, size=int(ask_sz), orders=int(ask_ct)))
            return DepthEvent(
                symbol=norm_symbol, contract=symbol, ts_utc=ts, bids=bids, asks=asks
            )

        return None
