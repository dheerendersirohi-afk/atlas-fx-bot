(function () {
  const stateKey = "atlas-fx-bot-state";
  const backendUrlKey = "atlas-fx-backend-url";
  const initialState = {
    connector: "Universal Paper Bridge",
    running: false,
    balance: 10000,
    pairs: {
      "EUR/USD": {
        price: 1.0862,
        history: [1.0798, 1.0806, 1.0811, 1.0804, 1.0819, 1.0827, 1.0835, 1.0828, 1.0837, 1.0844, 1.0849, 1.0853, 1.0858, 1.0860, 1.0862]
      },
      "GBP/USD": {
        price: 1.2715,
        history: [1.2644, 1.2651, 1.2663, 1.2670, 1.2668, 1.2679, 1.2688, 1.2695, 1.2691, 1.2700, 1.2704, 1.2709, 1.2711, 1.2713, 1.2715]
      },
      "USD/JPY": {
        price: 153.24,
        history: [151.82, 151.96, 152.08, 152.17, 152.31, 152.44, 152.59, 152.71, 152.84, 152.98, 153.04, 153.11, 153.17, 153.21, 153.24]
      }
    },
    chartListener: {
      mode: "all",
      pair: "EUR/USD"
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
    backendBadge: document.getElementById("backendBadge"),
    backendHeadline: document.getElementById("backendHeadline"),
    connectorName: document.getElementById("connectorName"),
    connectorCount: document.getElementById("connectorCount"),
    pairCount: document.getElementById("pairCount"),
    pendingApprovals: document.getElementById("pendingApprovals"),
    heroStatusNote: document.getElementById("heroStatusNote"),
    deskMode: document.getElementById("deskMode"),
    deskEngine: document.getElementById("deskEngine"),
    deskRisk: document.getElementById("deskRisk"),
    deskBridge: document.getElementById("deskBridge"),
    openTrades: document.getElementById("openTrades"),
    closedTrades: document.getElementById("closedTrades"),
    winRate: document.getElementById("winRate"),
    netPnl: document.getElementById("netPnl"),
    tickerList: document.getElementById("tickerList"),
    connectorList: document.getElementById("connectorList"),
    chartMode: document.getElementById("chartMode"),
    chartPair: document.getElementById("chartPair"),
    analyzeChart: document.getElementById("analyzeChart"),
    chartCanvas: document.getElementById("chartCanvas"),
    chartSummary: document.getElementById("chartSummary"),
    chartMeta: document.getElementById("chartMeta"),
    chartDecision: document.getElementById("chartDecision"),
    brainStatus: document.getElementById("brainStatus"),
    positionList: document.getElementById("positionList"),
    activityLog: document.getElementById("activityLog"),
    backendUrl: document.getElementById("backendUrl"),
    checkBackend: document.getElementById("checkBackend"),
    submitSignal: document.getElementById("submitSignal"),
    backendStatus: document.getElementById("backendStatus")
  };

  const storage = createStorage();
  let state = loadState();
  let timerId = null;
  const shouldAutoStart = window.location.hash === "#start";
  let backendSnapshot = {
    status: "unknown",
    details: "Not checked yet.",
    blocker: "",
    pendingApprovals: 0,
    mt5Ready: false,
    manualApproval: true,
    brains: ["rules"],
    brainSystem: null
  };
  let chartAnalysis = {
    status: "idle",
    message: "Run chart analysis to get the current buy, sell, or hold call."
  };

  if (Object.values(ui).some((element) => !element)) {
    throw new Error("Atlas FX Bot UI failed to initialize because required elements are missing.");
  }

  function cloneInitialState() {
    return JSON.parse(JSON.stringify(initialState));
  }

  function createStorage() {
    let memoryState = null;
    let memoryBackendUrl = null;

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
        },
        getBackendUrl() {
          return window.localStorage.getItem(backendUrlKey);
        },
        setBackendUrl(value) {
          window.localStorage.setItem(backendUrlKey, value);
        }
      };
    } catch (_error) {
      return {
        get() {
          return memoryState;
        },
        set(value) {
          memoryState = value;
        },
        getBackendUrl() {
          return memoryBackendUrl;
        },
        setBackendUrl(value) {
          memoryBackendUrl = value;
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
        ? candidate.history.filter(isFiniteNumber).slice(-15)
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

  function normalizeChartListener(input, pairs) {
    const fallback = cloneInitialState().chartListener;
    const availablePairs = Object.keys(pairs || cloneInitialState().pairs);
    const pair = input && typeof input.pair === "string" && availablePairs.includes(input.pair)
      ? input.pair
      : availablePairs[0] || fallback.pair;
    const mode = input && input.mode === "pair" ? "pair" : "all";
    return { mode, pair };
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
      .slice(0, 14);

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
      chartListener: normalizeChartListener(rawState.chartListener, normalizePairMap(rawState.pairs)),
      openPositions: Array.isArray(rawState.openPositions)
        ? rawState.openPositions.map(normalizePosition).filter(Boolean).slice(0, 4)
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

  function loadBackendUrl() {
    return storage.getBackendUrl ? storage.getBackendUrl() : null;
  }

  function saveBackendUrl(url) {
    if (storage.setBackendUrl) {
      storage.setBackendUrl(url);
    }
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2
    }).format(value);
  }

  function formatNumber(value, digits) {
    return Number(value).toFixed(digits);
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
    state.logs = state.logs.slice(0, 14);
  }

  function average(values) {
    return values.reduce((total, value) => total + value, 0) / values.length;
  }

  function signalClass(signal) {
    return signal ? signal.toLowerCase() : "wait";
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

  function createSignalChip(signal) {
    const label = signal || "WAIT";
    const chip = document.createElement("span");
    chip.className = `signal-chip ${signalClass(label)}`;
    chip.textContent = label;
    return chip;
  }

  function sparklineFromHistory(history) {
    const bars = "._-~=*#";
    const min = Math.min(...history);
    const max = Math.max(...history);
    if (max === min) {
      return bars[2].repeat(history.length);
    }

    return history
      .map((value) => {
        const index = Math.max(
          0,
          Math.min(bars.length - 1, Math.round(((value - min) / (max - min)) * (bars.length - 1)))
        );
        return bars[index];
      })
      .join("");
  }

  function getChartLabels(count) {
    const labels = [];
    for (let index = count - 1; index >= 0; index -= 1) {
      const day = new Date();
      day.setDate(day.getDate() - index);
      labels.push(day.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
    }
    return labels;
  }

  function buildAllMarketSeries() {
    const pairHistories = Object.values(state.pairs)
      .map((pair) => pair.history.slice(-15))
      .filter((history) => history.length);

    if (!pairHistories.length) {
      return [];
    }

    const length = Math.min(...pairHistories.map((history) => history.length));
    return Array.from({ length }, function (_value, index) {
      const normalizedValues = pairHistories.map(function (history) {
        const trimmed = history.slice(-length);
        const base = trimmed[0] || 1;
        return ((trimmed[index] - base) / base) * 100;
      });
      return normalizedValues.reduce(function (total, value) {
        return total + value;
      }, 0) / normalizedValues.length;
    });
  }

  function buildChartModel() {
    const mode = state.chartListener.mode;
    const pair = state.chartListener.pair in state.pairs ? state.chartListener.pair : Object.keys(state.pairs)[0];
    const labels = getChartLabels(15);

    if (mode === "pair" && pair) {
      const history = state.pairs[pair].history.slice(-15);
      const first = history[0] || 0;
      const last = history[history.length - 1] || 0;
      const changePct = first ? ((last - first) / first) * 100 : 0;
      return {
        title: `${pair} listener`,
        summary: `${pair} moved ${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}% over the last 15 days.`,
        meta: `Scope: particular symbol. Current price: ${pair === "USD/JPY" ? formatNumber(last, 3) : formatNumber(last, 5)}. Signal: ${calculateSignal(history) || "WAIT"}.`,
        values: history,
        labels,
        formatter: function (value) {
          return pair === "USD/JPY" ? formatNumber(value, 3) : formatNumber(value, 5);
        }
      };
    }

    const values = buildAllMarketSeries();
    const last = values[values.length - 1] || 0;
    return {
      title: "All tracked markets",
      summary: `The combined listener is showing ${last >= 0 ? "positive" : "negative"} 15-day momentum across ${Object.keys(state.pairs).length} tracked pairs.`,
      meta: `Scope: all tracked markets. Aggregate move: ${last >= 0 ? "+" : ""}${last.toFixed(2)}%. Trade listener follows the same 15-day desk window used by the simulator.`,
      values,
      labels,
      formatter: function (value) {
        return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
      }
    };
  }

  function createChartSvg(values, labels, formatter) {
    const svgNs = "http://www.w3.org/2000/svg";
    const width = 640;
    const height = 220;
    const padding = { top: 18, right: 22, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const yTicks = 4;

    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "chart-svg");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "15 day chart listener");

    const defs = document.createElementNS(svgNs, "defs");
    const gradient = document.createElementNS(svgNs, "linearGradient");
    gradient.setAttribute("id", "chartGradient");
    gradient.setAttribute("x1", "0");
    gradient.setAttribute("x2", "0");
    gradient.setAttribute("y1", "0");
    gradient.setAttribute("y2", "1");

    const startStop = document.createElementNS(svgNs, "stop");
    startStop.setAttribute("offset", "0%");
    startStop.setAttribute("stop-color", "#6fe8d2");
    startStop.setAttribute("stop-opacity", "0.52");
    const endStop = document.createElementNS(svgNs, "stop");
    endStop.setAttribute("offset", "100%");
    endStop.setAttribute("stop-color", "#6fe8d2");
    endStop.setAttribute("stop-opacity", "0");
    gradient.appendChild(startStop);
    gradient.appendChild(endStop);
    defs.appendChild(gradient);
    svg.appendChild(defs);

    for (let tick = 0; tick <= yTicks; tick += 1) {
      const ratio = tick / yTicks;
      const y = padding.top + chartHeight * ratio;
      const gridLine = document.createElementNS(svgNs, "line");
      gridLine.setAttribute("x1", String(padding.left));
      gridLine.setAttribute("x2", String(width - padding.right));
      gridLine.setAttribute("y1", String(y));
      gridLine.setAttribute("y2", String(y));
      gridLine.setAttribute("class", "chart-grid-line");
      svg.appendChild(gridLine);

      const value = max - span * ratio;
      const label = document.createElementNS(svgNs, "text");
      label.setAttribute("x", "6");
      label.setAttribute("y", String(y + 4));
      label.setAttribute("class", "chart-grid-text");
      label.textContent = formatter(value);
      svg.appendChild(label);
    }

    const points = values.map(function (value, index) {
      const x = padding.left + (chartWidth * index) / Math.max(values.length - 1, 1);
      const y = padding.top + ((max - value) / span) * chartHeight;
      return { x, y };
    });

    const area = document.createElementNS(svgNs, "path");
    area.setAttribute(
      "d",
      `M ${padding.left} ${height - padding.bottom} ${points.map(function (point) { return `L ${point.x} ${point.y}`; }).join(" ")} L ${points[points.length - 1].x} ${height - padding.bottom} Z`
    );
    area.setAttribute("class", "chart-area");
    svg.appendChild(area);

    const line = document.createElementNS(svgNs, "polyline");
    line.setAttribute(
      "points",
      points.map(function (point) {
        return `${point.x},${point.y}`;
      }).join(" ")
    );
    line.setAttribute("class", "chart-line");
    svg.appendChild(line);

    points.forEach(function (point, index) {
      if (index !== 0 && index !== points.length - 1 && index !== Math.floor(points.length / 2)) {
        return;
      }
      const dot = document.createElementNS(svgNs, "circle");
      dot.setAttribute("cx", String(point.x));
      dot.setAttribute("cy", String(point.y));
      dot.setAttribute("r", "4");
      dot.setAttribute("class", "chart-dot");
      svg.appendChild(dot);
    });

    [0, Math.floor(labels.length / 2), labels.length - 1].forEach(function (index) {
      const label = document.createElementNS(svgNs, "text");
      label.setAttribute("x", String(points[index].x));
      label.setAttribute("y", String(height - 8));
      label.setAttribute("text-anchor", index === 0 ? "start" : index === labels.length - 1 ? "end" : "middle");
      label.setAttribute("class", "chart-label-text");
      label.textContent = labels[index];
      svg.appendChild(label);
    });

    return svg;
  }

  function buildBackendSnapshotForPair(pair) {
    const market = state.pairs[pair];
    const history = market.history.slice(-15);
    const rawRsi = 50 + ((history[history.length - 1] - history[0]) / Math.max(history[0], 0.00001)) * 600;
    return {
      symbol: pair.replace("/", ""),
      bid: market.price - (pair === "USD/JPY" ? 0.01 : 0.0001),
      ask: market.price + (pair === "USD/JPY" ? 0.01 : 0.0001),
      spread_points: pair === "USD/JPY" ? 15 : 12,
      ema_fast: average(history.slice(-3)),
      ema_slow: average(history.slice(-5)),
      rsi: Math.max(1, Math.min(99, rawRsi)),
      source: "chart-listener"
    };
  }

  function buildAnalysisPayload() {
    if (state.chartListener.mode === "pair") {
      return buildBackendSnapshotForPair(state.chartListener.pair);
    }

    const pairs = Object.keys(state.pairs);
    const snapshots = pairs.map(buildBackendSnapshotForPair);
    const primary = snapshots[0];
    return {
      ...primary,
      symbol: "FX-BASKET",
      bid: snapshots.reduce((total, snapshot) => total + snapshot.bid, 0) / snapshots.length,
      ask: snapshots.reduce((total, snapshot) => total + snapshot.ask, 0) / snapshots.length,
      spread_points: Math.round(snapshots.reduce((total, snapshot) => total + snapshot.spread_points, 0) / snapshots.length),
      ema_fast: snapshots.reduce((total, snapshot) => total + snapshot.ema_fast, 0) / snapshots.length,
      ema_slow: snapshots.reduce((total, snapshot) => total + snapshot.ema_slow, 0) / snapshots.length,
      rsi: snapshots.reduce((total, snapshot) => total + snapshot.rsi, 0) / snapshots.length,
      source: "chart-listener-basket"
    };
  }

  async function analyzeChart() {
    const baseUrl = ui.backendUrl.value.trim().replace(/\/+$/, "");
    if (!baseUrl) {
      chartAnalysis = {
        status: "error",
        message: "Enter a backend URL before running chart analysis."
      };
      render();
      return;
    }

    chartAnalysis = {
      status: "loading",
      message: "Analyzing the active 15-day chart with the auto brain selector..."
    };
    render();

    try {
      const response = await fetch(`${baseUrl}/api/signal/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "auto",
          snapshot: buildAnalysisPayload()
        })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      const signal = result.signal;
      const reasons = Array.isArray(result.risk && result.risk.reasons) ? result.risk.reasons.join(", ") : "No risk note.";
      chartAnalysis = {
        status: signal.action.toLowerCase(),
        message: `Decision: ${signal.action} via ${result.selected_brain}. ${signal.reason} Risk gate: ${reasons}.`
      };
      addLog("system", `Chart analysis completed with ${signal.action} from ${result.selected_brain}.`);
    } catch (error) {
      chartAnalysis = {
        status: "error",
        message: `Chart analysis failed: ${error.message}`
      };
      addLog("system", "Chart analysis failed.");
    }

    saveState();
    render();
  }

  function emptyBackendSnapshot(status, details, blocker) {
    return {
      status,
      details,
      blocker,
      pendingApprovals: 0,
      mt5Ready: false,
      manualApproval: true,
      brains: ["rules"],
      brainSystem: null
    };
  }

  async function checkBackend() {
    const baseUrl = ui.backendUrl.value.trim().replace(/\/+$/, "");
    if (!baseUrl) {
      backendSnapshot = emptyBackendSnapshot("error", "Enter a backend URL first.", "Missing backend URL.");
      render();
      return;
    }

    saveBackendUrl(baseUrl);
    try {
      const response = await fetch(`${baseUrl}/api/status`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      const mt5Blocker = payload.mt5 && Array.isArray(payload.mt5.blockers) && payload.mt5.blockers.length
        ? payload.mt5.blockers[0]
        : "";
      const pendingApprovals = payload.store && Array.isArray(payload.store.pending_trades)
        ? payload.store.pending_trades.filter((trade) => trade.status === "pending").length
        : 0;

      backendSnapshot = {
        status: "online",
        details: `Brain route: ${payload.default_brain} | Active brains: ${(payload.brains || ["rules"]).join(", ")} | MT5 terminal detected: ${payload.mt5.terminal_exists} | Manual approval: ${payload.manual_approval}`,
        blocker: mt5Blocker,
        pendingApprovals,
        mt5Ready: Boolean(payload.mt5.terminal_exists && payload.mt5.package_available && payload.mt5.credentials_ready),
        manualApproval: Boolean(payload.manual_approval),
        brains: Array.isArray(payload.brains) ? payload.brains : ["rules"],
        brainSystem: payload.brain_system || null
      };
      addLog("system", "Backend connection successful.");
    } catch (error) {
      backendSnapshot = emptyBackendSnapshot(
        "offline",
        `Backend request failed: ${error.message}`,
        "Backend is unreachable."
      );
      addLog("system", "Backend connection failed.");
    }

    saveState();
    render();
  }

  async function submitSampleTrade() {
    const baseUrl = ui.backendUrl.value.trim().replace(/\/+$/, "");
    if (!baseUrl) {
      backendSnapshot = emptyBackendSnapshot("error", "Enter a backend URL first.", "Missing backend URL.");
      render();
      return;
    }

    const pair = Object.keys(state.pairs)[0];
    const market = state.pairs[pair];
    const payload = {
      provider: "auto",
      snapshot: {
        symbol: pair.replace("/", ""),
        bid: market.price - (pair === "USD/JPY" ? 0.01 : 0.0001),
        ask: market.price + (pair === "USD/JPY" ? 0.01 : 0.0001),
        spread_points: pair === "USD/JPY" ? 15 : 12,
        ema_fast: average(market.history.slice(-3)),
        ema_slow: average(market.history.slice(-5)),
        rsi: 48,
        source: "frontend-sample"
      }
    };

    saveBackendUrl(baseUrl);
    try {
      const response = await fetch(`${baseUrl}/api/trades/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      backendSnapshot.status = "online";
      if (result.evaluated) {
        const fallbackSummary = Array.isArray(result.evaluated.fallback_events) && result.evaluated.fallback_events.length
          ? ` Fallbacks: ${result.evaluated.fallback_events.map((event) => event.brain).join(", ")}.`
          : "";
        backendSnapshot.details = `Trade submit status: ${result.status} | Brain used: ${result.evaluated.selected_brain} | ${result.evaluated.selection_reason}${fallbackSummary}`;
        addLog(
          "system",
          `Backend trade submit result: ${result.status}. Brain: ${result.evaluated.selected_brain}.`
        );
      } else {
        backendSnapshot.details = `Trade submit status: ${result.status}`;
        addLog("system", `Backend trade submit result: ${result.status}.`);
      }
      await checkBackend();
    } catch (error) {
      backendSnapshot = {
        ...backendSnapshot,
        status: "offline",
        details: `Trade submit failed: ${error.message}`,
        blocker: backendSnapshot.blocker || "Trade submit failed."
      };
      addLog("system", "Backend trade submit failed.");
      saveState();
      render();
    }
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
    addLog("wallet", `${action} ${formatMoney(Math.abs(amountDelta))} in the local trading ledger.`);
    saveState();
    render();
  }

  function maybeOpenTrade(pair, data) {
    if (state.openPositions.length >= 4) {
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

      const hitStop = position.side === "BUY" ? price <= position.stop : price >= position.stop;
      const hitTarget = position.side === "BUY" ? price >= position.target : price <= position.target;

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

  function tickMarket() {
    Object.entries(state.pairs).forEach(([pair, data]) => {
      const direction = Math.random() - 0.48;
      const scale = pair === "USD/JPY" ? 0.08 : 0.0009;
      const nextPrice = Number((data.price + direction * scale).toFixed(pair === "USD/JPY" ? 3 : 5));
      data.price = nextPrice;
      data.history.push(nextPrice);
      data.history = data.history.slice(-15);

      maybeOpenTrade(pair, data);
      maybeCloseTrades(pair, data.price);
    });

    saveState();
    render();
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
      addLog("system", "Paper bot stopped.");
    }
    saveState();
    render();
  }

  function renderHero() {
    const connectors = Array.isArray(window.ATLAS_CONNECTORS) ? window.ATLAS_CONNECTORS : [];
    ui.connectorCount.textContent = String(connectors.length);
    ui.pairCount.textContent = String(Object.keys(state.pairs).length);
    ui.pendingApprovals.textContent = String(backendSnapshot.pendingApprovals);
    ui.connectorName.textContent = state.connector;

    ui.botStatus.textContent = state.running ? "Paper Bot Online" : "Paper Bot Offline";
    ui.botStatus.classList.toggle("live", state.running);
    ui.toggleBot.textContent = state.running ? "Stop Bot" : "Start Bot";

    ui.backendBadge.textContent = backendSnapshot.status === "online"
      ? backendSnapshot.mt5Ready
        ? "MT5 ready"
        : "Backend online"
      : backendSnapshot.status === "offline"
        ? "Backend offline"
        : "Backend unknown";

    ui.backendHeadline.textContent = backendSnapshot.status === "online"
      ? backendSnapshot.mt5Ready
        ? "Bridge can reach MT5"
        : "Bridge needs broker credentials"
      : "Backend not checked";

    ui.heroStatusNote.textContent = backendSnapshot.blocker
      ? backendSnapshot.blocker
      : state.running
        ? "Paper execution loop is active. Use the bridge panel to send sample trades into backend approval flow."
        : "Paper execution is idle. Start the bot or connect the backend to review MT5 bridge readiness.";

    ui.deskMode.textContent = state.running ? "Live simulation feed" : "Simulation desk";
    ui.deskEngine.textContent = backendSnapshot.brainSystem
      ? backendSnapshot.brainSystem.active_brains.join(", ")
      : backendSnapshot.brains.join(", ");
    ui.deskRisk.textContent = backendSnapshot.manualApproval ? "Manual approval" : "Auto execution";
    ui.deskBridge.textContent = backendSnapshot.mt5Ready ? "MT5 ready" : backendSnapshot.blocker || "Bridge pending";
  }

  function renderTickers() {
    ui.tickerList.innerHTML = "";
    Object.entries(state.pairs).forEach(([pair, data]) => {
      const signal = calculateSignal(data.history) || "WAIT";
      const row = document.createElement("div");
      row.className = "ticker-item";

      const left = document.createElement("div");
      left.className = "ticker-main";
      const copy = document.createElement("div");
      const pairLabel = document.createElement("strong");
      pairLabel.textContent = pair;
      const signalLabel = document.createElement("span");
      signalLabel.className = "ticker-meta";
      signalLabel.textContent = `EMA signal: ${signal}`;
      const sparkline = document.createElement("div");
      sparkline.className = "sparkline";
      sparkline.textContent = sparklineFromHistory(data.history);
      copy.appendChild(pairLabel);
      copy.appendChild(signalLabel);
      copy.appendChild(sparkline);
      left.appendChild(copy);

      const right = document.createElement("div");
      right.className = "ticker-price";
      const priceLabel = document.createElement("strong");
      priceLabel.textContent = pair === "USD/JPY" ? formatNumber(data.price, 3) : formatNumber(data.price, 5);
      const feedLabel = document.createElement("span");
      feedLabel.className = "ticker-meta";
      feedLabel.textContent = "Paper feed";
      right.appendChild(createSignalChip(signal));
      right.appendChild(priceLabel);
      right.appendChild(feedLabel);

      row.appendChild(left);
      row.appendChild(right);
      ui.tickerList.appendChild(row);
    });
  }

  function renderChartListener() {
    const pairs = Object.keys(state.pairs);
    if (!pairs.length) {
      ui.chartCanvas.textContent = "No market data available.";
      ui.chartSummary.textContent = "Chart listener is waiting for tracked instruments.";
      ui.chartMeta.textContent = "Add symbols to start the 15-day listener.";
      return;
    }

    if (!pairs.includes(state.chartListener.pair)) {
      state.chartListener.pair = pairs[0];
    }

    ui.chartPair.innerHTML = "";
    pairs.forEach(function (pair) {
      const option = document.createElement("option");
      option.value = pair;
      option.textContent = pair;
      ui.chartPair.appendChild(option);
    });

    ui.chartMode.value = state.chartListener.mode;
    ui.chartPair.value = state.chartListener.pair;
    ui.chartPair.disabled = state.chartListener.mode !== "pair";

    const chartModel = buildChartModel();
    ui.chartCanvas.innerHTML = "";
    ui.chartCanvas.appendChild(createChartSvg(chartModel.values, chartModel.labels, chartModel.formatter));
    ui.chartSummary.textContent = chartModel.summary;
    ui.chartMeta.textContent = chartModel.meta;
    ui.chartDecision.textContent = chartAnalysis.message;
  }

  function renderConnectors() {
    ui.connectorList.innerHTML = "";
    const connectors = Array.isArray(window.ATLAS_CONNECTORS) ? window.ATLAS_CONNECTORS : [];
    connectors.forEach((connector) => {
      const row = document.createElement("div");
      row.className = "connector-item";

      const head = document.createElement("div");
      head.className = "connector-head";
      const name = document.createElement("strong");
      name.textContent = connector.label;

      const tag = document.createElement("span");
      tag.className = `connector-tag ${connector.status === "active" ? "active" : "integration"}`;
      tag.textContent = connector.status === "active" ? "Active" : "Integration enabled";

      head.appendChild(name);
      head.appendChild(tag);

      const metaLine = document.createElement("div");
      metaLine.className = "connector-meta-line";

      const transport = document.createElement("span");
      transport.className = "connector-meta";
      transport.textContent = `Transport: ${connector.transport || "Unknown"}`;

      const auth = document.createElement("span");
      auth.className = "connector-meta";
      auth.textContent = `Auth: ${connector.auth || "Unknown"}`;

      const environments = document.createElement("span");
      environments.className = "connector-meta";
      environments.textContent = `Modes: ${(connector.environments || []).join(", ") || "Unknown"}`;

      const note = document.createElement("p");
      note.className = "connector-note";
      note.textContent = connector.note || "No connector note available.";

      metaLine.appendChild(transport);
      metaLine.appendChild(auth);
      metaLine.appendChild(environments);
      row.appendChild(head);
      row.appendChild(metaLine);
      row.appendChild(note);
      ui.connectorList.appendChild(row);
    });
  }

  function createBrainCard(title, tag, meta, tagClass) {
    const card = document.createElement("div");
    card.className = "brain-card";

    const head = document.createElement("div");
    head.className = "brain-head";
    const name = document.createElement("strong");
    name.textContent = title;
    const badge = document.createElement("span");
    badge.className = `brain-tag ${tagClass}`;
    badge.textContent = tag;
    head.appendChild(name);
    head.appendChild(badge);

    const body = document.createElement("div");
    body.className = "brain-meta";
    body.textContent = meta;

    card.appendChild(head);
    card.appendChild(body);
    return card;
  }

  function renderBrainStatus() {
    ui.brainStatus.innerHTML = "";
    const brainSystem = backendSnapshot.brainSystem;
    if (!brainSystem) {
      ui.brainStatus.appendChild(
        createBrainCard(
          "Brain system unavailable",
          "Unknown",
          "Connect the backend to inspect the rules engine, optional LLM adapters, and ML model state.",
          "idle"
        )
      );
      return;
    }

    ui.brainStatus.appendChild(
      createBrainCard(
        "Rules engine",
        "Active",
        `Signals: ${brainSystem.rules_engine.signals.join(", ")}.`,
        "live"
      )
    );

    (brainSystem.llm_adapters || []).forEach((adapter) => {
      const supportedModels = Array.isArray(adapter.supported_models) && adapter.supported_models.length
        ? ` Supported models: ${adapter.supported_models.join(", ")}.`
        : "";
      const meta = adapter.active
        ? `Model: ${adapter.model}. Adapter is configured and available in the backend.${supportedModels}`
        : `Model: ${adapter.model}. ${adapter.blocker || "Adapter is inactive."}${supportedModels}`;
      ui.brainStatus.appendChild(
        createBrainCard(
          `${adapter.name.toUpperCase()} adapter`,
          adapter.active ? "Online" : "Offline",
          meta,
          adapter.active ? "live" : "off"
        )
      );
    });

    ui.brainStatus.appendChild(
      createBrainCard(
        "ML model layer",
        brainSystem.ml_enabled ? "Online" : "Not added",
        brainSystem.ml_enabled
          ? (brainSystem.ml_models[0] && brainSystem.ml_models[0].note
              ? brainSystem.ml_models[0].note
              : "A local machine-learning style model is active for signal support.")
          : "No trained ML model is enabled right now. The project currently relies on deterministic rules and optional LLM adapters.",
        brainSystem.ml_enabled ? "live" : "off"
      )
    );
  }

  function renderPositions() {
    ui.positionList.innerHTML = "";
    if (!state.openPositions.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No open paper positions yet. Start the bot to generate simulated entries.";
      ui.positionList.appendChild(empty);
      return;
    }

    state.openPositions.forEach((position) => {
      const card = document.createElement("div");
      card.className = "position-card";

      const head = document.createElement("div");
      head.className = "position-head";
      const titleWrap = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `${position.pair} ${position.side}`;
      const time = document.createElement("span");
      time.className = "position-meta";
      time.textContent = `Opened ${formatTimestamp(position.openedAt)}`;
      titleWrap.appendChild(title);
      titleWrap.appendChild(time);
      head.appendChild(titleWrap);
      head.appendChild(createSignalChip(position.side));

      const grid = document.createElement("div");
      grid.className = "position-grid";
      [
        ["Units", position.units.toFixed(2)],
        ["Entry", position.entry.toFixed(position.pair === "USD/JPY" ? 3 : 5)],
        ["Target", position.target.toFixed(position.pair === "USD/JPY" ? 3 : 5)],
        ["Stop", position.stop.toFixed(position.pair === "USD/JPY" ? 3 : 5)]
      ].forEach(([label, value]) => {
        const item = document.createElement("div");
        item.className = "position-meta";
        const caption = document.createElement("span");
        caption.textContent = label;
        const strong = document.createElement("strong");
        strong.textContent = value;
        item.appendChild(caption);
        item.appendChild(strong);
        grid.appendChild(item);
      });

      card.appendChild(head);
      card.appendChild(grid);
      ui.positionList.appendChild(card);
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

  function renderBackendStatus() {
    ui.backendStatus.innerHTML = "";

    const items = [
      ["Connection", backendSnapshot.status],
      ["Brains", backendSnapshot.brains.join(", ")],
      ["Approvals", backendSnapshot.manualApproval ? "Manual approval enabled" : "Auto execution enabled"],
      ["Pending queue", String(backendSnapshot.pendingApprovals)]
    ];

    items.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "backend-item";
      const title = document.createElement("span");
      title.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      row.appendChild(title);
      row.appendChild(strong);
      ui.backendStatus.appendChild(row);
    });

    const summary = document.createElement("div");
    summary.className = "backend-item";
    const summaryLabel = document.createElement("span");
    summaryLabel.textContent = "Summary";
    const summaryText = document.createElement("p");
    summaryText.textContent = backendSnapshot.details;
    summary.appendChild(summaryLabel);
    summary.appendChild(summaryText);
    ui.backendStatus.appendChild(summary);

    if (backendSnapshot.blocker) {
      const blocker = document.createElement("div");
      blocker.className = "backend-item";
      const blockerLabel = document.createElement("span");
      blockerLabel.textContent = "Current blocker";
      const blockerText = document.createElement("p");
      blockerText.textContent = backendSnapshot.blocker;
      blocker.appendChild(blockerLabel);
      blocker.appendChild(blockerText);
      ui.backendStatus.appendChild(blocker);
    }
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
    ui.netPnl.style.color = netPnl < 0 ? "#ff8b97" : "#f2f6fb";
  }

  function render() {
    ui.balance.textContent = formatMoney(state.balance);
    renderHero();
    renderStats();
    renderTickers();
    renderChartListener();
    renderConnectors();
    renderBrainStatus();
    renderPositions();
    renderBackendStatus();
    renderLogs();
  }

  ui.deposit.addEventListener("click", function () {
    updateWallet(Number(ui.amount.value), "Deposited");
  });

  ui.withdraw.addEventListener("click", function () {
    updateWallet(-Number(ui.amount.value), "Withdrew");
  });

  ui.toggleBot.addEventListener("click", toggleBot);
  ui.chartMode.addEventListener("change", function () {
    state.chartListener.mode = ui.chartMode.value === "pair" ? "pair" : "all";
    saveState();
    render();
  });
  ui.chartPair.addEventListener("change", function () {
    state.chartListener.pair = ui.chartPair.value;
    saveState();
    render();
  });
  ui.analyzeChart.addEventListener("click", function () {
    void analyzeChart();
  });
  ui.checkBackend.addEventListener("click", function () {
    void checkBackend();
  });
  ui.submitSignal.addEventListener("click", function () {
    void submitSampleTrade();
  });

  const rememberedBackendUrl = loadBackendUrl();
  if (rememberedBackendUrl) {
    ui.backendUrl.value = rememberedBackendUrl;
  }

  if (shouldAutoStart && !state.running) {
    toggleBot();
  } else if (state.running) {
    timerId = window.setInterval(tickMarket, 2200);
  }

  render();
  void checkBackend();
})();
