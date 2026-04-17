# Atlas FX Bot

This workspace now includes two layers:

- a Python forex bot scaffold in `src/forex_bot`
- a zero-install local dashboard in `web/` with only two wallet actions exposed in the main UI: deposit and withdrawal
- a live-integration catalog for OANDA, cTrader, MetaTrader 4, MetaTrader 5, and IBKR

## Run the local app

From PowerShell:

```powershell
.\run-bot.ps1
```

Then open the reported `web\index.html` file in a browser.

If you want the script to launch the browser for you:

```powershell
.\run-bot.ps1 -Open
```

If you want it to open the dashboard and immediately start the paper bot:

```powershell
.\run-bot.ps1 -Open -StartBot
```

## Free hosting

The `web/` app is now prepared for GitHub Pages deployment through [.github/workflows/github-pages.yml](C:\Users\Administrator\Desktop\Bot\.github\workflows\github-pages.yml). Hosting notes are in [DEPLOYMENT.md](C:\Users\Administrator\Desktop\Bot\DEPLOYMENT.md).

## What the web app does

- runs a paper-trading simulation in the browser
- tracks EUR/USD, GBP/USD, and USD/JPY
- opens and closes simulated trades automatically
- keeps local wallet actions limited to deposit and withdrawal
- stores state in browser local storage
- shows which forex platforms are integration-ready versus truly active

## What the app does not do

- It does not connect real deposits or withdrawals to a live broker by default.
- It does not place live forex trades on every platform worldwide.
- It does not collect future market data or guarantee profit targets.

## Why it is structured this way

Real broker integration needs one adapter per platform, plus API credentials, compliance checks, and testing for order rules, margin, spreads, slippage, and account permissions. The dashboard is ready for that structure, but the active connector is a paper bridge so the app remains safe to run immediately.

## Existing Python scaffold

The Python code remains available for later work on:

- CSV backtesting
- strategy development
- broker-specific execution adapters
- richer risk management
- connector registry definitions in `src/forex_bot/connectors`
- an OANDA REST-v20 client in `src/forex_bot/connectors/oanda.py`
- MetaTrader indicator bridge helpers in `src/forex_bot/connectors/metatrader.py`

## Live connector config

Use `config.live-connectors.example.json` as the template for real broker credentials and environment selection. Keep real secrets out of the browser UI.

For OANDA, this project targets the current `REST-v20` API naming used in OANDA's official developer docs, not a separate `REST v2` label.

All supported broker entries in `config.live-connectors.example.json` are now marked as integration-enabled, so the bot is prepared for OANDA, cTrader, MetaTrader 4, MetaTrader 5, and IBKR onboarding. Real execution still requires valid credentials and a secure backend or bridge.

## OANDA CLI

After you replace the OANDA placeholders in `config.live-connectors.example.json`, the project includes a simple OANDA helper CLI:

```powershell
python -m forex_bot.oanda_cli --credentials config.live-connectors.example.json account
python -m forex_bot.oanda_cli --credentials config.live-connectors.example.json prices --instruments EUR_USD,GBP_USD
python -m forex_bot.oanda_cli --credentials config.live-connectors.example.json order --instrument EUR_USD --units 100
```

This wiring is now present in code, but it still cannot be exercised on this machine until a working Python runtime and real OANDA credentials are available.

## MetaTrader CLI

The project now also includes a MetaTrader helper CLI for `MT4` and `MT5` indicator probes:

```powershell
python -m forex_bot.mt_cli --credentials config.live-connectors.example.json config --platform metatrader5
python -m forex_bot.mt_cli --credentials config.live-connectors.example.json indicator --platform metatrader5 --name ima --period 20
python -m forex_bot.mt_cli --credentials config.live-connectors.example.json indicator --platform metatrader4 --name icustom --custom-indicator MyIndicators\\SignalArrow --mode 0
python -m forex_bot.mt_cli --credentials config.live-connectors.example.json demo-ea --symbol EURUSD
```

The MT4/MT5 helper generates MQL probe scripts for built-in indicators such as `iMA`, `iRSI`, `iATR`, and `iMACD`, plus `iCustom` for custom indicators. MT5 uses indicator handles and `CopyBuffer`, while MT4 indicator calls return values directly.

The `demo-ea` command generates an MT5 Expert Advisor scaffold with explicit spread, stop-loss, take-profit, and daily-loss guards. The example config now defaults MT5 to demo mode with `allow_live_trading` set to `false`.

## Next upgrade path

If you later want live integration, the safest path is to pick one broker first, for example OANDA or MetaTrader 5, and add a dedicated adapter with API keys and explicit withdrawal restrictions.
