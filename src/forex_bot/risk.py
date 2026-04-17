from __future__ import annotations

from .config import RiskConfig
from .models import AccountState, Candle, Order, Side, Signal


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def can_open(self, account: AccountState, candle: Candle, signal: Signal) -> tuple[bool, str]:
        if account.balance <= 0:
            return False, "Insufficient balance"
        if signal.confidence < self.config.min_confidence:
            return False, "Signal confidence below threshold"
        if candle.spread > self.config.max_spread:
            return False, "Spread too wide"
        if len(account.open_positions) >= self.config.max_open_positions:
            return False, "Max open positions reached"
        if any(position.pair == signal.pair and position.side == signal.side for position in account.open_positions):
            return False, "Similar position already open"
        return True, "approved"

    def build_order(self, account: AccountState, candle: Candle, signal: Signal) -> Order:
        stop_loss_pct = max(signal.stop_loss_pct, self.config.default_stop_loss_pct)
        take_profit_pct = max(signal.take_profit_pct, self.config.default_take_profit_pct)

        risk_capital = account.balance * (self.config.risk_per_trade_pct / 100)
        stop_distance = candle.close * (stop_loss_pct / 100)
        units = 0.0 if stop_distance <= 0 else risk_capital / stop_distance

        max_notional = account.balance * (self.config.max_total_exposure_pct / 100)
        units = min(units, max_notional / max(candle.close, 1e-9))

        return Order(
            pair=signal.pair,
            side=signal.side,
            units=round(units, 4),
            requested_price=candle.close,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            reason=signal.reason,
        )

    def should_close_position(self, candle: Candle, position_side: Side, stop_loss_price: float, take_profit_price: float) -> tuple[bool, str]:
        if position_side == Side.BUY:
            if candle.low <= stop_loss_price:
                return True, "stop_loss"
            if candle.high >= take_profit_price:
                return True, "take_profit"
        else:
            if candle.high >= stop_loss_price:
                return True, "stop_loss"
            if candle.low <= take_profit_price:
                return True, "take_profit"
        return False, ""
