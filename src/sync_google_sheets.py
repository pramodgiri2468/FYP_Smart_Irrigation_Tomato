"""Google Sheets Telemetry Bridge & Ingestion Tool.

Syncs real ESP32 sensor records from Google Sheets directly to the local
FastAPI smart irrigation service.

Usage:
    python3 -m src.sync_google_sheets --file <path_to_tsv_or_csv>
    python3 -m src.sync_google_sheets --poll   # Polls SCRIPT_URL periodically (requires ?json=1 in Apps Script)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_HOST = "http://127.0.0.1:8000"
DEFAULT_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw9etTizWnSERy0UmpoW_jPVl0iasuGZTRrtUKrDxTUkHywvrx_hKU_m_zm7xmY-fw/exec"
NPT = timezone(timedelta(hours=5, minutes=45))


def post_reading(host: str, temp: float, humidity: float, soil: float, pressure: float, device_id: str) -> dict:
    url = f"{host.rstrip('/')}/predict"
    payload = {
        "temperature": round(temp, 2),
        "humidity": round(humidity, 2),
        "soilMoisture": round(soil, 2),
        "pressure": round(pressure, 2),
        "device_id": device_id,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ingest_tsv_text(tsv_text: str, host: str = DEFAULT_HOST) -> int:
    lines = [l.strip() for l in tsv_text.strip().split("\n") if l.strip()]
    if not lines:
        return 0
    
    count = 0
    for line in lines:
        if "Timestamp" in line or "Temperature" in line:
            continue
        parts = line.split("\t") if "\t" in line else line.split(",")
        if len(parts) < 7:
            continue
        try:
            ts_str = parts[0].strip()
            temp = float(parts[2].strip())
            hum = float(parts[3].strip())
            press = float(parts[4].strip())
            soil = float(parts[5].strip())
            device_id = parts[16].strip() if len(parts) > 16 else "esp32-irrigation"

            res = post_reading(host, temp, hum, soil, press, device_id)
            count += 1
            print(f"[{count:03d}] {ts_str} | Temp={temp}°C, Hum={hum}%, Soil={soil}% -> {res.get('headline')} (Relay={res.get('relayStatus')})")
        except Exception as e:
            print(f"[WARN] Skipped row: {line[:40]}... ({e})", file=sys.stderr)
            continue
    return count


def poll_script_url(script_url: str, host: str = DEFAULT_HOST, interval: float = 30.0):
    print(f"Polling Google Sheets URL for real-time readings every {interval}s...")
    seen_timestamps = set()
    while True:
        try:
            url = f"{script_url}?json=1&limit=20"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartIrrigationBridge/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
                if content.strip().startswith("["):
                    rows = json.loads(content)
                    for r in rows:
                        ts = str(r.get("Timestamp", ""))
                        if ts and ts not in seen_timestamps:
                            seen_timestamps.add(ts)
                            temp = float(r.get("Temperature (C)", 0))
                            hum = float(r.get("Humidity (%)", 0))
                            press = float(r.get("Pressure (hPa)", 854.27))
                            soil = float(r.get("Soil Moisture (%)", 0))
                            device = str(r.get("Device ID", "esp32-irrigation"))
                            post_reading(host, temp, hum, soil, press, device)
                            print(f"[SYNC] Ingested Google Sheet row: {ts} Temp={temp}°C, Soil={soil}%")
        except Exception as err:
            print(f"[BRIDGE NOTICE] Polling note: {err}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Ingest real ESP32 Google Sheet data to FastAPI.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="API Base URL")
    parser.add_argument("--file", help="Path to TSV/CSV export file to ingest")
    parser.add_argument("--poll", action="store_true", help="Continuously poll Google Apps Script URL")
    parser.add_argument("--script-url", default=DEFAULT_SCRIPT_URL, help="Google Apps Script web app URL")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
        n = ingest_tsv_text(text, host=args.host)
        print(f"[SUCCESS] Ingested {n} rows into dashboard database.")
    elif args.poll:
        poll_script_url(args.script_url, host=args.host)
    else:
        print("Usage: python3 -m src.sync_google_sheets --file <path> OR --poll")


if __name__ == "__main__":
    main()
