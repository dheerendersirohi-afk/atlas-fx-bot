from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import MarketSnapshot, SignalDecision


@dataclass(slots=True)
class RiskLimits:
    max_risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 1.0
    max_spread_points: float = 30.0
    max_open_trades: int = 3
    min_confidence: float = 0.55
    stop_loss_pct: float = 0.35
    take_profit_pct: float = 1.2
    min_lot: float = 0.01
    max_lot: float = 2.0
    contract_size: float = 100000.0


@dataclass(slots=True)
class RiskAssessment:
    approved: bool
    volume_lots: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def assess(
        self,
        signal: SignalDecision,
        snapshot: MarketSnapshot,
        *,
        account_balance: float,
        daily_pnl_pct: float,
        open_trades: int,
    ) -> RiskAssessment:
        reasons: list[str] = []
        if signal.action not in {"BUY", "SELL"}:
            reasons.append("Signal action must be BUY or SELL.")
        if signal.confidence < self.limits.min_confidence:
            reasons.append("Signal confidence below threshold.")
        if snapshot.spread_points > self.limits.max_spread_points:
            reasons.append("Spread exceeds configured limit.")
        if daily_pnl_pct <= -abs(self.limits.max_daily_loss_pct):
            reasons.append("Daily loss limit already reached.")
        if open_trades >= self.limits.max_open_trades:
            reasons.append("Maximum open trades already reached.")
        if account_balance <= 0:
            reasons.append("Account balance must be positive.")

        stop_loss_pct = max(signal.stop_loss_pct, self.limits.stop_loss_pct)
        risk_amount = account_balance * (self.limits.max_risk_per_trade_pct / 100)
        price = max(snapshot.mid_price, 1e-9)
        raw_lots = risk_amount / (self.limits.contract_size * price * (stop_loss_pct / 100))
        volume_lots = max(self.limits.min_lot, min(self.limits.max_lot, round(raw_lots, 2)))

        if raw_lots <= 0:
            reasons.append("Computed lot size is not tradable.")

        return RiskAssessment(
            approved=not reasons,
            volume_lots=volume_lots,
            reasons=reasons or ["approved"],
        )
