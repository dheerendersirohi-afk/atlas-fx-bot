from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import BackendConfig, load_backend_config
from .llm_adapters import GeminiBrain, OpenAIBrain, RuleBasedBrain
from .models import MarketSnapshot, PendingTrade
from .mt5_bridge import MT5Bridge
from .risk_engine import RiskEngine
from .trade_store import TradeStore


class BackendApp:
    def __init__(self, config: BackendConfig) -> None:
        self.config = config
        self.store = TradeStore(config.state_file)
        self.risk = RiskEngine()
        self.mt5 = MT5Bridge(config.credentials_path)
        self.brains = {"rules": RuleBasedBrain()}
        if config.openai.enabled and config.openai.api_key:
            self.brains["openai"] = OpenAIBrain(config.openai)
        if config.gemini.enabled and config.gemini.api_key:
            self.brains["gemini"] = GeminiBrain(config.gemini)

    def evaluate_signal(self, snapshot_payload: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
        brain_name = provider or self.config.default_brain
        brain = self.brains.get(brain_name, self.brains["rules"])
        snapshot = MarketSnapshot(**snapshot_payload)
        signal = brain.evaluate(snapshot)
        state = self.store.get_status()
        assessment = self.risk.assess(
            signal,
            snapshot,
            account_balance=float(state.get("account_balance", 10000.0)),
            daily_pnl_pct=float(state.get("daily_pnl_pct", 0.0)),
            open_trades=int(state.get("open_trades", 0)),
        )
        return {
            "snapshot": snapshot.to_dict(),
            "signal": signal.to_dict(),
            "risk": assessment.to_dict(),
        }

    def submit_trade(self, snapshot_payload: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
        evaluated = self.evaluate_signal(snapshot_payload, provider)
        signal = evaluated["signal"]
        risk = evaluated["risk"]
        snapshot = MarketSnapshot(**evaluated["snapshot"])

        if not risk["approved"]:
            return {"status": "rejected", "evaluated": evaluated}

        trade = PendingTrade.from_signal(
            signal=self._signal_from_dict(signal),
            snapshot=snapshot,
            volume_lots=float(risk["volume_lots"]),
            approval_required=self.config.manual_approval,
            status="pending" if self.config.manual_approval else "approved",
        )

        if self.config.manual_approval:
            self.store.add_trade(trade)
            return {"status": "pending_approval", "trade": trade.to_dict(), "evaluated": evaluated}

        execution_result = self.mt5.execute_trade(trade.to_dict())
        trade.status = execution_result["status"]
        trade.execution_result = execution_result
        self.store.add_trade(trade)
        return {"status": trade.status, "trade": trade.to_dict(), "evaluated": evaluated}

    def approve_trade(self, trade_id: str) -> dict[str, Any]:
        trades = self.store.list_trades()
        target = next((item for item in trades if item["trade_id"] == trade_id), None)
        if target is None:
            return {"status": "not_found"}
        execution = self.mt5.execute_trade(target)
        updated = self.store.update_trade(trade_id, status=execution["status"], execution_result=execution)
        return {"status": execution["status"], "trade": updated}

    def reject_trade(self, trade_id: str) -> dict[str, Any]:
        updated = self.store.update_trade(trade_id, status="rejected", execution_result={"status": "rejected"})
        return {"status": "rejected" if updated else "not_found", "trade": updated}

    def status(self) -> dict[str, Any]:
        store_status = self.store.get_status()
        return {
            "host": self.config.host,
            "port": self.config.port,
            "manual_approval": self.config.manual_approval,
            "default_brain": self.config.default_brain,
            "brains": sorted(self.brains.keys()),
            "mt5": self.mt5.status(),
            "store": store_status,
        }

    @staticmethod
    def _signal_from_dict(signal: dict[str, Any]):
        from .models import SignalDecision

        return SignalDecision(
            action=signal["action"],
            confidence=float(signal["confidence"]),
            reason=str(signal["reason"]),
            stop_loss_pct=float(signal["stop_loss_pct"]),
            take_profit_pct=float(signal["take_profit_pct"]),
            provider=str(signal["provider"]),
            raw_response=signal.get("raw_response", {}),
        )


class BackendRequestHandler(BaseHTTPRequestHandler):
    app: BackendApp

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/api/status":
            self._send_json(self.app.status())
            return
        if parsed.path == "/api/trades":
            self._send_json({"trades": self.app.store.list_trades()})
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._read_json_body()
        try:
            if parsed.path == "/api/signal/evaluate":
                self._send_json(self.app.evaluate_signal(body["snapshot"], body.get("provider")))
                return
            if parsed.path == "/api/trades/submit":
                self._send_json(self.app.submit_trade(body["snapshot"], body.get("provider")))
                return
            if parsed.path.startswith("/api/trades/") and parsed.path.endswith("/approve"):
                trade_id = parsed.path.split("/")[-2]
                self._send_json(self.app.approve_trade(trade_id))
                return
            if parsed.path.startswith("/api/trades/") and parsed.path.endswith("/reject"):
                trade_id = parsed.path.split("/")[-2]
                self._send_json(self.app.reject_trade(trade_id))
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def run_server(config: BackendConfig | None = None) -> None:
    app_config = config or load_backend_config()
    app = BackendApp(app_config)

    class Handler(BackendRequestHandler):
        pass

    Handler.app = app
    server = ThreadingHTTPServer((app_config.host, app_config.port), Handler)
    print(f"Atlas backend listening on http://{app_config.host}:{app_config.port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
