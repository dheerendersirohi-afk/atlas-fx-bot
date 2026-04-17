from __future__ import annotations

from collections import defaultdict

from .config import StrategyConfig
from .models import Candle, Side, Signal


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = ((value - ema) * multiplier) + ema
    return ema


def _volatility_pct(candles: list[Candle], lookback: int) -> float:
    window = candles[-lookback:]
    if not window:
        return 0.0
    highs = max(item.high for item in window)
    lows = min(item.low for item in window)
    close = window[-1].close
    if close == 0:
        return 0.0
    return ((highs - lows) / close) * 100


class EmaCrossStrategy:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.history: dict[str, list[Candle]] = defaultdict(list)

    def on_candle(self, candle: Candle) -> Signal | None:
        pair_history = self.history[candle.pair]
        pair_history.append(candle)
        closes = [item.close for item in pair_history]

        fast = _ema(closes, self.config.fast_period)
        slow = _ema(closes, self.config.slow_period)
        if fast is None or slow is None:
            return None

        volatility = _volatility_pct(pair_history, self.config.volatility_lookback)
        if volatility < self.config.min_volatility_pct:
            return None

        previous_closes = closes[:-1]
        prev_fast = _ema(previous_closes, self.config.fast_period)
        prev_slow = _ema(previous_closes, self.config.slow_period)
        if prev_fast is None or prev_slow is None:
            return None

        crossed_up = prev_fast <= prev_slow and fast > slow
        crossed_down = prev_fast >= prev_slow and fast < slow

        spread_penalty = min(candle.spread / max(candle.close, 1e-9), 0.01) * 50
        confidence = max(0.0, min(0.95, 0.6 + (volatility / 100) - spread_penalty))

        if crossed_up:
            return Signal(
                pair=candle.pair,
                side=Side.BUY,
                confidence=confidence,
                reason=f"EMA bullish crossover with volatility {volatility:.3f}%",
                stop_loss_pct=0.35,
                take_profit_pct=1.2,
            )

        if crossed_down:
            return Signal(
                pair=candle.pair,
                side=Side.SELL,
                confidence=confidence,
                reason=f"EMA bearish crossover with volatility {volatility:.3f}%",
                stop_loss_pct=0.35,
                take_profit_pct=1.2,
            )

        return None
