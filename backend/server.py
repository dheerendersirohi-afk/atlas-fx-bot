from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import BackendConfig, load_backend_config
from .llm_adapters import GeminiBrain, OpenAIBrain, QuantModelBrain, RuleBasedBrain, SarvamBrain
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
        self.brains = {
            "rules": RuleBasedBrain(),
            "quant": QuantModelBrain(),
        }
        if config.sarvam.enabled and config.sarvam.api_key:
            self.brains["sarvam"] = SarvamBrain(config.sarvam)
        if config.openai.enabled and config.openai.api_key:
            self.brains["openai"] = OpenAIBrain(config.openai)
        if config.gemini.enabled and config.gemini.api_key:
            self.brains["gemini"] = GeminiBrain(config.gemini)

    def _select_auto_brain(self, snapshot: MarketSnapshot) -> tuple[str, str]:
        has_ema = snapshot.ema_fast is not None and snapshot.ema_slow is not None
        has_rsi = snapshot.rsi is not None

        if "sarvam" in self.brains and has_ema and has_rsi and snapshot.spread_points <= 25:
            return "sarvam", "Auto selector chose Sarvam because EMA and RSI features are both available with acceptable spread."

        if "gemini" in self.brains and has_rsi and snapshot.spread_points <= 35:
            return "gemini", "Auto selector chose Gemini because RSI context is available and spread is within the LLM threshold."

        if "quant" in self.brains and has_ema:
            return "quant", "Auto selector chose the local quant model because EMA features are available."

        return "rules", "Auto selector fell back to deterministic rules because richer model inputs were not available."

    def _auto_brain_candidates(self, snapshot: MarketSnapshot) -> list[tuple[str, str]]:
        selected_name, selection_reason = self._select_auto_brain(snapshot)
        candidates: list[tuple[str, str]] = [(selected_name, selection_reason)]

        if selected_name == "sarvam":
            if "gemini" in self.brains and snapshot.rsi is not None and snapshot.spread_points <= 35:
                candidates.append(("gemini", "Sarvam was unavailable, so Gemini is the next LLM fallback for RSI-aware snapshots."))
            if "quant" in self.brains and snapshot.ema_fast is not None and snapshot.ema_slow is not None:
                candidates.append(("quant", "LLM providers were unavailable, so the local quant model is taking over with EMA features."))
        elif selected_name == "gemini":
            if "quant" in self.brains and snapshot.ema_fast is not None and snapshot.ema_slow is not None:
                candidates.append(("quant", "Gemini was unavailable, so the local quant model is taking over with EMA features."))

        if "rules" in self.brains and all(name != "rules" for name, _ in candidates):
            candidates.append(("rules", "External and statistical brains were unavailable, so deterministic rules are being used as the final fallback."))

        return candidates

    def _resolve_brain(self, snapshot: MarketSnapshot, provider: str | None) -> tuple[str, Any, str]:
        requested = (provider or self.config.default_brain or "rules").strip().lower()
        if requested == "auto":
            selected_name, selection_reason = self._select_auto_brain(snapshot)
            return selected_name, self.brains[selected_name], selection_reason

        if requested in self.brains:
            return requested, self.brains[requested], f"Explicit brain selection: {requested}."

        return "rules", self.brains["rules"], f"Requested brain '{requested}' is unavailable, so rules were used."

    def brain_status(self) -> dict[str, Any]:
        llm_available = []
        if self.config.sarvam.enabled and self.config.sarvam.api_key:
            llm_available.append(
                {
                    "name": "sarvam",
                    "type": "llm",
                    "active": "sarvam" in self.brains,
                    "model": self.config.sarvam.model,
                    "supported_models": list(self.config.sarvam.available_models),
                }
            )
        else:
            llm_available.append(
                {
                    "name": "sarvam",
                    "type": "llm",
                    "active": False,
                    "model": self.config.sarvam.model,
                    "supported_models": list(self.config.sarvam.available_models),
                    "blocker": "Sarvam adapter is ready, but it needs a valid API key to activate.",
                }
            )

        if self.config.openai.enabled and self.config.openai.api_key:
            llm_available.append(
                {
                    "name": "openai",
                    "type": "llm",
                    "active": "openai" in self.brains,
                    "model": self.config.openai.model,
                }
            )
        else:
            llm_available.append(
                {
                    "name": "openai",
                    "type": "llm",
                    "active": False,
                    "model": self.config.openai.model,
                    "blocker": "OpenAI adapter is ready, but it needs a valid API key to activate.",
                }
            )

        if self.config.gemini.enabled and self.config.gemini.api_key:
            llm_available.append(
                {
                    "name": "gemini",
                    "type": "llm",
                    "active": "gemini" in self.brains,
                    "model": self.config.gemini.model,
                }
            )
        else:
            llm_available.append(
                {
                    "name": "gemini",
                    "type": "llm",
                    "active": False,
                    "model": self.config.gemini.model,
                    "blocker": "Gemini adapter is ready, but it needs a valid API key to activate.",
                }
            )

        return {
            "default_brain": self.config.default_brain,
            "active_brains": sorted(self.brains.keys()),
            "auto_selector": {
                "enabled": self.config.default_brain == "auto",
                "priority": ["sarvam", "gemini", "quant", "rules"],
                "policy": "Sarvam for rich EMA+RSI snapshots, Gemini for RSI-led snapshots, quant for EMA-led snapshots, rules as fallback.",
            },
            "rules_engine": {
                "name": "rules",
                "type": "deterministic",
                "active": True,
                "signals": ["ema_crossover", "rsi_extremes"],
            },
            "llm_adapters": llm_available,
            "ml_models": [
                {
                    "name": "quant",
                    "type": "feature_score_model",
                    "active": True,
                    "features": ["ema_gap_pct", "rsi", "spread_penalty"],
                    "note": "Local statistical model available without external API keys.",
                }
            ],
            "ml_enabled": True,
            "summary": "Rule-based and local quant model engines are active. OpenAI and Gemini adapters are wired and can activate once API keys are configured.",
        }

    def evaluate_signal(self, snapshot_payload: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
        snapshot = MarketSnapshot.from_payload(snapshot_payload)
        requested = (provider or self.config.default_brain or "rules").strip().lower()
        fallback_events: list[dict[str, str]] = []

        if requested == "auto":
            signal = None
            brain_name = "rules"
            selection_reason = "Auto selector fell back to deterministic rules because richer model inputs were not available."
            for candidate_name, candidate_reason in self._auto_brain_candidates(snapshot):
                try:
                    signal = self.brains[candidate_name].evaluate(snapshot)
                    brain_name = candidate_name
                    selection_reason = candidate_reason
                    break
                except Exception as exc:
                    fallback_events.append({"brain": candidate_name, "error": str(exc)})

            if signal is None:
                raise RuntimeError("No trading brain was able to evaluate the current snapshot.")
        else:
            brain_name, brain, selection_reason = self._resolve_brain(snapshot, provider)
            try:
                signal = brain.evaluate(snapshot)
            except Exception as exc:
                if brain_name == "rules":
                    raise
                fallback_events.append({"brain": brain_name, "error": str(exc)})
                brain_name = "rules"
                selection_reason = f"{selection_reason} The requested brain failed, so deterministic rules were used instead."
                signal = self.brains["rules"].evaluate(snapshot)

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
            "selected_brain": brain_name,
            "selection_reason": selection_reason,
            "fallback_events": fallback_events,
            "signal": signal.to_dict(),
            "risk": assessment.to_dict(),
        }

    def submit_trade(self, snapshot_payload: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
        evaluated = self.evaluate_signal(snapshot_payload, provider)
        signal = evaluated["signal"]
        risk = evaluated["risk"]
        snapshot = MarketSnapshot.from_payload(evaluated["snapshot"])

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
            "brain_system": self.brain_status(),
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
