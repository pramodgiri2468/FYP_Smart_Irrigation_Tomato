async function getJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error("Could not reach the greenhouse computer");
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

function setHidden(id, hidden) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden", hidden);
}

function localWhen(timestamp) {
  if (!timestamp) return "—";
  const d = new Date(timestamp);
  if (Number.isNaN(d.getTime())) return String(timestamp);
  return d.toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "numeric",
    month: "short",
  });
}

function ago(seconds) {
  if (seconds == null) return "";
  if (seconds < 5) return "Just now";
  if (seconds < 60) return "Updated " + seconds + " seconds ago";
  const mins = Math.round(seconds / 60);
  if (mins === 1) return "Updated 1 minute ago";
  if (mins < 60) return "Updated " + mins + " minutes ago";
  return "Updated more than an hour ago";
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
    t.textContent = "Need two live readings to draw the soil line.";
    svg.appendChild(t);
    return;
  }
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = pad + (1 - v / 100) * (h - pad * 2);
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
    const [status, logs] = await Promise.all([
      getJson("/api/status"),
      getJson("/api/logs?limit=80"),
    ]);

    const latest = status.latest;
    const farmer = status.farmer;
    const live = Boolean(farmer && farmer.live);
    const livePill = document.getElementById("live-pill");
    livePill.textContent = live ? "Live greenhouse" : latest ? "No new reading" : "Waiting for sensors";
    livePill.className = "pill " + (live ? "live" : latest ? "bad" : "");

    const pump = document.getElementById("pump-pill");
    const hero = document.getElementById("decision-banner");
    const pumpCard = document.getElementById("pump-card");

    if (latest && farmer) {
      const on = farmer.pump_plain === "Running";
      pump.textContent = on ? "Pump running" : "Pump stopped";
      pump.className = "pill pump " + (on ? "on" : "off");
      hero.className = "hero " + (on ? "water" : "wait");
      setText("hero-label", live ? "Live decision" : "Last known decision");
      setText("decision-text", farmer.headline);
      setText("decision-reason", farmer.reason);
      setText("updated-at", ago(farmer.age_seconds));
      setText("v-soil", fmt(latest.soilMoisture, 0) + "%");
      setText("soil-plain", farmer.soil_plain);
      setText("v-temp", fmt(latest.temperature, 0) + "°");
      setText("temp-plain", farmer.temp_plain);
      setText("v-hum", fmt(latest.humidity, 0) + "%");
      setText("hum-plain", farmer.humidity_plain);
      setText("v-pres", fmt(latest.pressure, 0));
      setText("v-pump", farmer.pump_plain);
      setText("confidence-plain", farmer.confidence_plain);
      pumpCard.className = "card pump-card " + (on ? "on" : "off");
      document.getElementById("bar-soil").style.width =
        Math.max(0, Math.min(100, Number(latest.soilMoisture))) + "%";
      setHidden("stale-banner", live);
    } else {
      pump.textContent = "Pump —";
      pump.className = "pill pump";
      hero.className = "hero idle";
      setText("hero-label", "Waiting");
      setText("decision-text", "Waiting for the greenhouse sensor…");
      setText("decision-reason", "Turn on the ESP32. This page will fill in by itself.");
      setText("updated-at", "");
      setHidden("stale-banner", true);
    }

    const rows = logs.rows || [];
    const n = logs.count || 0;
    setText(
      "log-meta",
      n ? n + " live reading" + (n === 1 ? "" : "s") + " stored on this computer" : "No live rows yet"
    );
    drawChart(rows);

    const body = document.getElementById("log-body");
    if (!rows.length) {
      body.innerHTML =
        '<tr><td colspan="5" class="empty">Waiting for the first live reading from the greenhouse.</td></tr>';
    } else {
      body.replaceChildren();
      for (const row of [...rows].reverse().slice(0, 20)) {
        const tr = document.createElement("tr");
        const on = String(row.relayStatus).toUpperCase() === "ON";
        const cells = [
          localWhen(row.timestamp),
          fmt(row.soilMoisture, 0) + "%",
          fmt(row.temperature, 0) + "°",
          fmt(row.humidity, 0) + "%",
          on ? "Watered" : "Waited",
        ];
        cells.forEach((c, i) => {
          const td = document.createElement("td");
          td.textContent = c;
          if (i === 4) td.className = on ? "action-on" : "action-off";
          tr.appendChild(td);
        });
        body.appendChild(tr);
      }
    }

    const learn = status.learn || {};
    const btn = document.getElementById("learn-btn");
    btn.disabled = !learn.can_learn;
    if (learn.busy) {
      setText("learn-status", "Updating the model from the greenhouse log. Pump still uses the current model.");
    } else if (!learn.ready) {
      setText(
        "learn-meta",
        "Need " +
          learn.min_rows +
          " live greenhouse readings before the model can learn from this farm (now " +
          (learn.live_rows || 0) +
          ")."
      );
      setText("learn-status", "");
    } else {
      setText(
        "learn-meta",
        (learn.live_rows || 0) +
          " live readings are ready. The model can learn from this greenhouse."
      );
      setText("learn-status", learn.last_error ? "Last update failed: " + learn.last_error : "");
    }
  } catch (err) {
    setText("decision-text", "This page cannot reach the greenhouse computer");
    setText("decision-reason", "Start the API on this Mac, then refresh.");
    setHidden("stale-banner", true);
  }
}

async function learnNow() {
  const btn = document.getElementById("learn-btn");
  btn.disabled = true;
  setText("learn-status", "Starting…");
  try {
    const result = await getJson("/api/learn", { method: "POST" });
    setText("learn-status", result.reason || (result.started ? "Updating…" : "Not started"));
  } catch (err) {
    setText("learn-status", String(err));
  }
  refresh();
}

document.getElementById("learn-btn").addEventListener("click", learnNow);
refresh();
setInterval(refresh, 3000);
