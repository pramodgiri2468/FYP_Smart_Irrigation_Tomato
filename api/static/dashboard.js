async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + " " + res.status);
  return res.json();
}

function fmt(value, digits) {
  if (value === undefined || value === null || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : String(value);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function drawChart(rows) {
  const svg = document.getElementById("chart");
  svg.replaceChildren();
  const w = 640;
  const h = 160;
  const pad = 12;
  const values = rows.map((r) => Number(r.soilMoisture)).filter((n) => Number.isFinite(n));
  if (values.length < 2) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", "20");
    t.setAttribute("y", "84");
    t.setAttribute("fill", "#5c6b62");
    t.setAttribute("font-size", "14");
    t.textContent = "Need at least two logged readings to draw the soil line.";
    svg.appendChild(t);
    return;
  }
  const min = 0;
  const max = 100;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / (max - min)) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  poly.setAttribute("fill", "none");
  poly.setAttribute("stroke", "#1f4d38");
  poly.setAttribute("stroke-width", "2.4");
  poly.setAttribute("points", pts.join(" "));
  svg.appendChild(poly);
}

async function refresh() {
  try {
    const [health, status, logs] = await Promise.all([
      getJson("/health"),
      getJson("/api/status"),
      getJson("/api/logs?limit=80"),
    ]);

    const hp = document.getElementById("health-pill");
    hp.textContent = health.model_loaded ? "Model loaded" : "Model missing";
    hp.className = "pill " + (health.model_loaded ? "ok" : "bad");

    const latest = status.latest;
    const pump = document.getElementById("pump-pill");
    if (latest) {
      const on = String(latest.relayStatus).toUpperCase() === "ON";
      pump.textContent = on ? "Pump ON" : "Pump OFF";
      pump.className = "pill pump " + (on ? "on" : "off");
      const need = Number(latest.water_needed) === 1;
      setText("decision-text", need ? "Water needed — irrigate now" : "Hold water — soil / climate OK");
      setText("decision-reason", latest.reason || "");
      setText("v-soil", fmt(latest.soilMoisture, 1));
      setText("v-temp", fmt(latest.temperature, 1));
      setText("v-hum", fmt(latest.humidity, 1));
      setText("v-pres", fmt(latest.pressure, 1));
      setText("v-need", String(latest.water_needed));
      setText("v-prob", fmt(Number(latest.probability) * 100, 1) + "%");
      setText("v-model", latest.model || "xgboost");
      document.getElementById("bar-soil").style.width = Math.max(0, Math.min(100, Number(latest.soilMoisture))) + "%";
    } else {
      pump.textContent = "Pump —";
      pump.className = "pill pump";
    }

    const rows = logs.rows || [];
    setText("log-meta", logs.count ? logs.count + " stored decisions" : "No live rows yet");
    drawChart(rows);

    const body = document.getElementById("log-body");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8" class="empty">POST /predict from the ESP32 (or /docs) to fill this table.</td></tr>';
      return;
    }
    body.replaceChildren();
    for (const row of [...rows].reverse().slice(0, 25)) {
      const tr = document.createElement("tr");
      const cells = [
        row.timestamp,
        fmt(row.soilMoisture, 1),
        fmt(row.temperature, 1),
        fmt(row.humidity, 1),
        fmt(row.pressure, 1),
        row.water_needed,
        row.relayStatus,
        fmt(row.probability, 3),
      ];
      for (const c of cells) {
        const td = document.createElement("td");
        td.textContent = c == null ? "—" : String(c);
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  } catch (err) {
    setText("decision-text", "Dashboard cannot reach the API");
    setText("decision-reason", String(err));
  }
}

refresh();
setInterval(refresh, 5000);
