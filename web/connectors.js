window.ATLAS_CONNECTORS = [
  {
    key: "paper",
    label: "Universal Paper Bridge",
    status: "active",
    transport: "Local simulation",
    auth: "None",
    environments: ["paper"],
    note: "Runs immediately in the browser with no broker credentials."
  },
  {
    key: "oanda",
    label: "OANDA REST v20",
    status: "integration_enabled",
    transport: "HTTPS REST",
    auth: "Bearer token",
    environments: ["practice", "live"],
    note: "Integration is enabled, but live use still needs a backend proxy and account token."
  },
  {
    key: "ctrader",
    label: "cTrader Open API",
    status: "integration_enabled",
    transport: "TCP / WebSocket",
    auth: "OAuth 2.0",
    environments: ["demo", "live"],
    note: "Integration is enabled, but live use still needs broker-linked credentials and a bridge service."
  },
  {
    key: "metatrader5",
    label: "MetaTrader 5 Bridge",
    status: "integration_enabled",
    transport: "Local terminal bridge",
    auth: "Terminal login",
    environments: ["demo", "live"],
    note: "Integration is enabled, but live use still needs MetaTrader 5 installed locally plus broker login."
  },
  {
    key: "metatrader4",
    label: "MetaTrader 4 Bridge",
    status: "integration_enabled",
    transport: "Local terminal bridge",
    auth: "Terminal login",
    environments: ["demo", "live"],
    note: "Integration is enabled, but live use still needs MetaTrader 4 installed locally plus MQL4 bridge scripts."
  },
  {
    key: "ibkr",
    label: "IBKR Web API",
    status: "integration_enabled",
    transport: "HTTPS / WebSocket",
    auth: "OAuth or session auth",
    environments: ["paper", "live"],
    note: "Integration is enabled, but live use still needs an authenticated brokerage session."
  }
];
