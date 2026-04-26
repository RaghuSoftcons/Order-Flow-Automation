"""
File:        apps/api/src/orderflow_api/services/orderbook/events.py
Created:     2026-04-26 18:18 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 18:18 EST

Change Log:
- 2026-04-26 18:18 EST | 1.0.0 | Phase 1A: event schemas for NT bridge → engine.

Pydantic models for events that flow from the NT bridge (or replay harness)
into the order book engine. Same schema is used for live and replay paths.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, RootModel


class DepthLevel(BaseModel):
    price: float
    size: int = Field(ge=0)
    orders: int = Field(default=0, ge=0)


class DepthEvent(BaseModel):
    """Full top-N depth snapshot for one side or both sides of one symbol."""

    type: Literal["depth"] = "depth"
    symbol: str = Field(min_length=1, max_length=10, description="Normalized symbol (e.g. 'ES')")
    contract: str = Field(min_length=1, max_length=20, description="Full contract identifier (e.g. 'ES 06-26')")
    ts_utc: datetime
    bids: list[DepthLevel] = Field(default_factory=list)
    asks: list[DepthLevel] = Field(default_factory=list)


class TradeEvent(BaseModel):
    type: Literal["trade"] = "trade"
    symbol: str = Field(min_length=1, max_length=10)
    contract: str = Field(min_length=1, max_length=20)
    ts_utc: datetime
    price: float
    size: int = Field(gt=0)
    aggressor: Literal["buy", "sell"]


Event = Annotated[Union[DepthEvent, TradeEvent], Field(discriminator="type")]


class EventEnvelope(RootModel[Event]):
    """For ingest endpoints that need to validate one inbound event."""
    pass
