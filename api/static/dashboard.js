/**
 * SMART TOMATO GREENHOUSE — LIVE TELEMETRY & AI DECISION DASHBOARD
 * Powered by Chart.js (with resilient Canvas fallback), real-time polling, and ESP32 active learning.
 */

// Global State
let chartInstance = null;
let currentChartMode = "multi"; // 'multi' | 'soil' | 'climate' | 'pressure'
let currentTimeWindow = 60;
let lastKnownRows = [];
let simDismissed = false;
let hwDismissed = false;
let staleDismissed = false;

// Helper: HTTP JSON fetcher
async function getJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error("Could not reach the greenhouse API service");
  return res.json();
}

// Helper: Number formatting
function fmt(value, digits = 1) {
  if (value === undefined || value === null || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : String(value);
}

// Helper: DOM text helper
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// Helper: Toggle hidden class
function setHidden(id, hidden) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden", hidden);
}

// Helper: Local time formatting
function localWhen(timestamp) {
  if (!timestamp) return "—";
  const d = new Date(timestamp);
  if (Number.isNaN(d.getTime())) return String(timestamp);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Helper: Relative time string
function ago(seconds) {
  if (seconds == null) return "Connecting…";
  if (seconds < 5) return "Just now";
  if (seconds < 60) return `Updated ${seconds}s ago`;
  const mins = Math.round(seconds / 60);
  if (mins === 1) return "Updated 1 min ago";
  if (mins < 60) return `Updated ${mins} mins ago`;
  return "Updated > 1h ago";
}

// Live Clock: NPT Kathmandu (+05:45)
function updateClock() {
  const clockEl = document.getElementById("local-clock");
  if (!clockEl) return;
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour12: false });
  clockEl.textContent = `${timeStr} Local`;
}
setInterval(updateClock, 1000);
updateClock();

/* ==========================================================================
   MINI SPARKLINES RENDERER (NATIVE CANVAS 2D)
   ========================================================================== */
function drawSparkline(canvasId, values, strokeColor, fillColor) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !values || values.length < 2) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.width;
  const h = canvas.clientHeight || canvas.height;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const cleanVals = values.slice(-20).map(Number).filter(Number.isFinite);
  if (cleanVals.length < 2) return;

  const min = Math.min(...cleanVals);
  const max = Math.max(...cleanVals);
  const range = max === min ? 1 : max - min;
  const pad = 4;

  const pts = cleanVals.map((v, i) => {
    const x = (i / (cleanVals.length - 1)) * (w - pad * 2) + pad;
    const y = h - ((v - min) / range) * (h - pad * 2) - pad;
    return { x, y };
  });

  // Area Fill
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(pts[i].x, pts[i].y);
  }
  ctx.lineTo(pts[pts.length - 1].x, h);
  ctx.lineTo(pts[0].x, h);
  ctx.closePath();

  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, fillColor || "rgba(16, 185, 129, 0.3)");
  grad.addColorStop(1, "rgba(16, 185, 129, 0.0)");
  ctx.fillStyle = grad;
  ctx.fill();

  // Line Stroke
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(pts[i].x, pts[i].y);
  }
  ctx.strokeStyle = strokeColor || "#10b981";
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke();
}

/* ==========================================================================
   PRIMARY TELEMETRY CHART (CHART.JS WITH FALLBACK)
   ========================================================================== */
function initOrUpdateChart(rows) {
  const overlay = document.getElementById("chart-empty-overlay");
  if (!rows || rows.length < 2) {
    if (overlay) overlay.style.display = "flex";
    return;
  }
  if (overlay) overlay.style.display = "none";

  const windowed = rows.slice(-currentTimeWindow);
  const labels = windowed.map((r) => localWhen(r.timestamp));
  const soilData = windowed.map((r) => Number(r.soilMoisture));
  const tempData = windowed.map((r) => Number(r.temperature));
  const humData = windowed.map((r) => Number(r.humidity));
  const presData = windowed.map((r) => Number(r.pressure));

  // If Chart.js CDN is present
  if (typeof Chart !== "undefined") {
    renderChartJs(labels, soilData, tempData, humData, presData);
  } else {
    renderCanvasFallback(soilData, tempData, humData);
  }

  // Update Mini Sparklines
  drawSparkline("spark-soil", soilData, "#34d399", "rgba(52, 211, 153, 0.25)");
  drawSparkline("spark-temp", tempData, "#fbbf24", "rgba(251, 191, 36, 0.25)");
  drawSparkline("spark-hum", humData, "#22d3ee", "rgba(34, 211, 238, 0.25)");
  drawSparkline("spark-pres", presData, "#818cf8", "rgba(129, 140, 248, 0.25)");
}

function renderChartJs(labels, soilData, tempData, humData, presData) {
  const canvas = document.getElementById("liveSensorChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // Gradients for area fills
  const soilGrad = ctx.createLinearGradient(0, 0, 0, 260);
  soilGrad.addColorStop(0, "rgba(52, 211, 153, 0.3)");
  soilGrad.addColorStop(1, "rgba(52, 211, 153, 0.0)");

  const tempGrad = ctx.createLinearGradient(0, 0, 0, 260);
  tempGrad.addColorStop(0, "rgba(251, 191, 36, 0.28)");
  tempGrad.addColorStop(1, "rgba(251, 191, 36, 0.0)");

  const humGrad = ctx.createLinearGradient(0, 0, 0, 260);
  humGrad.addColorStop(0, "rgba(34, 211, 238, 0.25)");
  humGrad.addColorStop(1, "rgba(34, 211, 238, 0.0)");

  const presGrad = ctx.createLinearGradient(0, 0, 0, 260);
  presGrad.addColorStop(0, "rgba(129, 140, 248, 0.25)");
  presGrad.addColorStop(1, "rgba(129, 140, 248, 0.0)");

  let datasets = [];
  let scales = {};

  if (currentChartMode === "multi") {
    datasets = [
      {
        label: "Soil Moisture (%)",
        data: soilData,
        borderColor: "#34d399",
        backgroundColor: soilGrad,
        fill: true,
        tension: 0.35,
        borderWidth: 2.2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: "#34d399",
        yAxisID: "yPct",
      },
      {
        label: "Temperature (°C)",
        data: tempData,
        borderColor: "#fbbf24",
        backgroundColor: "transparent",
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: "#fbbf24",
        yAxisID: "yTemp",
      },
      {
        label: "Humidity (%)",
        data: humData,
        borderColor: "#22d3ee",
        backgroundColor: "transparent",
        borderDash: [4, 4],
        tension: 0.35,
        borderWidth: 1.8,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: "#22d3ee",
        yAxisID: "yPct",
      },
    ];

    scales = {
      x: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" }, maxTicksLimit: 8 },
      },
      yPct: {
        type: "linear",
        position: "left",
        min: 0,
        max: 100,
        grid: { color: "rgba(255, 255, 255, 0.05)" },
        ticks: { color: "#34d399", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v}%` },
      },
      yTemp: {
        type: "linear",
        position: "right",
        min: 10,
        max: 45,
        grid: { display: false },
        ticks: { color: "#fbbf24", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v}°C` },
      },
    };
  } else if (currentChartMode === "soil") {
    datasets = [
      {
        label: "Soil Moisture (%)",
        data: soilData,
        borderColor: "#34d399",
        backgroundColor: soilGrad,
        fill: true,
        tension: 0.3,
        borderWidth: 2.8,
        pointRadius: 1,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: "#34d399",
      },
    ];
    scales = {
      x: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" }, maxTicksLimit: 8 },
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: "rgba(255, 255, 255, 0.06)" },
        ticks: { color: "#34d399", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v}%` },
      },
    };
  } else if (currentChartMode === "climate") {
    datasets = [
      {
        label: "Air Temperature (°C)",
        data: tempData,
        borderColor: "#fbbf24",
        backgroundColor: tempGrad,
        fill: true,
        tension: 0.35,
        borderWidth: 2.4,
        pointRadius: 0,
        pointHoverRadius: 5,
        yAxisID: "yTemp",
      },
      {
        label: "Humidity (%)",
        data: humData,
        borderColor: "#22d3ee",
        backgroundColor: humGrad,
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        yAxisID: "yHum",
      },
    ];
    scales = {
      x: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" }, maxTicksLimit: 8 },
      },
      yTemp: {
        type: "linear",
        position: "left",
        min: 10,
        max: 45,
        grid: { color: "rgba(255, 255, 255, 0.06)" },
        ticks: { color: "#fbbf24", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v}°C` },
      },
      yHum: {
        type: "linear",
        position: "right",
        min: 0,
        max: 100,
        grid: { display: false },
        ticks: { color: "#22d3ee", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v}%` },
      },
    };
  } else if (currentChartMode === "pressure") {
    datasets = [
      {
        label: "Atmospheric Pressure (hPa)",
        data: presData,
        borderColor: "#818cf8",
        backgroundColor: presGrad,
        fill: true,
        tension: 0.2,
        borderWidth: 2.5,
        pointRadius: 1,
        pointHoverRadius: 6,
      },
    ];
    const minP = Math.floor(Math.min(...presData.filter((v) => v > 0)) || 840) - 4;
    const maxP = Math.ceil(Math.max(...presData) || 870) + 4;
    scales = {
      x: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" }, maxTicksLimit: 8 },
      },
      y: {
        min: minP,
        max: maxP,
        grid: { color: "rgba(255, 255, 255, 0.06)" },
        ticks: { color: "#818cf8", font: { size: 10, family: "JetBrains Mono" }, callback: (v) => `${v} hPa` },
      },
    };
  }

  if (chartInstance) {
    chartInstance.data.labels = labels;
    chartInstance.data.datasets = datasets;
    chartInstance.options.scales = scales;
    chartInstance.update("none");
  } else {
    chartInstance = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(10, 15, 26, 0.95)",
            titleColor: "#f8fafc",
            bodyColor: "#cbd5e1",
            borderColor: "rgba(255, 255, 255, 0.15)",
            borderWidth: 1,
            padding: 10,
            cornerRadius: 8,
            titleFont: { family: "JetBrains Mono", size: 11 },
            bodyFont: { family: "Plus Jakarta Sans", size: 12 },
          },
        },
        scales,
      },
    });
  }
}

// Resilient Native Canvas Fallback (if CDN is unavailable)
function renderCanvasFallback(soilData) {
  const canvas = document.getElementById("liveSensorChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (soilData.length < 2) return;
  const pad = 30;
  ctx.beginPath();
  soilData.forEach((v, i) => {
    const x = pad + (i / (soilData.length - 1)) * (w - pad * 2);
    const y = h - pad - (v / 100) * (h - pad * 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#34d399";
  ctx.lineWidth = 2.5;
  ctx.stroke();
}

/* ==========================================================================
   REFRESH TELEMETRY DATA (3s INTERVAL)
   ========================================================================== */
async function refresh() {
  try {
    const [status, logs] = await Promise.all([
      getJson("/api/status"),
      getJson("/api/logs?limit=120"),
    ]);

    const latest = status.latest;
    const farmer = status.farmer;
    const live = Boolean(farmer && farmer.live);
    const isSimulated = Boolean(farmer && farmer.is_simulated);
    const deviceId = (latest && latest.device_id) || "unknown";

    // 0. Source status pill
    const sourcePill = document.getElementById("source-pill");
    if (sourcePill) {
      if (!latest) {
        sourcePill.className = "pill source-pill idle";
        setText("source-text", "Awaiting Device");
      } else if (isSimulated) {
        sourcePill.className = "pill source-pill sim";
        setText("source-text", "⚡ Simulator Mode");
      } else {
        sourcePill.className = "pill source-pill hw";
        setText("source-text", "🌱 Physical ESP32");
      }
    }

    // 1. Live status pill
    const livePill = document.getElementById("live-pill");
    if (livePill) {
      livePill.className = "pill status-pill " + (live ? "live" : latest ? "bad" : "");
      const pillText = livePill.querySelector(".pill-text");
      if (pillText) {
        pillText.textContent = live ? "Stream Active" : latest ? "No Recent Reading" : "Waiting for Sensors";
      }
    }

    // 2. Hardware / Simulator / Stale Banners
    if (isSimulated) {
      setText("sim-device-name", deviceId);
    } else {
      setText("hw-device-name", deviceId);
    }

    if (live) {
      staleDismissed = false;
      setHidden("sim-banner", !isSimulated || simDismissed);
      setHidden("hw-banner", isSimulated || hwDismissed);
      setHidden("stale-banner", true);
    } else {
      setHidden("sim-banner", true);
      setHidden("hw-banner", true);
      if (staleDismissed) {
        setHidden("stale-banner", true);
      } else {
        setHidden("stale-banner", false);
        if (isSimulated) {
          setText("stale-icon", "⚡");
          setText("stale-title", "Simulator Telemetry Standby");
          setText(
            "stale-desc",
            "Simulator stream is paused. Run python3 -m src.simulate_esp32 for continuous live streaming, or click Send Test Reading."
          );
        } else {
          setText("stale-icon", "📡");
          setText("stale-title", "Telemetry Standby (>90s since last packet)");
          setText(
            "stale-desc",
            "Awaiting live sensor readings. If using physical ESP32, verify it is powered on and connected to this Wi-Fi network."
          );
        }
      }
    }

    // 3. Pump pill & hero decision card
    const pumpPill = document.getElementById("pump-pill");
    const hero = document.getElementById("decision-banner");
    const pumpCard = document.getElementById("pump-card");
    const pumpBadge = document.getElementById("pump-status-badge");
    const relayPill = document.getElementById("relay-pill");

    if (latest && farmer) {
      const isPumpOn = farmer.pump_plain === "Running";

      if (pumpPill) {
        pumpPill.className = "pill pump-pill " + (isPumpOn ? "on" : "off");
        const pText = pumpPill.querySelector(".pill-text");
        if (pText) pText.textContent = isPumpOn ? "Pump Running" : "Pump Idle";
      }

      if (hero) {
        hero.className = "hero-decision " + (isPumpOn ? "water" : "wait");
      }

      setText("hero-label", live ? (isSimulated ? "Simulated Agronomic Decision" : "Live Hardware Decision") : "Last Stored Decision");
      setText("decision-text", farmer.headline);
      setText("decision-reason", farmer.reason);
      setText("updated-at", ago(farmer.age_seconds));

      // Sensor Card Values
      setText("v-soil", fmt(latest.soilMoisture, 1));
      setText("soil-plain", farmer.soil_plain);
      setText("v-temp", fmt(latest.temperature, 1));
      setText("temp-plain", farmer.temp_plain);
      setText("v-hum", fmt(latest.humidity, 1));
      setText("hum-plain", farmer.humidity_plain);
      setText("v-pres", fmt(latest.pressure, 1));

      // Pump & Model Card
      setText("v-pump", isPumpOn ? "RUNNING" : "STOPPED");
      setText("confidence-plain", farmer.confidence_plain || "High Confidence (XGBoost)");

      if (pumpBadge) {
        pumpBadge.textContent = isPumpOn ? "Active Irrigate" : "Standby";
        pumpBadge.className = "status-chip " + (isPumpOn ? "chip-pump" : "chip-neutral");
      }

      if (relayPill) {
        relayPill.innerHTML = `<span class="relay-led"></span> Relay: ${isPumpOn ? "ON (100%)" : "OFF (0%)"}`;
      }

      if (pumpCard) {
        pumpCard.className = "sensor-card pump-card " + (isPumpOn ? "on" : "off");
      }

      const barSoil = document.getElementById("bar-soil");
      if (barSoil) {
        const soilVal = Math.max(0, Math.min(100, Number(latest.soilMoisture)));
        barSoil.style.width = soilVal + "%";
      }
    } else {
      if (pumpPill) {
        pumpPill.className = "pill pump-pill";
        const pText = pumpPill.querySelector(".pill-text");
        if (pText) pText.textContent = "Pump —";
      }
      if (hero) hero.className = "hero-decision idle";
      setText("hero-label", "Waiting");
      setText("decision-text", "Waiting for the greenhouse sensor…");
      setText("decision-reason", "Turn on the ESP32. This page will fill in by itself.");
      setText("updated-at", "Awaiting telemetry…");
      setHidden("stale-banner", true);
      setHidden("sim-banner", true);
      setHidden("hw-banner", true);
    }

    // 3. Update Telemetry Charts & Table
    const rows = logs.rows || [];
    lastKnownRows = rows;
    const count = logs.count || rows.length;

    setText(
      "log-meta",
      count
        ? `${count.toLocaleString()} continuous sensor reading${count === 1 ? "" : "s"} stored in local database`
        : "No live rows yet"
    );

    initOrUpdateChart(rows);

    // Update Observations Table (Most recent 15)
    const tableBody = document.getElementById("log-body");
    if (tableBody) {
      if (!rows.length) {
        tableBody.innerHTML =
          '<tr><td colspan="6" class="table-empty">Waiting for the first live reading from greenhouse ESP32…</td></tr>';
      } else {
        tableBody.replaceChildren();
        const displayRows = [...rows].reverse().slice(0, 15);
        for (const row of displayRows) {
          const tr = document.createElement("tr");
          const isWatered = String(row.relayStatus).toUpperCase() === "ON";

          const cells = [
            localWhen(row.timestamp),
            `${fmt(row.soilMoisture, 1)}%`,
            `${fmt(row.temperature, 1)}°C`,
            `${fmt(row.humidity, 1)}%`,
            `${fmt(row.pressure, 1)} hPa`,
          ];

          cells.forEach((val) => {
            const td = document.createElement("td");
            td.textContent = val;
            tr.appendChild(td);
          });

          // Action Badge Column
          const actionTd = document.createElement("td");
          const badge = document.createElement("span");
          badge.className = "action-badge " + (isWatered ? "watered" : "waited");
          badge.textContent = isWatered ? "Watered" : "Waited";
          actionTd.appendChild(badge);
          tr.appendChild(actionTd);

          tableBody.appendChild(tr);
        }
      }
    }

    // 4. Update Active Learning Progress
    const learn = status.learn || {};
    const learnBtn = document.getElementById("learn-btn");
    const learnSpinner = document.getElementById("learn-spinner");
    const learnBtnLabel = document.getElementById("learn-btn-label");
    const liveRows = learn.live_rows || count || 0;
    const minRows = learn.min_rows || 50;

    const fillPct = Math.min(100, Math.round((liveRows / minRows) * 100));
    const meterFill = document.getElementById("learn-meter-fill");
    if (meterFill) meterFill.style.width = fillPct + "%";
    setText("learn-count-text", `${liveRows} / ${minRows} readings`);

    if (learnBtn) {
      learnBtn.disabled = !learn.can_learn || learn.busy;
      if (learn.busy) {
        if (learnSpinner) setHidden("learn-spinner", false);
        if (learnBtnLabel) learnBtnLabel.textContent = "Retraining XGBoost Model…";
        setText("learn-status", "Retraining model on live field observations. Pump remains protected by active model.");
      } else if (!learn.ready) {
        if (learnSpinner) setHidden("learn-spinner", true);
        if (learnBtnLabel) learnBtnLabel.textContent = "Update model from greenhouse log";
        setText(
          "learn-meta",
          `Accumulating data. Need ${minRows - liveRows} more verified readings before active learning triggers.`
        );
        setText("learn-status", "");
      } else {
        if (learnSpinner) setHidden("learn-spinner", true);
        if (learnBtnLabel) learnBtnLabel.textContent = "Retrain model now";
        setText("learn-meta", `${liveRows} verified greenhouse readings ready for model fine-tuning.`);
        setText("learn-status", learn.last_error ? `Last update issue: ${learn.last_error}` : "Ready to update.");
      }
    }
  } catch (err) {
    setText("decision-text", "This page cannot reach the greenhouse computer");
    setText("decision-reason", "Start the FastAPI service on this computer (port 8000), then refresh.");
    setHidden("stale-banner", true);
  }
}

// Active Learning Trigger
async function learnNow() {
  const btn = document.getElementById("learn-btn");
  const spinner = document.getElementById("learn-spinner");
  const label = document.getElementById("learn-btn-label");
  if (btn) btn.disabled = true;
  if (spinner) setHidden("learn-spinner", false);
  if (label) label.textContent = "Initiating retraining…";
  setText("learn-status", "Starting XGBoost retraining pipeline…");

  try {
    const result = await getJson("/api/learn", { method: "POST" });
    setText("learn-status", result.reason || (result.started ? "Retraining initiated in background…" : "Not started"));
  } catch (err) {
    setText("learn-status", String(err));
  }
  refresh();
}

async function injectReading() {
  const quickBtn = document.getElementById("btn-quick-inject");
  const staleBtn = document.getElementById("btn-stale-inject");
  if (quickBtn) quickBtn.disabled = true;
  if (staleBtn) staleBtn.disabled = true;
  try {
    await getJson("/api/simulate", { method: "POST" });
    staleDismissed = false;
    await refresh();
  } catch (err) {
    console.error("Simulation failed:", err);
  } finally {
    if (quickBtn) quickBtn.disabled = false;
    if (staleBtn) staleBtn.disabled = false;
  }
}

// Chart Mode Tabs & Control Interaction
document.addEventListener("DOMContentLoaded", () => {
  const quickBtn = document.getElementById("btn-quick-inject");
  if (quickBtn) {
    quickBtn.addEventListener("click", injectReading);
  }

  const staleInjectBtn = document.getElementById("btn-stale-inject");
  if (staleInjectBtn) {
    staleInjectBtn.addEventListener("click", injectReading);
  }

  const dismissSim = document.getElementById("btn-dismiss-sim");
  if (dismissSim) {
    dismissSim.addEventListener("click", () => {
      simDismissed = true;
      setHidden("sim-banner", true);
    });
  }

  const dismissHw = document.getElementById("btn-dismiss-hw");
  if (dismissHw) {
    dismissHw.addEventListener("click", () => {
      hwDismissed = true;
      setHidden("hw-banner", true);
    });
  }

  const dismissStale = document.getElementById("btn-dismiss-stale");
  if (dismissStale) {
    dismissStale.addEventListener("click", () => {
      staleDismissed = true;
      setHidden("stale-banner", true);
    });
  }

  const tabGroup = document.getElementById("chart-tabs");
  if (tabGroup) {
    tabGroup.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (!btn) return;
      tabGroup.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentChartMode = btn.dataset.view;
      if (lastKnownRows.length) initOrUpdateChart(lastKnownRows);
    });
  }

  const windowSelect = document.getElementById("time-window-select");
  if (windowSelect) {
    windowSelect.addEventListener("change", (e) => {
      currentTimeWindow = Number(e.target.value) || 60;
      if (lastKnownRows.length) initOrUpdateChart(lastKnownRows);
    });
  }

  const learnBtn = document.getElementById("learn-btn");
  if (learnBtn) {
    learnBtn.addEventListener("click", learnNow);
  }

  // Initial poll & start repeating timer
  refresh();
  setInterval(refresh, 3000);
});
