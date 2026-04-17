from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import Candle


def _float_or_default(raw: str | None, default: float = 0.0) -> float:
    if raw is None:
        return default
    text = raw.strip()
    if text == "":
        return default
    return float(text)


def load_candles_csv(path: str | Path) -> list[Candle]:
    candles: list[Candle] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candles.append(
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    pair=row["pair"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=_float_or_default(row.get("volume"), 0.0),
                    spread=_float_or_default(row.get("spread"), 0.0),
                )
            )
    candles.sort(key=lambda item: (item.timestamp, item.pair))
    return candles
