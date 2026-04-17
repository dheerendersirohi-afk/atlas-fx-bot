from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


@dataclass(slots=True)
class OandaCredentials:
    account_id: str
    access_token: str
    environment: str = "practice"

    @property
    def base_url(self) -> str:
        if self.environment == "live":
            return "https://api-fxtrade.oanda.com"
        return "https://api-fxpractice.oanda.com"

    def validate(self) -> None:
        if not self.account_id or self.account_id.startswith("YOUR_"):
            raise OandaApiError("OANDA account_id is missing or still set to a placeholder value.")
        if not self.access_token or self.access_token.startswith("YOUR_"):
            raise OandaApiError("OANDA access_token is missing or still set to a placeholder value.")
        if self.environment not in {"practice", "live"}:
            raise OandaApiError("OANDA environment must be either 'practice' or 'live'.")


def load_oanda_credentials(path: str | Path) -> OandaCredentials:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    connector = raw["connectors"]["oanda"]
    return OandaCredentials(
        account_id=str(connector["account_id"]),
        access_token=str(connector["access_token"]),
        environment=str(connector.get("environment", "practice")),
    )


class OandaApiError(RuntimeError):
    pass


class OandaClient:
    def __init__(self, credentials: OandaCredentials, timeout_seconds: int = 20) -> None:
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self.credentials.validate()

    def get_account_summary(self) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/v3/accounts/{self.credentials.account_id}/summary",
        )

    def get_prices(self, instruments: list[str]) -> dict[str, Any]:
        params = parse.urlencode({"instruments": ",".join(instruments)})
        return self._request_json(
            "GET",
            f"/v3/accounts/{self.credentials.account_id}/pricing?{params}",
        )

    def place_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss_price: str | None = None,
        take_profit_price: str | None = None,
    ) -> dict[str, Any]:
        order: dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }

        if stop_loss_price:
            order["stopLossOnFill"] = {"price": stop_loss_price}
        if take_profit_price:
            order["takeProfitOnFill"] = {"price": take_profit_price}

        return self._request_json(
            "POST",
            f"/v3/accounts/{self.credentials.account_id}/orders",
            {"order": order},
        )

    def _request_json(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        target = f"{self.credentials.base_url}{path}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.credentials.access_token}",
            "Accept-Datetime-Format": "RFC3339",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"

        req = request.Request(target, data=payload, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OandaApiError(f"OANDA HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise OandaApiError(f"OANDA connection error: {exc.reason}") from exc
