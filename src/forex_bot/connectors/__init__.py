"""Connector specs for live broker integrations."""

from .base import BrokerConnectorSpec, ConnectorRegistry, build_default_registry
from .metatrader import (
    IndicatorSpec,
    MetaTraderTerminalConfig,
    MetaTraderRiskControls,
    build_mt4_indicator_call,
    build_mt4_indicator_script,
    build_mt5_demo_ea,
    build_mt5_indicator_script,
    load_metatrader_risk_controls,
    load_metatrader_terminal_config,
)
from .oanda import OandaApiError, OandaClient, OandaCredentials, load_oanda_credentials

__all__ = [
    "BrokerConnectorSpec",
    "ConnectorRegistry",
    "build_default_registry",
    "IndicatorSpec",
    "MetaTraderTerminalConfig",
    "MetaTraderRiskControls",
    "build_mt4_indicator_call",
    "build_mt4_indicator_script",
    "build_mt5_demo_ea",
    "build_mt5_indicator_script",
    "load_metatrader_risk_controls",
    "load_metatrader_terminal_config",
    "OandaApiError",
    "OandaClient",
    "OandaCredentials",
    "load_oanda_credentials",
]
