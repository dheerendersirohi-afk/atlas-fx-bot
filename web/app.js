(function () {
  const stateKey = "atlas-fx-bot-state";
  const initialState = {
    connector: "Universal Paper Bridge",
    running: false,
    balance: 10000,
    pairs: {
      "EUR/USD": { price: 1.0862, history: [1.0831, 1.0838, 1.0844, 1.0853, 1.0862] },
      "GBP/USD": { price: 1.2715, history: [1.2682, 1.2687, 1.2696, 1.2702, 1.2715] },
      "USD/JPY": { price: 153.24, history: [152.91, 152.98, 153.04, 153.17, 153.24] }
    },
    openPositions: [],
    closedPositions: [],
    logs: [
      {
        type: "system",
        message: "Atlas FX Bot initialized in paper mode.",
        timestamp: new Date().toISOString()
      }
    ]
  };

  const ui = {
    balance: document.getElementById("walletBalance"),
    amount: document.getElementById("walletAmount"),
    deposit: document.getElementById("depositBtn"),
    withdraw: document.getElementById("withdrawBtn"),
    toggleBot: document.getElementById("toggleBot"),
    botStatus: document.getElementById("botStatus"),
    connectorName: document.getElementById("connectorName"),
    openTrades: document.getElementById("openTrades"),
    closedTrades: document.getElementById("closedTrades"),
    winRate: document.getElementById("winRate"),
    netPnl: document.getElementById("netPnl"),
    tickerList: document.getElementById("tickerList"),
    connectorList: document.getElementById("connectorList"),
    activityLog: document.getElementById("activityLog")
  };
  const storage = createStorage();

  let state = loadState();
  let timerId = null;
  const shouldAutoStart = window.location.hash === "#start";

  if (Object.values(ui).some((element) => !element)) {
    throw new Error("Atlas FX Bot UI failed to initialize because required elements are missing.");
  }

  function cloneInitialState() {
    return JSON.parse(JSON.stringify(initialState));
  }

  function createStorage() {
    let memoryState = null;

    try {
      if (!window.localStorage) {
        throw new Error("localStorage unavailable");
      }

      const probeKey = `${stateKey}-probe`;
      window.localStorage.setItem(probeKey, "1");
      window.localStorage.removeItem(probeKey);

      return {
        get() {
          return window.localStorage.getItem(stateKey);
        },
        set(value) {
          window.localStorage.setItem(stateKey, value);
        }
      };
    } catch (_error) {
      return {
        get() {
          return memoryState;
        },
        set(value) {
          memoryState = value;
        }
      };
    }
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function normalizePairMap(input) {
    const fallback = cloneInitialState().pairs;
    if (!input || typeof input !== "object") {
      return fallback;
    }

    const normalized = {};
    Object.entries(fallback).forEach(([pair, defaults]) => {
      const candidate = input[pair];
      const history = Array.isArray(candidate && candidate.history)
        ? candidate.history.filter(isFiniteNumber).slice(-8)
        : defaults.history.slice();

      normalized[pair] = {
        price: isFiniteNumber(candidate && candidate.price)
          ? candidate.price
          : history[history.length - 1] || defaults.price,
        history: history.length ? history : defaults.history.slice()
      };
    });
    return normalized;
  }

  function normalizePosition(position) {
    if (!position || typeof position !== "object") {
      return null;
    }

    if (
      typeof position.pair !== "string" ||
      (position.side !== "BUY" && position.side !== "SELL") ||
      !isFiniteNumber(position.units) ||
      !isFiniteNumber(position.entry) ||
      !isFiniteNumber(position.stop) ||
      !isFiniteNumber(position.target)
    ) {
      return null;
    }

    return {
      id: typeof position.id === "string" ? position.id : `${position.pair}-${Date.now()}`,
      pair: position.pair,
      side: position.side,
      units: position.units,
      entry: position.entry,
      stop: position.stop,
      target: position.target,
      openedAt: typeof position.openedAt === "string" ? position.openedAt : new Date().toISOString()
    };
  }

  function normalizeClosedPosition(position) {
    const normalized = normalizePosition(position);
    if (!normalized || !isFiniteNumber(position.pnl) || !isFiniteNumber(position.exit)) {
      return null;
    }

    return {
      ...normalized,
      closedAt: typeof position.closedAt === "string" ? position.closedAt : new Date().toISOString(),
      exit: position.exit,
      pnl: position.pnl
    };
  }

  function normalizeLogs(input) {
    if (!Array.isArray(input)) {
      return cloneInitialState().logs;
    }

    const normalized = input
      .filter((entry) => entry && typeof entry === "object" && typeof entry.message === "string")
      .map((entry) => ({
        type: typeof entry.type === "string" ? entry.type : "system",
        message: entry.message,
        timestamp: typeof entry.timestamp === "string" ? entry.timestamp : new Date().toISOString()
      }))
      .slice(0, 12);

    return normalized.length ? normalized : cloneInitialState().logs;
  }

  function normalizeState(rawState) {
    const fallback = cloneInitialState();
    if (!rawState || typeof rawState !== "object") {
      return fallback;
    }

    return {
      connector: typeof rawState.connector === "string" ? rawState.connector : fallback.connector,
      running: Boolean(rawState.running),
      balance: isFiniteNumber(rawState.balance) && rawState.balance >= 0 ? rawState.balance : fallback.balance,
      pairs: normalizePairMap(rawState.pairs),
      openPositions: Array.isArray(rawState.openPositions)
        ? rawState.openPositions.map(normalizePosition).filter(Boolean).slice(0, 3)
        : [],
      closedPositions: Array.isArray(rawState.closedPositions)
        ? rawState.closedPositions.map(normalizeClosedPosition).filter(Boolean).slice(0, 20)
        : [],
      logs: normalizeLogs(rawState.logs)
    };
  }

  function loadState() {
    try {
      const raw = storage.get();
      return raw ? normalizeState(JSON.parse(raw)) : cloneInitialState();
    } catch (_error) {
      return cloneInitialState();
    }
  }

  function saveState() {
    storage.set(JSON.stringify(state));
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD"
    }).format(value);
  }

  function formatTimestamp(value) {
    const timestamp = new Date(value);
    return Number.isNaN(timestamp.getTime()) ? "Unknown time" : timestamp.toLocaleString();
  }

  function addLog(type, message) {
    state.logs.unshift({
      type,
      message,
      timestamp: new Date().toISOString()
    });
    state.logs = state.logs.slice(0, 12);
  }

  function updateWallet(amountDelta, action) {
    const amount = Number(ui.amount.value);
    if (!Number.isFinite(amount) || amount <= 0) {
      addLog("wallet", "Enter a valid amount before using wallet actions.");
      saveState();
      render();
      return;
    }

    if (amountDelta < 0 && state.balance < Math.abs(amountDelta)) {
      addLog("wallet", "Withdrawal blocked because the local wallet balance is too low.");
      saveState();
      render();
      return;
    }

    state.balance += amountDelta;
    addLog("wallet", `${action} ${formatMoney(Math.abs(amountDelta))} in the local wallet simulator.`);
    saveState();
    render();
  }

  function calculateSignal(history) {
    if (history.length < 5) {
      return null;
    }

    const fast = average(history.slice(-3));
    const slow = average(history.slice(-5));
    if (fast > slow * 1.0006) {
      return "BUY";
    }
    if (fast < slow * 0.9994) {
      return "SELL";
    }
    return null;
  }

  function average(values) {
    return values.reduce((total, value) => total + value, 0) / values.length;
  }

  function tickMarket() {
    Object.entries(state.pairs).forEach(([pair, data]) => {
      const direction = Math.random() - 0.48;
      const scale = pair === "USD/JPY" ? 0.08 : 0.0009;
      const nextPrice = Number((data.price + direction * scale).toFixed(pair === "USD/JPY" ? 3 : 5));
      data.price = nextPrice;
      data.history.push(nextPrice);
      data.history = data.history.slice(-8);

      maybeOpenTrade(pair, data);
      maybeCloseTrades(pair, data.price);
    });

    saveState();
    render();
  }

  function maybeOpenTrade(pair, data) {
    if (state.openPositions.length >= 3) {
      return;
    }

    if (state.openPositions.some((position) => position.pair === pair)) {
      return;
    }

    const signal = calculateSignal(data.history);
    if (!signal) {
      return;
    }

    const units = Number((state.balance * 0.02).toFixed(2));
    if (units <= 0) {
      return;
    }

    const stop = signal === "BUY" ? data.price * 0.997 : data.price * 1.003;
    const target = signal === "BUY" ? data.price * 1.012 : data.price * 0.988;

    state.openPositions.push({
      id: `${pair}-${Date.now()}`,
      pair,
      side: signal,
      units,
      entry: data.price,
      stop,
      target,
      openedAt: new Date().toISOString()
    });

    addLog("trade", `${signal} opened on ${pair} at ${data.price}.`);
  }

  function maybeCloseTrades(pair, price) {
    const survivors = [];
    state.openPositions.forEach((position) => {
      if (position.pair !== pair) {
        survivors.push(position);
        return;
      }

      const hitStop =
        position.side === "BUY" ? price <= position.stop : price >= position.stop;
      const hitTarget =
        position.side === "BUY" ? price >= position.target : price <= position.target;

      if (!hitStop && !hitTarget) {
        survivors.push(position);
        return;
      }

      const pnlDirection = position.side === "BUY" ? 1 : -1;
      const pnl = (price - position.entry) * position.units * pnlDirection;
      state.balance += pnl;
      state.closedPositions.unshift({
        ...position,
        closedAt: new Date().toISOString(),
        exit: price,
        pnl
      });
      state.closedPositions = state.closedPositions.slice(0, 20);
      addLog(
        "trade",
        `${position.side} closed on ${pair} at ${price} with ${pnl >= 0 ? "profit" : "loss"} ${formatMoney(pnl)}.`
      );
    });

    state.openPositions = survivors;
  }

  function toggleBot() {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }

    state.running = !state.running;
    if (state.running) {
      timerId = window.setInterval(tickMarket, 2200);
      addLog("system", "Paper bot started. Simulated market feed is running.");
    } else {
      window.clearInterval(timerId);
      timerId = null;
      addLog("system", "Paper bot stopped.");
    }
    saveState();
    render();
  }

  function renderTickers() {
    ui.tickerList.innerHTML = "";
    Object.entries(state.pairs).forEach(([pair, data]) => {
      const signal = calculateSignal(data.history) || "WAIT";
      const row = document.createElement("div");
      row.className = "ticker-item";
      const left = document.createElement("div");
      const pairLabel = document.createElement("strong");
      pairLabel.textContent = pair;
      const signalLabel = document.createElement("span");
      signalLabel.className = "ticker-meta";
      signalLabel.textContent = `Signal: ${signal}`;
      left.appendChild(pairLabel);
      left.appendChild(signalLabel);

      const right = document.createElement("div");
      const priceLabel = document.createElement("strong");
      priceLabel.textContent = String(data.price);
      const metaLabel = document.createElement("span");
      metaLabel.className = "ticker-meta";
      metaLabel.textContent = "Paper feed";
      right.appendChild(priceLabel);
      right.appendChild(metaLabel);

      row.appendChild(left);
      row.appendChild(right);
      ui.tickerList.appendChild(row);
    });
  }

  function renderLogs() {
    ui.activityLog.innerHTML = "";
    state.logs.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "log-item";
      const message = document.createElement("strong");
      message.textContent = entry.message;
      const time = document.createElement("time");
      time.textContent = formatTimestamp(entry.timestamp);
      row.appendChild(message);
      row.appendChild(time);
      ui.activityLog.appendChild(row);
    });
  }

  function renderConnectors() {
    ui.connectorList.innerHTML = "";
    const connectors = Array.isArray(window.ATLAS_CONNECTORS) ? window.ATLAS_CONNECTORS : [];
    connectors.forEach((connector) => {
      const environments = Array.isArray(connector.environments) ? connector.environments : [];
      const row = document.createElement("div");
      row.className = "connector-item";

      const top = document.createElement("div");
      top.className = "connector-top";

      const name = document.createElement("strong");
      name.textContent = connector.label;

      const tag = document.createElement("span");
      tag.className = "connector-tag";
      tag.textContent =
        connector.status === "active"
          ? "Active"
          : connector.status === "integration_enabled"
            ? "Integration Enabled"
            : "Backend Needed";

      top.appendChild(name);
      top.appendChild(tag);

      const meta = document.createElement("span");
      meta.className = "connector-meta";
      meta.textContent = `${connector.transport || "Unknown"} | ${connector.auth || "Unknown"} | ${environments.join(", ") || "Unknown"}`;

      const note = document.createElement("span");
      note.className = "connector-meta";
      note.textContent = connector.note || "No connector note available.";

      row.appendChild(top);
      row.appendChild(meta);
      row.appendChild(note);
      ui.connectorList.appendChild(row);
    });
  }

  function renderStats() {
    const wins = state.closedPositions.filter((trade) => trade.pnl > 0).length;
    const netPnl = state.closedPositions.reduce((total, trade) => total + trade.pnl, 0);
    const winRate = state.closedPositions.length
      ? Math.round((wins / state.closedPositions.length) * 100)
      : 0;

    ui.openTrades.textContent = String(state.openPositions.length);
    ui.closedTrades.textContent = String(state.closedPositions.length);
    ui.winRate.textContent = `${winRate}%`;
    ui.netPnl.textContent = formatMoney(netPnl);
  }

  function render() {
    ui.balance.textContent = formatMoney(state.balance);
    ui.botStatus.textContent = state.running ? "Paper Bot Online" : "Paper Bot Offline";
    ui.botStatus.classList.toggle("live", state.running);
    ui.toggleBot.textContent = state.running ? "Stop Bot" : "Start Bot";
    ui.connectorName.textContent = state.connector;
    renderStats();
    renderTickers();
    renderConnectors();
    renderLogs();
  }

  ui.deposit.addEventListener("click", function () {
    updateWallet(Number(ui.amount.value), "Deposited");
  });

  ui.withdraw.addEventListener("click", function () {
    updateWallet(-Number(ui.amount.value), "Withdrew");
  });

  ui.toggleBot.addEventListener("click", toggleBot);

  if (shouldAutoStart && !state.running) {
    toggleBot();
  } else if (state.running) {
    timerId = window.setInterval(tickMarket, 2200);
  }

  render();
})();
