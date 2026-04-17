from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .models import PendingTrade


class TradeStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self.path.exists():
            self._write(
                {
                    "pending_trades": [],
                    "account_balance": 10000.0,
                    "daily_pnl_pct": 0.0,
                    "open_trades": 0,
                }
            )

    def _read(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_status(self) -> dict[str, Any]:
        return self._read()

    def list_trades(self) -> list[dict[str, Any]]:
        return self._read()["pending_trades"]

    def add_trade(self, trade: PendingTrade) -> PendingTrade:
        state = self._read()
        state["pending_trades"].insert(0, trade.to_dict())
        if trade.status in {"approved", "executed"}:
            state["open_trades"] = int(state.get("open_trades", 0)) + 1
        self._write(state)
        return trade

    def update_trade(self, trade_id: str, *, status: str, execution_result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = self._read()
        for trade in state["pending_trades"]:
            if trade["trade_id"] != trade_id:
                continue
            previous_status = trade.get("status")
            trade["status"] = status
            trade["updated_at"] = datetime.now(timezone.utc).isoformat()
            trade["execution_result"] = execution_result or {}
            if previous_status == "pending" and status in {"approved", "executed"}:
                state["open_trades"] = int(state.get("open_trades", 0)) + 1
            self._write(state)
            return trade
        return None
