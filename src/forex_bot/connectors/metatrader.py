from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


_MT4_BUILTINS = {
    "ima": "iMA({symbol}, {timeframe}, {period}, {shift}, {method}, {price}, {bar_shift})",
    "irsi": "iRSI({symbol}, {timeframe}, {period}, {price}, {bar_shift})",
    "iatr": "iATR({symbol}, {timeframe}, {period}, {bar_shift})",
    "imacd": "iMACD({symbol}, {timeframe}, {fast}, {slow}, {signal}, {price}, {macd_mode}, {bar_shift})",
    "icustom": "iCustom({symbol}, {timeframe}, {name}, {inputs}{mode}, {bar_shift})",
}

_MT5_BUILTINS = {
    "ima": 'int handle=iMA({symbol}, {timeframe}, {period}, {shift}, {method}, {price});',
    "irsi": 'int handle=iRSI({symbol}, {timeframe}, {period}, {price});',
    "iatr": 'int handle=iATR({symbol}, {timeframe}, {period});',
    "imacd": 'int handle=iMACD({symbol}, {timeframe}, {fast}, {slow}, {signal}, {price});',
    "icustom": 'int handle=iCustom({symbol}, {timeframe}, {name}{inputs});',
}


@dataclass(slots=True)
class MetaTraderTerminalConfig:
    platform: str
    terminal_path: str
    login: int
    password: str
    server: str
    mode: str = "live"
    integration_enabled: bool = True

    def validate(self) -> None:
        if self.platform not in {"metatrader4", "metatrader5"}:
            raise ValueError(f"Unsupported MetaTrader platform: {self.platform}")
        if not self.terminal_path or self.terminal_path.startswith("YOUR_"):
            raise ValueError(f"{self.platform} terminal_path is missing or still set to a placeholder value.")
        if self.login <= 0:
            raise ValueError(f"{self.platform} login must be a real account number.")
        if not self.password or self.password.startswith("YOUR_"):
            raise ValueError(f"{self.platform} password is missing or still set to a placeholder value.")
        if not self.server or self.server.startswith("YOUR_"):
            raise ValueError(f"{self.platform} server is missing or still set to a placeholder value.")
        if self.mode not in {"demo", "live"}:
            raise ValueError(f"{self.platform} mode must be either 'demo' or 'live'.")


@dataclass(slots=True)
class MetaTraderRiskControls:
    max_risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 1.0
    max_spread_points: int = 30
    stop_loss_pct: float = 0.35
    take_profit_pct: float = 1.2
    allow_live_trading: bool = False


@dataclass(slots=True)
class IndicatorSpec:
    name: str
    symbol: str = "NULL"
    timeframe: str = "PERIOD_CURRENT"
    period: int = 14
    shift: int = 0
    method: str = "MODE_SMA"
    price: str = "PRICE_CLOSE"
    fast: int = 12
    slow: int = 26
    signal: int = 9
    mode: int = 0
    bar_shift: int = 0
    custom_indicator: str = ""
    custom_inputs: tuple[str, ...] = field(default_factory=tuple)


def load_metatrader_terminal_config(path: str | Path, platform: str, validate: bool = True) -> MetaTraderTerminalConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    connector = raw["connectors"][platform]
    config = MetaTraderTerminalConfig(
        platform=platform,
        terminal_path=str(connector["terminal_path"]),
        login=int(connector["login"]),
        password=str(connector["password"]),
        server=str(connector["server"]),
        mode=str(connector.get("mode", "live")),
        integration_enabled=bool(connector.get("integration_enabled", True)),
    )
    if validate:
        config.validate()
    return config


def load_metatrader_risk_controls(path: str | Path, platform: str) -> MetaTraderRiskControls:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    connector = raw["connectors"][platform]
    risk = connector.get("risk", {})
    return MetaTraderRiskControls(
        max_risk_per_trade_pct=float(risk.get("max_risk_per_trade_pct", 0.25)),
        max_daily_loss_pct=float(risk.get("max_daily_loss_pct", 1.0)),
        max_spread_points=int(risk.get("max_spread_points", 30)),
        stop_loss_pct=float(risk.get("stop_loss_pct", 0.35)),
        take_profit_pct=float(risk.get("take_profit_pct", 1.2)),
        allow_live_trading=bool(risk.get("allow_live_trading", False)),
    )


def build_mt4_indicator_call(spec: IndicatorSpec) -> str:
    key = spec.name.lower()
    if key not in _MT4_BUILTINS:
        raise ValueError(f"Unsupported MT4 indicator: {spec.name}")
    template = _MT4_BUILTINS[key]
    inputs = ""
    mode_suffix = ""
    macd_mode = "MODE_MAIN" if spec.mode == 0 else "MODE_SIGNAL"
    if key == "icustom":
        inputs = "".join(f"{value}, " for value in spec.custom_inputs)
        mode_suffix = f"{spec.mode}, "
    return template.format(
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        period=spec.period,
        shift=spec.shift,
        method=spec.method,
        price=spec.price,
        fast=spec.fast,
        slow=spec.slow,
        signal=spec.signal,
        macd_mode=macd_mode,
        bar_shift=spec.bar_shift,
        name=f'"{spec.custom_indicator}"',
        inputs=inputs,
        mode=mode_suffix,
    )


def build_mt5_indicator_script(spec: IndicatorSpec) -> str:
    key = spec.name.lower()
    if key not in _MT5_BUILTINS:
        raise ValueError(f"Unsupported MT5 indicator: {spec.name}")
    template = _MT5_BUILTINS[key]
    inputs = ""
    if key == "icustom":
        inputs = "".join(f", {value}" for value in spec.custom_inputs)

    handle_line = template.format(
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        period=spec.period,
        shift=spec.shift,
        method=spec.method,
        price=spec.price,
        fast=spec.fast,
        slow=spec.slow,
        signal=spec.signal,
        name=f'"{spec.custom_indicator}"',
        inputs=inputs,
    )
    buffer_index = 1 if key == "imacd" and spec.mode == 1 else 0
    return "\n".join(
        [
            "// Auto-generated MT5 indicator probe",
            "#property script_show_inputs",
            "void OnStart()",
            "{",
            f"   {handle_line}",
            "   if(handle==INVALID_HANDLE)",
            "   {",
            '      Print("Indicator handle creation failed: ", GetLastError());',
            "      return;",
            "   }",
            "   double values[];",
            "   ArraySetAsSeries(values, true);",
            f"   if(CopyBuffer(handle, {buffer_index}, 0, 5, values) < 0)",
            "   {",
            '      Print("CopyBuffer failed: ", GetLastError());',
            "      IndicatorRelease(handle);",
            "      return;",
            "   }",
            '   Print("Indicator values: ", ArrayToString(values));',
            "   IndicatorRelease(handle);",
            "}",
        ]
    )


def build_mt4_indicator_script(spec: IndicatorSpec) -> str:
    call = build_mt4_indicator_call(spec)
    return "\n".join(
        [
            "// Auto-generated MT4 indicator probe",
            "#property strict",
            "void OnStart()",
            "{",
            f"   double indicatorValue = {call};",
            '   Print("Indicator value: ", DoubleToString(indicatorValue, Digits));',
            "}",
        ]
    )


def build_mt5_demo_ea(symbol: str, risk: MetaTraderRiskControls) -> str:
    return "\n".join(
        [
            "// Auto-generated MT5 demo EA scaffold",
            "#property strict",
            "#include <Trade/Trade.mqh>",
            "CTrade trade;",
            f'input string InpSymbol = "{symbol}";',
            f"input double InpRiskPerTradePct = {risk.max_risk_per_trade_pct};",
            f"input double InpMaxDailyLossPct = {risk.max_daily_loss_pct};",
            f"input int InpMaxSpreadPoints = {risk.max_spread_points};",
            f"input double InpStopLossPct = {risk.stop_loss_pct};",
            f"input double InpTakeProfitPct = {risk.take_profit_pct};",
            f'input bool InpAllowLiveTrading = {"true" if risk.allow_live_trading else "false"};',
            "",
            "double startingBalance = 0.0;",
            "",
            "int OnInit()",
            "{",
            "   if(!SymbolSelect(InpSymbol, true))",
            "   {",
            '      Print("Failed to select symbol: ", InpSymbol);',
            "      return(INIT_FAILED);",
            "   }",
            "   startingBalance = AccountInfoDouble(ACCOUNT_BALANCE);",
            "   return(INIT_SUCCEEDED);",
            "}",
            "",
            "bool RiskChecksPassed()",
            "{",
            "   double balance = AccountInfoDouble(ACCOUNT_BALANCE);",
            "   double drawdownPct = startingBalance <= 0 ? 0 : ((startingBalance - balance) / startingBalance) * 100.0;",
            "   if(drawdownPct >= InpMaxDailyLossPct)",
            "   {",
            '      Print("Daily loss limit reached.");',
            "      return(false);",
            "   }",
            "",
            "   MqlTick tick;",
            "   if(!SymbolInfoTick(InpSymbol, tick))",
            "   {",
            '      Print("Failed to read symbol tick.");',
            "      return(false);",
            "   }",
            "   double spreadPoints = (tick.ask - tick.bid) / _Point;",
            "   if(spreadPoints > InpMaxSpreadPoints)",
            "   {",
            '      Print("Spread guard blocked trade.");',
            "      return(false);",
            "   }",
            "   return(true);",
            "}",
            "",
            "double ComputeVolume()",
            "{",
            "   double balance = AccountInfoDouble(ACCOUNT_BALANCE);",
            "   double riskAmount = balance * (InpRiskPerTradePct / 100.0);",
            "   double contractSize = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_CONTRACT_SIZE);",
            "   double price = SymbolInfoDouble(InpSymbol, SYMBOL_ASK);",
            "   if(contractSize <= 0 || price <= 0)",
            "      return(0.01);",
            "   double rawLots = riskAmount / (contractSize * price * (InpStopLossPct / 100.0));",
            "   double volumeMin = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MIN);",
            "   double volumeMax = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MAX);",
            "   double volumeStep = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_STEP);",
            "   if(volumeStep <= 0)",
            "      volumeStep = 0.01;",
            "   double normalized = MathMax(volumeMin, MathFloor(rawLots / volumeStep) * volumeStep);",
            "   if(volumeMax > 0)",
            "      normalized = MathMin(normalized, volumeMax);",
            "   return(normalized);",
            "}",
            "",
            "void OnTick()",
            "{",
            "   long tradeMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);",
            "   bool isDemo = (tradeMode == ACCOUNT_TRADE_MODE_DEMO);",
            "   if(!InpAllowLiveTrading && !isDemo && !MQLInfoInteger(MQL_TESTER))",
            "   {",
            '      Print("Live trading is disabled by risk controls.");',
            "      return;",
            "   }",
            "   if(PositionSelect(InpSymbol))",
            "      return;",
            "   if(!RiskChecksPassed())",
            "      return;",
            "",
            "   int maFast = iMA(InpSymbol, PERIOD_M5, 5, 0, MODE_EMA, PRICE_CLOSE);",
            "   int maSlow = iMA(InpSymbol, PERIOD_M5, 12, 0, MODE_EMA, PRICE_CLOSE);",
            "   if(maFast == INVALID_HANDLE || maSlow == INVALID_HANDLE)",
            "      return;",
            "",
            "   double fastValues[];",
            "   double slowValues[];",
            "   ArraySetAsSeries(fastValues, true);",
            "   ArraySetAsSeries(slowValues, true);",
            "   if(CopyBuffer(maFast, 0, 0, 2, fastValues) < 0 || CopyBuffer(maSlow, 0, 0, 2, slowValues) < 0)",
            "   {",
            "      IndicatorRelease(maFast);",
            "      IndicatorRelease(maSlow);",
            "      return;",
            "   }",
            "",
            "   bool bullishCross = fastValues[1] <= slowValues[1] && fastValues[0] > slowValues[0];",
            "   bool bearishCross = fastValues[1] >= slowValues[1] && fastValues[0] < slowValues[0];",
            "   double volume = ComputeVolume();",
            "   double ask = SymbolInfoDouble(InpSymbol, SYMBOL_ASK);",
            "   double bid = SymbolInfoDouble(InpSymbol, SYMBOL_BID);",
            "   double buySl = ask * (1.0 - (InpStopLossPct / 100.0));",
            "   double buyTp = ask * (1.0 + (InpTakeProfitPct / 100.0));",
            "   double sellSl = bid * (1.0 + (InpStopLossPct / 100.0));",
            "   double sellTp = bid * (1.0 - (InpTakeProfitPct / 100.0));",
            "",
            "   if(bullishCross)",
            "      trade.Buy(volume, InpSymbol, ask, buySl, buyTp, \"Atlas demo buy\");",
            "   else if(bearishCross)",
            "      trade.Sell(volume, InpSymbol, bid, sellSl, sellTp, \"Atlas demo sell\");",
            "",
            "   IndicatorRelease(maFast);",
            "   IndicatorRelease(maSlow);",
            "}",
        ]
    )
