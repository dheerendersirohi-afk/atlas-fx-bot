from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None


class MT5Bridge:
    def __init__(self, credentials_path: str | Path) -> None:
        self.credentials_path = Path(credentials_path)

    def _read_connector(self) -> dict[str, Any]:
        raw = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        return raw["connectors"]["metatrader5"]

    @staticmethod
    def _has_real_credentials(connector: dict[str, Any]) -> bool:
        login = int(connector.get("login", 0) or 0)
        password = str(connector.get("password", "")).strip()
        server = str(connector.get("server", "")).strip()
        placeholder_tokens = {
            "",
            "YOUR_MT5_PASSWORD",
            "YOUR_BROKER_SERVER",
            "YOUR_MT4_PASSWORD",
            "YOUR_MT4_BROKER_SERVER",
        }
        return login > 0 and password not in placeholder_tokens and server not in placeholder_tokens

    def status(self) -> dict[str, Any]:
        connector = self._read_connector()
        terminal_path = str(connector.get("terminal_path", ""))
        blockers: list[str] = []
        if not Path(terminal_path).exists():
            blockers.append("MT5 terminal path does not exist.")
        if mt5 is None:
            blockers.append("MetaTrader5 Python package is not installed.")
        if not self._has_real_credentials(connector):
            blockers.append("MT5 broker login, password, or server is still missing.")
        return {
            "integration_enabled": bool(connector.get("integration_enabled", False)),
            "mode": connector.get("mode", "demo"),
            "terminal_path": terminal_path,
            "terminal_exists": Path(terminal_path).exists(),
            "package_available": mt5 is not None,
            "credentials_ready": self._has_real_credentials(connector),
            "server": connector.get("server", ""),
            "login": connector.get("login", 0),
            "blockers": blockers,
        }

    def execute_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        status = self.status()
        if not status["integration_enabled"]:
            return {"status": "blocked", "reason": "MT5 integration disabled in config."}
        if not status["terminal_exists"]:
            return {"status": "blocked", "reason": "MT5 terminal path does not exist."}
        if mt5 is None:
            return {
                "status": "ready_but_unavailable",
                "reason": "MetaTrader5 Python package is not installed in this environment.",
            }
        if not status["credentials_ready"]:
            return {
                "status": "blocked",
                "reason": "MT5 broker login, password, or server is still missing in the connector config.",
            }

        connector = self._read_connector()
        initialized = mt5.initialize(
            path=connector["terminal_path"],
            login=int(connector["login"]),
            password=str(connector["password"]),
            server=str(connector["server"]),
        )
        if not initialized:
            return {"status": "blocked", "reason": f"MT5 initialize failed: {mt5.last_error()}"}

        try:
            symbol = trade["symbol"]
            if not mt5.symbol_select(symbol, True):
                return {"status": "blocked", "reason": f"Could not select symbol {symbol}."}

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {"status": "blocked", "reason": "Could not read symbol tick."}

            is_buy = trade["side"] == "BUY"
            price = tick.ask if is_buy else tick.bid
            sl = price * (1 - (trade["stop_loss_pct"] / 100)) if is_buy else price * (1 + (trade["stop_loss_pct"] / 100))
            tp = price * (1 + (trade["take_profit_pct"] / 100)) if is_buy else price * (1 - (trade["take_profit_pct"] / 100))

            request_payload = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(trade["volume_lots"]),
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 424242,
                "comment": f"Atlas {trade['provider']} signal",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            result = mt5.order_send(request_payload)
            if result is None:
                return {"status": "blocked", "reason": f"order_send failed: {mt5.last_error()}"}
            return {"status": "executed", "result": str(result)}
        finally:
            mt5.shutdown()
