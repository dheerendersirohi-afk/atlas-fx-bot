from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BrokerConnectorSpec:
    key: str
    label: str
    transport: str
    auth: str
    environments: tuple[str, ...]
    integration_enabled: bool
    requires_backend: bool
    supports_market_data: bool
    supports_order_entry: bool
    supports_deposit_withdrawal: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class ConnectorRegistry:
    connectors: dict[str, BrokerConnectorSpec]

    def list_connectors(self) -> list[BrokerConnectorSpec]:
        return list(self.connectors.values())

    def get(self, key: str) -> BrokerConnectorSpec | None:
        return self.connectors.get(key)


def build_default_registry() -> ConnectorRegistry:
    return ConnectorRegistry(
        connectors={
            "paper": BrokerConnectorSpec(
                key="paper",
                label="Universal Paper Bridge",
                transport="local",
                auth="none",
                environments=("paper",),
                integration_enabled=True,
                requires_backend=False,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Safe default mode for testing.",),
            ),
            "oanda": BrokerConnectorSpec(
                key="oanda",
                label="OANDA REST v20",
                transport="https",
                auth="bearer-token",
                environments=("practice", "live"),
                integration_enabled=True,
                requires_backend=True,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Use a backend proxy so access tokens stay off the browser.",),
            ),
            "ctrader": BrokerConnectorSpec(
                key="ctrader",
                label="cTrader Open API",
                transport="tcp/websocket",
                auth="oauth2",
                environments=("demo", "live"),
                integration_enabled=True,
                requires_backend=True,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Live and demo environments should be handled separately.",),
            ),
            "metatrader5": BrokerConnectorSpec(
                key="metatrader5",
                label="MetaTrader 5 Bridge",
                transport="local-terminal",
                auth="terminal-login",
                environments=("demo", "live"),
                integration_enabled=True,
                requires_backend=True,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Requires a locally installed MT5 terminal.",),
            ),
            "metatrader4": BrokerConnectorSpec(
                key="metatrader4",
                label="MetaTrader 4 Bridge",
                transport="local-terminal",
                auth="terminal-login",
                environments=("demo", "live"),
                integration_enabled=True,
                requires_backend=True,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Requires a locally installed MT4 terminal and MQL4 bridge scripts.",),
            ),
            "ibkr": BrokerConnectorSpec(
                key="ibkr",
                label="IBKR Web API",
                transport="https/websocket",
                auth="oauth/session",
                environments=("paper", "live"),
                integration_enabled=True,
                requires_backend=True,
                supports_market_data=True,
                supports_order_entry=True,
                supports_deposit_withdrawal=False,
                notes=("Funding actions belong in IBKR account workflows, not this bot UI.",),
            ),
        }
    )
