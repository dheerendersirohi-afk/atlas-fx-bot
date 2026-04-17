from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.models import MarketSnapshot, SignalDecision
from backend.risk_engine import RiskEngine
from backend.trade_store import TradeStore


class BackendTests(unittest.TestCase):
    def test_risk_engine_rejects_high_spread(self) -> None:
        engine = RiskEngine()
        signal = SignalDecision("BUY", 0.8, "Test", 0.35, 1.2, "rules")
        snapshot = MarketSnapshot(symbol="EURUSD", bid=1.1, ask=1.1003, spread_points=99)
        assessment = engine.assess(signal, snapshot, account_balance=10000.0, daily_pnl_pct=0.0, open_trades=0)
        self.assertFalse(assessment.approved)

    def test_trade_store_persists_trade(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = TradeStore(Path(temp_dir) / "state.json")
            payload = {
                "trade_id": "abc123",
                "symbol": "EURUSD",
                "side": "BUY",
                "confidence": 0.7,
                "provider": "rules",
                "status": "pending",
                "reason": "Test trade",
                "approval_required": True,
                "volume_lots": 0.01,
                "stop_loss_pct": 0.35,
                "take_profit_pct": 1.2,
                "entry_bid": 1.1,
                "entry_ask": 1.1002,
                "created_at": "2026-04-17T00:00:00+00:00",
                "updated_at": "2026-04-17T00:00:00+00:00",
                "execution_result": {},
            }
            store.add_trade(type("TradeStub", (), {"to_dict": lambda self: payload, "status": "pending"})())

            saved = json.loads((Path(temp_dir) / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(saved["pending_trades"][0]["trade_id"], "abc123")

    def test_trade_store_updates_open_trade_count_on_execution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = TradeStore(Path(temp_dir) / "state.json")
            payload = {
                "trade_id": "abc123",
                "symbol": "EURUSD",
                "side": "BUY",
                "confidence": 0.7,
                "provider": "rules",
                "status": "pending",
                "reason": "Test trade",
                "approval_required": True,
                "volume_lots": 0.01,
                "stop_loss_pct": 0.35,
                "take_profit_pct": 1.2,
                "entry_bid": 1.1,
                "entry_ask": 1.1002,
                "created_at": "2026-04-17T00:00:00+00:00",
                "updated_at": "2026-04-17T00:00:00+00:00",
                "execution_result": {},
            }
            store.add_trade(type("TradeStub", (), {"to_dict": lambda self: payload, "status": "pending"})())
            store.update_trade("abc123", status="executed", execution_result={"status": "executed"})

            saved = json.loads((Path(temp_dir) / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(saved["open_trades"], 1)


if __name__ == "__main__":
    unittest.main()
