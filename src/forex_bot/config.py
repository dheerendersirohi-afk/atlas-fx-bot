from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RiskConfig:
    risk_per_trade_pct: float
    max_total_exposure_pct: float
    max_open_positions: int
    max_spread: float
    default_stop_loss_pct: float
    default_take_profit_pct: float
    min_confidence: float

    def validate(self) -> None:
        if self.risk_per_trade_pct <= 0:
            raise ValueError("risk_per_trade_pct must be greater than 0.")
        if self.max_total_exposure_pct <= 0:
            raise ValueError("max_total_exposure_pct must be greater than 0.")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be greater than 0.")
        if self.max_spread < 0:
            raise ValueError("max_spread cannot be negative.")
        if self.default_stop_loss_pct <= 0:
            raise ValueError("default_stop_loss_pct must be greater than 0.")
        if self.default_take_profit_pct <= 0:
            raise ValueError("default_take_profit_pct must be greater than 0.")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1.")


@dataclass(slots=True)
class StrategyConfig:
    fast_period: int
    slow_period: int
    volatility_lookback: int
    min_volatility_pct: float

    def validate(self) -> None:
        if self.fast_period <= 0:
            raise ValueError("fast_period must be greater than 0.")
        if self.slow_period <= 0:
            raise ValueError("slow_period must be greater than 0.")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be smaller than slow_period.")
        if self.volatility_lookback <= 0:
            raise ValueError("volatility_lookback must be greater than 0.")
        if self.min_volatility_pct < 0:
            raise ValueError("min_volatility_pct cannot be negative.")


@dataclass(slots=True)
class BotConfig:
    account_currency: str
    starting_balance: float
    risk: RiskConfig
    strategy: StrategyConfig

    def validate(self) -> None:
        if not self.account_currency:
            raise ValueError("account_currency is required.")
        if self.starting_balance <= 0:
            raise ValueError("starting_balance must be greater than 0.")
        self.risk.validate()
        self.strategy.validate()


def load_config(path: str | Path) -> BotConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    config = BotConfig(
        account_currency=raw["account_currency"],
        starting_balance=float(raw["starting_balance"]),
        risk=RiskConfig(**raw["risk"]),
        strategy=StrategyConfig(**raw["strategy"]),
    )
    config.validate()
    return config
