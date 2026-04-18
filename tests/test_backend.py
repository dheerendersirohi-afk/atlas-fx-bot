from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.config import AIProviderConfig, BackendConfig, load_backend_config
from backend.llm_adapters import QuantModelBrain, SarvamBrain
from backend.mt5_bridge import MT5Bridge
from backend.models import MarketSnapshot, SignalDecision
from backend.risk_engine import RiskEngine
from backend.server import BackendApp
from backend.trade_store import TradeStore

TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_tests"
TEST_TMP_ROOT.mkdir(exist_ok=True)


class StaticBrain:
    def __init__(self, provider: str, action: str = "BUY") -> None:
        self.provider = provider
        self.action = action

    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        return SignalDecision(self.action, 0.7, f"{self.provider} signal", 0.3, 1.1, self.provider)


class BrokenBrain:
    def __init__(self, message: str) -> None:
        self.message = message

    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        raise RuntimeError(self.message)


class BackendTests(unittest.TestCase):
    def make_temp_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_risk_engine_rejects_high_spread(self) -> None:
        engine = RiskEngine()
        signal = SignalDecision("BUY", 0.8, "Test", 0.35, 1.2, "rules")
        snapshot = MarketSnapshot(symbol="EURUSD", bid=1.1, ask=1.1003, spread_points=99)
        assessment = engine.assess(signal, snapshot, account_balance=10000.0, daily_pnl_pct=0.0, open_trades=0)
        self.assertFalse(assessment.approved)

    def test_trade_store_persists_trade(self) -> None:
        temp_dir = self.make_temp_path("trade_store_persists")
        store = TradeStore(temp_dir / "state.json")
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

        saved = json.loads((temp_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["pending_trades"][0]["trade_id"], "abc123")

    def test_trade_store_updates_open_trade_count_on_execution(self) -> None:
        temp_dir = self.make_temp_path("trade_store_open_count")
        store = TradeStore(temp_dir / "state.json")
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

        saved = json.loads((temp_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["open_trades"], 1)

    def test_market_snapshot_ignores_unknown_payload_fields(self) -> None:
        snapshot = MarketSnapshot.from_payload(
            {
                "symbol": "EURUSD",
                "bid": 1.1,
                "ask": 1.1002,
                "spread_points": 12,
                "ema_fast": 1.1004,
                "ema_slow": 1.0998,
                "account_balance": 10000,
                "unexpected_flag": True,
            }
        )

        self.assertEqual(snapshot.symbol, "EURUSD")
        self.assertFalse(hasattr(snapshot, "account_balance"))

    def test_mt5_bridge_status_reports_missing_credentials(self) -> None:
        temp_dir = self.make_temp_path("mt5_bridge_status")
        config_path = temp_dir / "connectors.json"
        config_path.write_text(
            json.dumps(
                {
                    "connectors": {
                        "metatrader5": {
                            "integration_enabled": True,
                            "mode": "demo",
                            "terminal_path": "C:\\missing\\terminal64.exe",
                            "login": 0,
                            "password": "YOUR_MT5_PASSWORD",
                            "server": "YOUR_BROKER_SERVER",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        status = MT5Bridge(config_path).status()
        self.assertFalse(status["credentials_ready"])
        self.assertIn("MT5 broker login, password, or server is still missing.", status["blockers"])

    def test_quant_model_brain_produces_buy_signal_for_bullish_snapshot(self) -> None:
        signal = QuantModelBrain().evaluate(
            MarketSnapshot(
                symbol="EURUSD",
                bid=1.1000,
                ask=1.1002,
                spread_points=12,
                ema_fast=1.1012,
                ema_slow=1.0994,
                rsi=44,
            )
        )

        self.assertEqual(signal.action, "BUY")
        self.assertEqual(signal.provider, "quant")

    def test_load_backend_config_prefers_env_file_values_over_inherited_environment(self) -> None:
        temp_dir = self.make_temp_path("config_override")
        env_path = temp_dir / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "OPENAI_ENABLED=true",
                    "OPENAI_API_KEY=env_file_key",
                    "OPENAI_MODEL=gpt-4.1-mini",
                ]
            ),
            encoding="utf-8",
        )

        self.addCleanup(lambda: os.environ.pop("OPENAI_ENABLED", None))
        self.addCleanup(lambda: os.environ.pop("OPENAI_API_KEY", None))
        self.addCleanup(lambda: os.environ.pop("OPENAI_MODEL", None))
        os.environ["OPENAI_ENABLED"] = "false"
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["OPENAI_MODEL"] = "stale-model"

        config = load_backend_config(env_path)

        self.assertTrue(config.openai.enabled)
        self.assertEqual(config.openai.api_key, "env_file_key")
        self.assertEqual(config.openai.model, "gpt-4.1-mini")

    def test_sarvam_brain_parses_chat_completion_response(self) -> None:
        config = AIProviderConfig(
            enabled=True,
            api_key="sk_test",
            model="sarvam-30b",
            base_url="https://api.sarvam.ai/v1/chat/completions",
            available_models=("sarvam-30b", "sarvam-105b", "sarvam-m"),
        )
        fake_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "action": "BUY",
                                "confidence": 0.77,
                                "reason": "Sarvam bullish.",
                                "stop_loss_pct": 0.3,
                                "take_profit_pct": 1.1,
                            }
                        )
                    }
                }
            ]
        }

        with patch("backend.llm_adapters._post_json", return_value=fake_response):
            signal = SarvamBrain(config).evaluate(
                MarketSnapshot(symbol="EURUSD", bid=1.1, ask=1.1002, spread_points=12, ema_fast=1.101, ema_slow=1.099)
            )

        self.assertEqual(signal.provider, "sarvam")
        self.assertEqual(signal.action, "BUY")

    def test_auto_selector_prioritizes_sarvam_for_rich_snapshot(self) -> None:
        temp_dir = self.make_temp_path("auto_selector_sarvam")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(False, "", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(True, "sk_test", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {"rules": object(), "quant": object(), "gemini": object(), "sarvam": object()}

        selected, reason = app._select_auto_brain(
            MarketSnapshot(
                symbol="EURUSD",
                bid=1.1000,
                ask=1.1002,
                spread_points=12,
                ema_fast=1.1012,
                ema_slow=1.0994,
                rsi=44,
            )
        )

        self.assertEqual(selected, "sarvam")
        self.assertIn("Sarvam", reason)

    def test_auto_selector_uses_gemini_for_rsi_snapshot(self) -> None:
        temp_dir = self.make_temp_path("auto_selector_gemini")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(True, "gem_key", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(False, "", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {"rules": object(), "quant": object(), "gemini": object()}

        selected, reason = app._select_auto_brain(
            MarketSnapshot(
                symbol="EURUSD",
                bid=1.1000,
                ask=1.1002,
                spread_points=20,
                rsi=72,
            )
        )

        self.assertEqual(selected, "gemini")
        self.assertIn("Gemini", reason)

    def test_auto_selector_uses_quant_for_ema_snapshot(self) -> None:
        temp_dir = self.make_temp_path("auto_selector_quant")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(False, "", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(False, "", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {"rules": object(), "quant": object()}

        selected, reason = app._select_auto_brain(
            MarketSnapshot(
                symbol="EURUSD",
                bid=1.1000,
                ask=1.1002,
                spread_points=20,
                ema_fast=1.1012,
                ema_slow=1.0994,
            )
        )

        self.assertEqual(selected, "quant")
        self.assertIn("quant", reason.lower())

    def test_auto_selector_falls_back_to_rules(self) -> None:
        temp_dir = self.make_temp_path("auto_selector_rules")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(False, "", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(False, "", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {"rules": object()}

        selected, reason = app._select_auto_brain(
            MarketSnapshot(
                symbol="EURUSD",
                bid=1.1000,
                ask=1.1002,
                spread_points=45,
            )
        )

        self.assertEqual(selected, "rules")
        self.assertIn("fell back", reason.lower())

    def test_auto_evaluate_falls_back_from_sarvam_to_quant(self) -> None:
        temp_dir = self.make_temp_path("auto_eval_fallback_quant")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(True, "gem_key", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(True, "sk_test", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {
            "rules": StaticBrain("rules", "HOLD"),
            "quant": StaticBrain("quant", "BUY"),
            "gemini": BrokenBrain("gemini offline"),
            "sarvam": BrokenBrain("sarvam offline"),
        }

        evaluated = app.evaluate_signal(
            {
                "symbol": "EURUSD",
                "bid": 1.1000,
                "ask": 1.1002,
                "spread_points": 12,
                "ema_fast": 1.1012,
                "ema_slow": 1.0994,
                "rsi": 44,
            }
        )

        self.assertEqual(evaluated["selected_brain"], "quant")
        self.assertEqual(evaluated["signal"]["provider"], "quant")
        self.assertEqual(len(evaluated["fallback_events"]), 2)

    def test_explicit_provider_falls_back_to_rules_when_requested_brain_fails(self) -> None:
        temp_dir = self.make_temp_path("explicit_eval_fallback_rules")
        app = BackendApp(
            BackendConfig(
                host="127.0.0.1",
                port=8787,
                credentials_path=str(temp_dir / "creds.json"),
                state_file=str(temp_dir / "state.json"),
                default_brain="auto",
                manual_approval=True,
                openai=AIProviderConfig(False, "", "gpt-4.1-mini", "https://api.openai.com/v1/responses"),
                gemini=AIProviderConfig(True, "gem_key", "gemini-2.5-flash", "https://example.com"),
                sarvam=AIProviderConfig(False, "", "sarvam-30b", "https://api.sarvam.ai/v1/chat/completions"),
            )
        )
        app.brains = {
            "rules": StaticBrain("rules", "SELL"),
            "quant": StaticBrain("quant", "BUY"),
            "gemini": BrokenBrain("gemini malformed response"),
        }

        evaluated = app.evaluate_signal(
            {
                "symbol": "EURUSD",
                "bid": 1.1000,
                "ask": 1.1002,
                "spread_points": 20,
                "rsi": 72,
            },
            provider="gemini",
        )

        self.assertEqual(evaluated["selected_brain"], "rules")
        self.assertEqual(evaluated["signal"]["provider"], "rules")
        self.assertEqual(len(evaluated["fallback_events"]), 1)


if __name__ == "__main__":
    unittest.main()
