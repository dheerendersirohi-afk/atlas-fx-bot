from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(slots=True)
class Candle:
    timestamp: datetime
    pair: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float = 0.0


@dataclass(slots=True)
class Signal:
    pair: str
    side: Side
    confidence: float
    reason: str
    stop_loss_pct: float
    take_profit_pct: float


@dataclass(slots=True)
class Order:
    pair: str
    side: Side
    units: float
    requested_price: float
    stop_loss_pct: float
    take_profit_pct: float
    reason: str


@dataclass(slots=True)
class Fill:
    pair: str
    side: Side
    units: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    timestamp: datetime
    reason: str


@dataclass(slots=True)
class Position:
    pair: str
    side: Side
    units: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    opened_at: datetime
    reason: str
    closed_at: datetime | None = None
    exit_price: float | None = None
    realized_pnl: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.closed_at is None


@dataclass(slots=True)
class AccountState:
    balance: float
    equity: float
    currency: str
    open_positions: list[Position] = field(default_factory=list)
    closed_positions: list[Position] = field(default_factory=list)
