from __future__ import annotations

from dataclasses import asdict

from .broker import Broker, PaperBroker
from .config import BotConfig
from .data import load_candles_csv
from .models import AccountState, Candle, Position
from .risk import RiskManager
from .strategy import EmaCrossStrategy


class TradingEngine:
    def __init__(self, config: BotConfig, broker: Broker | None = None) -> None:
        self.config = config
        self.account = AccountState(
            balance=config.starting_balance,
            equity=config.starting_balance,
            currency=config.account_currency,
        )
        self.strategy = EmaCrossStrategy(config.strategy)
        self.risk = RiskManager(config.risk)
        self.broker = broker or PaperBroker()

    def run_csv(self, path: str) -> dict[str, float | int]:
        candles = load_candles_csv(path)
        for candle in candles:
            self._evaluate_open_positions(candle)
            self._evaluate_new_signal(candle)
        return self.summary()

    def _evaluate_open_positions(self, candle: Candle) -> None:
        open_positions = list(self.account.open_positions)
        for position in open_positions:
            if position.pair != candle.pair:
                continue
            should_close, reason = self.risk.should_close_position(
                candle,
                position.side,
                position.stop_loss_price,
                position.take_profit_price,
            )
            if not should_close:
                continue
            exit_price = position.stop_loss_price if reason == "stop_loss" else position.take_profit_price
            closed = self.broker.close_position(
                self.account,
                position,
                exit_price=exit_price,
                timestamp=candle.timestamp,
                reason=reason,
            )
            self.account.open_positions.remove(position)
            self.account.closed_positions.append(closed)

    def _evaluate_new_signal(self, candle: Candle) -> None:
        signal = self.strategy.on_candle(candle)
        if signal is None:
            return

        approved, _reason = self.risk.can_open(self.account, candle, signal)
        if not approved:
            return

        order = self.risk.build_order(self.account, candle, signal)
        if order.units <= 0:
            return
        fill = self.broker.place_order(self.account, order, candle.timestamp)
        self.account.open_positions.append(
            Position(
                pair=fill.pair,
                side=fill.side,
                units=fill.units,
                entry_price=fill.entry_price,
                stop_loss_price=fill.stop_loss_price,
                take_profit_price=fill.take_profit_price,
                opened_at=fill.timestamp,
                reason=fill.reason,
            )
        )

    def summary(self) -> dict[str, float | int]:
        wins = sum(1 for trade in self.account.closed_positions if trade.realized_pnl > 0)
        losses = sum(1 for trade in self.account.closed_positions if trade.realized_pnl < 0)
        return {
            "starting_balance": round(self.config.starting_balance, 2),
            "ending_balance": round(self.account.balance, 2),
            "closed_trades": len(self.account.closed_positions),
            "open_trades": len(self.account.open_positions),
            "wins": wins,
            "losses": losses,
        }

    def export_state(self) -> dict[str, object]:
        return {
            "account": asdict(self.account),
        }
