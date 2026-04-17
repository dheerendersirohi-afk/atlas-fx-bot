from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    bid: float
    ask: float
    spread_points: float
    ema_fast: float | None = None
    ema_slow: float | None = None
    rsi: float | None = None
    source: str = "manual"
    timestamp: str = field(default_factory=utc_now_iso)

    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SignalDecision:
    action: str
    confidence: float
    reason: str
    stop_loss_pct: float
    take_profit_pct: float
    provider: str
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PendingTrade:
    trade_id: str
    symbol: str
    side: str
    confidence: float
    provider: str
    status: str
    reason: str
    approval_required: bool
    volume_lots: float
    stop_loss_pct: float
    take_profit_pct: float
    entry_bid: float
    entry_ask: float
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    execution_result: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_signal(
        cls,
        signal: SignalDecision,
        snapshot: MarketSnapshot,
        volume_lots: float,
        approval_required: bool,
        status: str = "pending",
    ) -> "PendingTrade":
        return cls(
            trade_id=uuid4().hex,
            symbol=snapshot.symbol,
            side=signal.action,
            confidence=signal.confidence,
            provider=signal.provider,
            status=status,
            reason=signal.reason,
            approval_required=approval_required,
            volume_lots=volume_lots,
            stop_loss_pct=signal.stop_loss_pct,
            take_profit_pct=signal.take_profit_pct,
            entry_bid=snapshot.bid,
            entry_ask=snapshot.ask,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
