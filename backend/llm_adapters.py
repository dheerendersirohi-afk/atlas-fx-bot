from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from urllib import error, request

from .config import AIProviderConfig
from .models import MarketSnapshot, SignalDecision


class BaseBrain(ABC):
    name: str

    @abstractmethod
    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        raise NotImplementedError


class RuleBasedBrain(BaseBrain):
    name = "rules"

    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        if snapshot.ema_fast is not None and snapshot.ema_slow is not None:
            if snapshot.ema_fast > snapshot.ema_slow:
                return SignalDecision("BUY", 0.62, "Fast EMA above slow EMA.", 0.35, 1.2, self.name)
            if snapshot.ema_fast < snapshot.ema_slow:
                return SignalDecision("SELL", 0.62, "Fast EMA below slow EMA.", 0.35, 1.2, self.name)

        if snapshot.rsi is not None:
            if snapshot.rsi < 30:
                return SignalDecision("BUY", 0.58, "RSI indicates oversold conditions.", 0.35, 1.0, self.name)
            if snapshot.rsi > 70:
                return SignalDecision("SELL", 0.58, "RSI indicates overbought conditions.", 0.35, 1.0, self.name)

        return SignalDecision("HOLD", 0.4, "No strong rules-based edge detected.", 0.35, 1.0, self.name)


class OpenAIBrain(BaseBrain):
    name = "openai"

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        if not self.config.enabled or not self.config.api_key:
            raise RuntimeError("OpenAI brain is not configured.")

        prompt = (
            "Return a strict JSON object with keys action, confidence, reason, stop_loss_pct, take_profit_pct. "
            "Allowed action values: BUY, SELL, HOLD. "
            f"Market snapshot: {json.dumps(snapshot.to_dict())}"
        )
        payload = {
            "model": self.config.model,
            "input": prompt,
            "max_output_tokens": 300,
        }
        response = _post_json(
            self.config.base_url,
            payload,
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        text = _extract_openai_text(response)
        parsed = json.loads(text)
        return SignalDecision(
            action=parsed["action"],
            confidence=float(parsed["confidence"]),
            reason=str(parsed["reason"]),
            stop_loss_pct=float(parsed["stop_loss_pct"]),
            take_profit_pct=float(parsed["take_profit_pct"]),
            provider=self.name,
            raw_response=response,
        )


class GeminiBrain(BaseBrain):
    name = "gemini"

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    def evaluate(self, snapshot: MarketSnapshot) -> SignalDecision:
        if not self.config.enabled or not self.config.api_key:
            raise RuntimeError("Gemini brain is not configured.")

        target = self.config.base_url.format(model=self.config.model)
        prompt = (
            "Return strict JSON only with keys action, confidence, reason, stop_loss_pct, take_profit_pct. "
            "Allowed action values: BUY, SELL, HOLD. "
            f"Market snapshot: {json.dumps(snapshot.to_dict())}"
        )
        response = _post_json(
            f"{target}?key={self.config.api_key}",
            {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                        ]
                    }
                ]
            },
            {"Content-Type": "application/json"},
        )
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        return SignalDecision(
            action=parsed["action"],
            confidence=float(parsed["confidence"]),
            reason=str(parsed["reason"]),
            stop_loss_pct=float(parsed["stop_loss_pct"]),
            take_profit_pct=float(parsed["take_profit_pct"]),
            provider=self.name,
            raw_response=response,
        )


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _extract_openai_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                return text
    raise RuntimeError("OpenAI response did not contain a text output.")
