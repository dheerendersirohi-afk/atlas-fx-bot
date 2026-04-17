"""Forex trading bot scaffold."""

from .config import BotConfig, load_config
from .connectors import (
    IndicatorSpec,
    MetaTraderTerminalConfig,
    MetaTraderRiskControls,
    OandaClient,
    OandaCredentials,
    build_mt4_indicator_script,
    build_mt5_demo_ea,
    build_mt5_indicator_script,
    load_metatrader_risk_controls,
    load_metatrader_terminal_config,
    load_oanda_credentials,
)
from .engine import TradingEngine

__all__ = [
    "BotConfig",
    "IndicatorSpec",
    "MetaTraderTerminalConfig",
    "MetaTraderRiskControls",
    "TradingEngine",
    "build_mt4_indicator_script",
    "build_mt5_demo_ea",
    "build_mt5_indicator_script",
    "load_config",
    "load_metatrader_risk_controls",
    "load_metatrader_terminal_config",
    "OandaClient",
    "OandaCredentials",
    "load_oanda_credentials",
]
