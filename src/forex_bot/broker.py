from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .models import AccountState, Fill, Order, Position, Side


class Broker(ABC):
    @abstractmethod
    def place_order(self, account: AccountState, order: Order, timestamp: datetime) -> Fill:
        raise NotImplementedError

    @abstractmethod
    def close_position(self, account: AccountState, position: Position, exit_price: float, timestamp: datetime, reason: str) -> Position:
        raise NotImplementedError


class PaperBroker(Broker):
    def place_order(self, account: AccountState, order: Order, timestamp: datetime) -> Fill:
        if order.units <= 0:
            raise ValueError("Order units must be greater than zero")

        if order.side == Side.BUY:
            stop_loss_price = order.requested_price * (1 - (order.stop_loss_pct / 100))
            take_profit_price = order.requested_price * (1 + (order.take_profit_pct / 100))
        else:
            stop_loss_price = order.requested_price * (1 + (order.stop_loss_pct / 100))
            take_profit_price = order.requested_price * (1 - (order.take_profit_pct / 100))

        return Fill(
            pair=order.pair,
            side=order.side,
            units=order.units,
            entry_price=order.requested_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            timestamp=timestamp,
            reason=order.reason,
        )

    def close_position(self, account: AccountState, position: Position, exit_price: float, timestamp: datetime, reason: str) -> Position:
        position.closed_at = timestamp
        position.exit_price = exit_price
        direction = 1 if position.side == Side.BUY else -1
        position.realized_pnl = (exit_price - position.entry_price) * position.units * direction
        account.balance += position.realized_pnl
        account.equity = account.balance
        return position
