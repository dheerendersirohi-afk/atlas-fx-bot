from __future__ import annotations

import shutil
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from forex_bot.config import BotConfig, RiskConfig, StrategyConfig
from forex_bot.data import load_candles_csv
from forex_bot.engine import TradingEngine
from forex_bot.models import Candle

TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
TEST_TMP_ROOT.mkdir(exist_ok=True)


def make_config() -> BotConfig:
    return BotConfig(
        account_currency="USD",
        starting_balance=10000.0,
        risk=RiskConfig(
            risk_per_trade_pct=0.25,
            max_total_exposure_pct=5.0,
            max_open_positions=3,
            max_spread=0.0003,
            default_stop_loss_pct=0.35,
            default_take_profit_pct=1.0,
            min_confidence=0.1,
        ),
        strategy=StrategyConfig(
            fast_period=3,
            slow_period=5,
            volatility_lookback=3,
            min_volatility_pct=0.01,
        ),
    )


def make_candle(index: int, close: float, high: float | None = None, low: float | None = None) -> Candle:
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return Candle(
        timestamp=stamp,
        pair="EUR/USD",
        open=close,
        high=high if high is not None else close + 0.0020,
        low=low if low is not None else close - 0.0020,
        close=close,
        volume=1000,
        spread=0.0001,
    )


class TradingBotTests(unittest.TestCase):
    def make_temp_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_config_validation_rejects_invalid_strategy_periods(self) -> None:
        with self.assertRaises(ValueError):
            BotConfig(
                account_currency="USD",
                starting_balance=10000.0,
                risk=make_config().risk,
                strategy=StrategyConfig(
                    fast_period=5,
                    slow_period=5,
                    volatility_lookback=3,
                    min_volatility_pct=0.01,
                ),
            ).validate()

    def test_engine_opens_and_closes_trade(self) -> None:
        engine = TradingEngine(make_config())
        candles = [
            make_candle(1, 1.1050),
            make_candle(2, 1.1030),
            make_candle(3, 1.1010),
            make_candle(4, 1.1000),
            make_candle(5, 1.1025),
            make_candle(6, 1.1080),
            make_candle(7, 1.1220, high=1.1240, low=1.1200),
        ]

        for candle in candles:
            engine._evaluate_open_positions(candle)
            engine._evaluate_new_signal(candle)

        summary = engine.summary()
        self.assertGreaterEqual(summary["closed_trades"], 1)
        self.assertGreaterEqual(summary["ending_balance"], summary["starting_balance"])

    def test_strategy_respects_spread_guard(self) -> None:
        config = make_config()
        engine = TradingEngine(config)
        candle = make_candle(1, 1.1)
        candle.spread = 1.0
        allowed, _reason = engine.risk.can_open(
            engine.account,
            candle,
            signal=type(
                "SignalStub",
                (),
                {
                    "confidence": 0.9,
                    "pair": "EUR/USD",
                    "side": "BUY",
                },
            )(),
        )
        self.assertFalse(allowed)

    def test_csv_loader_accepts_blank_optional_fields(self) -> None:
        temp_dir = self.make_temp_path("bot_csv_loader")
        csv_path = temp_dir / "market.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "timestamp,pair,open,high,low,close,volume,spread",
                    "2026-04-17T09:00:00+00:00,EUR/USD,1.0810,1.0822,1.0806,1.0818,,",
                ]
            ),
            encoding="utf-8",
        )

        candles = load_candles_csv(csv_path)

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].volume, 0.0)
        self.assertEqual(candles[0].spread, 0.0)


if __name__ == "__main__":
    unittest.main()
