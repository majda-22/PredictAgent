const icons = {
  alert: "M12 9v4m0 4h.01M10.3 3.5 1.4 2.4A2 2 0 0 0 .7 8v8a2 2 0 0 0 2 2h17.2a2 2 0 0 0 1.7-3L13.7 5.9a2 2 0 0 0-3.4 0Z",
  antenna: "M12 19v-7m-3 7h6M8 7a5 5 0 0 1 8 0M5 4a9 9 0 0 1 14 0",
  bell: "M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4",
  bolt: "m13 2-8 12h6l-2 8 8-12h-6l2-8Z",
  brain: "M9 3a3 3 0 0 0-3 3v1a3 3 0 0 0 0 6v1a3 3 0 0 0 3 3m6-14a3 3 0 0 1 3 3v1a3 3 0 0 1 0 6v1a3 3 0 0 1-3 3M9 3v18m6-18v18M7 9h4m2 0h4M7 15h4m2 0h4",
  chart: "M4 19V5m6 14V9m6 10V3M3 19h18",
  check: "M20 6 9 17l-5-5",
  grid: "M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z",
  hand: "M8 13V7a2 2 0 1 1 4 0v5M12 7a2 2 0 1 1 4 0v6M16 9a2 2 0 1 1 4 0v5a7 7 0 0 1-7 7h-2a7 7 0 0 1-7-7v-2a2 2 0 1 1 4 0v1",
  layers: "m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  network: "M12 3v6m0 0-6 4m6-4 6 4M6 13v6m12-6v6M4 21h4m8 0h4m-6-12h-4",
  play: "m8 5 11 7-11 7V5Z",
  reset: "M3 12a9 9 0 1 0 3-6.7M3 4v6h6",
  robot: "M12 8V4m-5 8h10v7H7v-7Zm-2 3h.01M14 11h.01M9 19v2m6-2v2M5 14H3m18 0h-2",
  search: "M10 18a8 8 0 1 1 5.7-2.3L21 21",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8-3a8 8 0 0 0-.1-1l2-1.5-2-3.5-2.4 1a7 7 0 0 0-1.7-1L15.5 3h-7L8.2 6a7 7 0 0 0-1.7 1L4 6 2 9.5 4 11a8 8 0 0 0 0 2l-2 1.5L4 18l2.5-1a7 7 0 0 0 1.7 1l.3 3h7l.3-3a7 7 0 0 0 1.7-1l2.5 1 2-3.5-2-1.5c.1-.3.1-.7.1-1Z",
  signal: "M4 12a8 8 0 0 1 16 0M8 12a4 4 0 0 1 8 0m-4 4h.01",
  sliders: "M4 7h16M4 17h16M8 3v8m8 2v8",
  spark: "M13 2 9 10 2 13l7 3 4 8 4-8 7-3-7-3-4-8Z",
  stop: "M8 8h8v8H8z",
  sun: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.7-5.7 1.4-1.4M4.9 19.1l1.4-1.4m0-11.4L4.9 4.9m14.2 14.2-1.4-1.4M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
  thermo: "M14 14.8V5a2 2 0 1 0-4 0v9.8a4 4 0 1 0 4 0ZM14 5h4m-4 4h3",
  user: "M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
  video: "M4 6h12v12H4zM16 10l5-3v10l-5-3",
  wave: "M3 8c3-4 6 4 9 0s6 4 9 0M3 14c3-4 6 4 9 0s6 4 9 0",
  wrench: "M14.7 6.3a4 4 0 0 0-5 5L3 18l3 3 6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-2.6-2.6 2-2.8Z",
  zap: "m13 2-8 12h6l-2 8 8-12h-6l2-8Z",
};

const titles = {
  dashboard: "Dashboard Overview",
  alerts: "Alerts & Events",
  analytics: "Behavior Analytics",
  insights: "Maintenance Insights",
  control: "System Control",
  settings: "System Configuration",
};

const state = {
  dashboard: null,
  eventFilter: "ALL",
  search: "",
  settings: null,
};

function renderIcons() {
  document.querySelectorAll("[data-icon]").forEach((node) => {
    const path = icons[node.dataset.icon];
    if (!path) return;
    node.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`;
  });
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function setWidth(id, value) {
  const node = document.getElementById(id);
  if (node) node.style.width = `${Math.max(0, Math.min(100, value))}%`;
}

function setPage(page) {
  document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.id === page));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.page === page));
  setText("top-title", titles[page]);
  document.getElementById("search-input").placeholder = page === "settings" ? "Search parameters..." : `Search ${page === "dashboard" ? "telemetry" : page}...`;
  drawDashboard();
}

function cssVar(name) {
  return getComputedStyle(document.querySelector(".app-shell")).getPropertyValue(name).trim();
}

function scale(value, min, max, height, padding) {
  if (max <= min) return height / 2;
  const normalized = (value - min) / (max - min);
  return height - padding - normalized * (height - padding * 2);
}

function prepareCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

function drawGrid(ctx, width, height) {
  ctx.strokeStyle = cssVar("--border");
  ctx.globalAlpha = 0.32;
  ctx.lineWidth = 1;
  for (let i = 1; i <= 3; i += 1) {
    const y = (height / 4) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawBarChart(id, values) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const { ctx, width, height } = prepareCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  const data = values.length ? values : [0];
  const max = Math.max(...data, 1);
  const gap = 8;
  const barWidth = Math.max(6, (width - gap * (data.length - 1)) / data.length);
  data.forEach((value, index) => {
    const x = index * (barWidth + gap);
    const barHeight = Math.max(4, (value / max) * (height - 24));
    const gradient = ctx.createLinearGradient(0, height - barHeight, 0, height);
    gradient.addColorStop(0, cssVar("--accent"));
    gradient.addColorStop(1, "#655b7c");
    ctx.fillStyle = gradient;
    ctx.fillRect(x, height - barHeight, barWidth, barHeight);
  });
}

function drawLineChart(id, series, configs) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const { ctx, width, height } = prepareCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  const values = configs.flatMap((config) => series.map(config.value)).filter((value) => Number.isFinite(value));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const paddedMin = min === max ? min - 1 : min;
  const paddedMax = min === max ? max + 1 : max;

  configs.forEach((config) => {
    const data = series.map(config.value).filter((value) => Number.isFinite(value));
    if (data.length < 2) return;
    ctx.beginPath();
    data.forEach((value, index) => {
      const x = (width / (data.length - 1)) * index;
      const y = scale(value, paddedMin, paddedMax, height, 14);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = config.color;
    ctx.lineWidth = config.width || 3;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
  });
}

function drawDecisionChart(id, counts) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const { ctx, width, height } = prepareCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  const items = Object.entries(counts || {});
  const labels = ["NORMAL", "MONITOR", "WARNING", "MAINTENANCE_ALERT", "EMERGENCY_STOP"];
  const values = labels.map((label) => counts?.[label] || 0);
  const max = Math.max(...values, 1);
  const gap = 12;
  const barWidth = Math.max(24, (width - gap * (labels.length - 1)) / labels.length);
  labels.forEach((label, index) => {
    const value = counts?.[label] || 0;
    const h = Math.max(3, (value / max) * (height - 42));
    const x = index * (barWidth + gap);
    ctx.fillStyle = label === "NORMAL" || label === "MONITOR" ? cssVar("--accent") : cssVar("--accent-strong");
    ctx.fillRect(x, height - h - 22, barWidth, h);
    ctx.fillStyle = cssVar("--muted");
    ctx.font = "11px sans-serif";
    ctx.fillText(label.replace("_ALERT", "").slice(0, 8), x, height - 4);
  });
  if (!items.length) {
    ctx.fillStyle = cssVar("--muted");
    ctx.fillText("Waiting for stream data", 12, 24);
  }
}

function drawScatter(id, series) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const { ctx, width, height } = prepareCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  const data = series.filter((item) => item.temperature && item.current);
  if (!data.length) return;
  const temps = data.map((item) => item.temperature);
  const currents = data.map((item) => item.current);
  const minT = Math.min(...temps);
  const maxT = Math.max(...temps);
  const minC = Math.min(...currents);
  const maxC = Math.max(...currents);
  data.forEach((item) => {
    const x = 14 + ((item.current - minC) / Math.max(1e-6, maxC - minC)) * (width - 28);
    const y = scale(item.temperature, minT, maxT, height, 14);
    ctx.fillStyle = item.decision === "EMERGENCY_STOP" ? cssVar("--danger") : cssVar("--accent");
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });
  setText("correlation-value", correlation(temps, currents).toFixed(2));
}

function correlation(a, b) {
  if (a.length < 2 || b.length < 2) return 0;
  const meanA = a.reduce((sum, value) => sum + value, 0) / a.length;
  const meanB = b.reduce((sum, value) => sum + value, 0) / b.length;
  let numerator = 0;
  let denomA = 0;
  let denomB = 0;
  a.forEach((value, index) => {
    const da = value - meanA;
    const db = b[index] - meanB;
    numerator += da * db;
    denomA += da * da;
    denomB += db * db;
  });
  return numerator / Math.sqrt(Math.max(1e-9, denomA * denomB));
}

function renderEvents(events) {
  const body = document.getElementById("events-body");
  if (!body) return;
  body.innerHTML = "";
  const filtered = state.eventFilter === "ALL"
    ? events
    : events.filter((event) => event.decision === state.eventFilter);
  const searched = state.search
    ? filtered.filter((event) => {
        const haystack = `${event.time} ${event.decision} ${event.reason} ${event.command}`.toLowerCase();
        return haystack.includes(state.search);
      })
    : filtered;
  searched.slice(0, 8).forEach((event) => {
    const kind = event.decision === "EMERGENCY_STOP" ? "red" : event.decision === "MAINTENANCE_ALERT" || event.decision === "WARNING" ? "amber" : "green";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${event.time || "--"}</td>
      <td><b class="${kind}">${event.score_display.toFixed(2)}</b><span class="score ${kind}bar"></span></td>
      <td><span class="tag ${kind}tag">${event.decision}</span></td>
      <td>${event.reason || "No reason recorded"}</td>
      <td><code>${event.command || "NO_ACTION"}</code></td>
      <td>...</td>
    `;
    body.appendChild(row);
  });
  setText("events-footer", `Showing ${Math.min(searched.length, 8)} live entries`);
}

function renderMetrics(payload) {
  const latest = payload.latest || {};
  setText("metric-temperature", `${latest.temperature.toFixed(1)}C`);
  setText("metric-current", `${latest.current.toFixed(1)}A`);
  setText("metric-voltage", `${latest.voltage.toFixed(0)}V`);
  setText("metric-vibration", latest.vibration.toFixed(2));
  setWidth("meter-temperature", (latest.temperature / 100) * 100);
  setWidth("meter-current", (latest.current / 30) * 100);
  setWidth("meter-voltage", (latest.voltage / 260) * 100);
  setWidth("meter-vibration", (latest.vibration / 8) * 100);
  setText("latest-decision", latest.decision || "Waiting for stream");
  setText("latest-reason", latest.reason || "No reason recorded.");
  setText("latest-time", `Analysed: ${latest.timestamp || "--"}`);
  setText("stream-vibration", `${latest.vibration.toFixed(2)} mm/s`);
  setText("stream-temperature", `${latest.temperature.toFixed(1)}C`);
  setText("stream-stability", `${Math.max(0, 100 - latest.score_display * 25).toFixed(1)}%`);
  setText("critical-count", payload.counts.critical.toLocaleString());
  setText("maintenance-count", payload.counts.maintenance.toLocaleString());
  setText("successful-count", payload.counts.successful.toLocaleString());
  setText("maintenance-prediction", `${payload.prediction.message} Estimated maintenance window: ${payload.prediction.hours_to_maintenance} operational hours.`);
  document.querySelectorAll(".health-pill").forEach((node) => {
    node.lastChild.textContent = ` System Health: ${payload.health}`;
  });
}

function drawDashboard() {
  if (!state.dashboard) return;
  const series = state.dashboard.series || [];
  drawBarChart("temperature-chart", series.slice(-24).map((item) => item.temperature));
  drawLineChart("vibration-chart", series.slice(-50), [
    { value: (item) => item.vibration, color: cssVar("--accent"), width: 4 },
    { value: (item) => item.current, color: cssVar("--green"), width: 3 },
  ]);
  drawLineChart("score-chart", series.slice(-50), [
    { value: (item) => item.score_display, color: cssVar("--green"), width: 3 },
  ]);
  drawDecisionChart("decision-chart", state.dashboard.counts.by_decision);
  drawScatter("correlation-chart", series);
}

async function refreshDashboard() {
  try {
    const response = await fetch("/api/dashboard?limit=120");
    if (!response.ok) throw new Error(`Dashboard request failed: ${response.status}`);
    state.dashboard = await response.json();
    renderMetrics(state.dashboard);
    renderEvents(state.dashboard.events || []);
    drawDashboard();
  } catch (error) {
    setText("latest-reason", "Dashboard API is unavailable. Start the FastAPI server and stream sensor rows.");
  }
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) throw new Error(`Settings request failed: ${response.status}`);
    state.settings = await response.json();
    renderSettings(state.settings);
  } catch (error) {
    setText("settings-status", "Settings API unavailable.");
  }
}

function renderSettings(settings) {
  document.getElementById("temp-setting").value = settings.temperature_alert_sensitivity;
  document.getElementById("vib-setting").value = Math.round(settings.vibration_tolerance * 10);
  document.getElementById("autopilot-toggle").checked = Boolean(settings.alert_mode);
  document.getElementById("alert-mode-toggle").checked = Boolean(settings.alert_mode);
  document.getElementById("mqtt-setting").value = settings.mqtt_broker_url;
  document.getElementById("client-setting").value = settings.client_identity;
  document.getElementById("email-setting").value = settings.email_destination;
  document.getElementById("telegram-setting").value = settings.telegram_chat_id;
  updateSettingLabels();
}

function updateSettingLabels() {
  setText("temp-setting-value", `${document.getElementById("temp-setting").value}C`);
  setText("vib-setting-value", (document.getElementById("vib-setting").value / 10).toFixed(1));
}

async function saveSettings() {
  const payload = {
    temperature_alert_sensitivity: Number(document.getElementById("temp-setting").value),
    vibration_tolerance: Number(document.getElementById("vib-setting").value) / 10,
    alert_mode: document.getElementById("alert-mode-toggle").checked,
    mqtt_broker_url: document.getElementById("mqtt-setting").value,
    client_identity: document.getElementById("client-setting").value,
    email_destination: document.getElementById("email-setting").value,
    telegram_chat_id: document.getElementById("telegram-setting").value,
  };
  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Save failed: ${response.status}`);
    const data = await response.json();
    state.settings = data.settings;
    setText("settings-status", "Configuration saved just now.");
  } catch (error) {
    setText("settings-status", "Could not save configuration.");
  }
}

async function askAgent(question) {
  const output = document.getElementById("chat-output");
  output.textContent = "Thinking through recent motor events...";
  try {
    const response = await fetch("/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    const data = await response.json();
    output.textContent = data.answer;
  } catch (error) {
    output.textContent = "The API is not available yet. Start the FastAPI server to enable live agent chat.";
  }
}

async function sendCommand(command) {
  try {
    const response = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    });
    if (!response.ok) throw new Error(`Command failed: ${response.status}`);
    setText("settings-status", `Command sent: ${command}`);
    refreshDashboard();
  } catch (error) {
    setText("settings-status", `Command failed: ${command}`);
  }
}

async function runManualPrediction(event) {
  event.preventDefault();
  const resultNode = document.getElementById("manual-result");
  resultNode.className = "manual-result";
  resultNode.innerHTML = "<b>Analysing motor state...</b><span>Running manual prediction.</span>";

  const payload = {
    timestamp: new Date().toISOString(),
    temperature: Number(document.getElementById("manual-temperature").value),
    current: Number(document.getElementById("manual-current").value),
    voltage: Number(document.getElementById("manual-voltage").value),
    vibration: Number(document.getElementById("manual-vibration").value),
    speed_rpm: Number(document.getElementById("manual-speed").value),
    ambient_temperature: Number(document.getElementById("manual-ambient").value),
  };

  try {
    const response = await fetch("/predict-manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Manual prediction failed: ${response.status}`);
    const data = await response.json();
    const className = data.decision === "EMERGENCY_STOP"
      ? "manual-result danger"
      : data.decision === "MAINTENANCE_ALERT" || data.decision === "WARNING"
        ? "manual-result warn"
        : "manual-result";
    resultNode.className = className;
    resultNode.innerHTML = `
      <b>${data.decision}</b>
      <span>Score ${Number(data.score).toFixed(5)} / threshold ${Number(data.threshold).toFixed(5)} - command ${data.command}</span>
      <span>${data.reason}</span>
      <span>Regime ${data.regime}${data.sub_regime !== null ? `.${data.sub_regime}` : ""}. Manual test only: no MQTT command was published.</span>
    `;
  } catch (error) {
    resultNode.className = "manual-result danger";
    resultNode.innerHTML = "<b>Prediction unavailable</b><span>Start the FastAPI server and try again.</span>";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderIcons();
  const savedTheme = localStorage.getItem("predictagent-theme") || "dark";
  document.querySelector(".app-shell").dataset.theme = savedTheme;

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => setPage(button.dataset.page));
  });

  document.getElementById("view-details-btn").addEventListener("click", () => setPage("insights"));
  document.getElementById("deep-dive-btn").addEventListener("click", () => setPage("analytics"));
  document.getElementById("profile-btn").addEventListener("click", () => setPage("settings"));
  document.getElementById("refresh-stream-btn").addEventListener("click", refreshDashboard);
  document.getElementById("search-input").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderEvents(state.dashboard?.events || []);
  });
  document.getElementById("export-csv-btn").addEventListener("click", () => {
    window.location.href = "/api/events.csv";
  });
  document.getElementById("export-excel-btn").addEventListener("click", () => {
    window.location.href = "/api/events.xlsx";
  });
  document.getElementById("export-pdf-btn").addEventListener("click", () => {
    window.location.href = "/api/events.pdf";
  });
  document.getElementById("apply-filters-btn").addEventListener("click", () => {
    state.eventFilter = document.getElementById("decision-filter").value;
    renderEvents(state.dashboard?.events || []);
  });
  document.querySelectorAll(".schedule-btn").forEach((button) => {
    button.addEventListener("click", () => {
      setPage("control");
      setText("settings-status", "Maintenance scheduling request staged.");
    });
  });
  document.getElementById("dismiss-insight-btn").addEventListener("click", () => {
    document.getElementById("chat-output").textContent = "Insight dismissed. The live stream remains active.";
  });
  document.getElementById("temp-setting").addEventListener("input", updateSettingLabels);
  document.getElementById("vib-setting").addEventListener("input", updateSettingLabels);
  document.getElementById("alert-mode-toggle").addEventListener("change", () => {
    document.getElementById("autopilot-toggle").checked = document.getElementById("alert-mode-toggle").checked;
  });
  document.getElementById("autopilot-toggle").addEventListener("change", () => {
    document.getElementById("alert-mode-toggle").checked = document.getElementById("autopilot-toggle").checked;
  });
  document.getElementById("save-settings-btn").addEventListener("click", saveSettings);
  document.getElementById("discard-settings-btn").addEventListener("click", () => {
    if (state.settings) renderSettings(state.settings);
    setText("settings-status", "Unsaved changes discarded.");
  });

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const shell = document.querySelector(".app-shell");
    const next = shell.dataset.theme === "dark" ? "light" : "dark";
    shell.dataset.theme = next;
    localStorage.setItem("predictagent-theme", next);
    drawDashboard();
  });

  document.getElementById("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("chat-question");
    const question = input.value.trim();
    if (!question) return;
    askAgent(question);
    input.value = "";
  });

  document.querySelectorAll(".command").forEach((button) => {
    button.addEventListener("click", () => sendCommand(button.dataset.command));
  });
  document.getElementById("manual-predict-form").addEventListener("submit", runManualPrediction);

  window.addEventListener("resize", drawDashboard);
  loadSettings();
  refreshDashboard();
  setInterval(refreshDashboard, 2500);
});
