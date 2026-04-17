# Live Integration Notes

This project now includes a connector catalog for these forex-capable routes:

- Paper connector
- OANDA REST v20
- cTrader Open API
- MetaTrader 4 bridge
- MetaTrader 5 bridge
- IBKR Web API / Client Portal

All of the above are now marked integration-enabled in the example connector config so you can onboard any of them next.

## Important architecture rule

The browser dashboard should not hold live broker secrets directly. For real trading, use a backend or local bridge process that:

- stores credentials securely
- performs broker authentication
- signs requests
- normalizes account, price, order, and position data
- enforces risk checks before any live order

## Connector-specific notes

### OANDA

- use the REST-v20 API naming from OANDA's official developer documentation
- token-based REST access
- account and order endpoints available
- pricing endpoints available

### cTrader

- OAuth-based account authentication
- TCP or WebSocket connectivity depending on implementation
- separate demo and live environments

### MetaTrader 4

- requires a local MetaTrader 4 terminal
- custom indicators can be accessed through MQL4 indicator calls such as `iCustom`
- built-in indicators return values directly from functions like `iMA`, `iRSI`, and `iATR`

### MetaTrader 5

- requires a local MetaTrader 5 terminal
- Python integration can initialize the terminal, log in, inspect account data, and send orders
- indicator access is handle-based and values are retrieved with `CopyBuffer`

### IBKR

- Web API / Client Portal requires authenticated sessions
- supports HTTP plus websocket-style event flows
- brokerage session is required for order placement

## Recommended rollout

1. Keep paper mode as the default.
2. Add exactly one live connector first.
3. Validate account reads before enabling orders.
4. Enable trading only after paper and demo tests pass.
