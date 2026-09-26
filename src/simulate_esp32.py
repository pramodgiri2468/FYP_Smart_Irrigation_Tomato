"""Simulate greenhouse ESP32 sensor telemetry sent to the local FastAPI service.

Allows testing the closed-loop system, web dashboard, and /health live status
without requiring physical hardware to be plugged in.

Usage:
    python3 -m src.simulate_esp32          # Stream continuous readings every 5 seconds
    python3 -m src.simulate_esp32 --once   # Send single reading to turn live: true
    python3 -m src.simulate_esp32 --dry    # Send dry reading (water_needed = 1)
    python3 -m src.simulate_esp32 --wet    # Send wet reading (water_needed = 0)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
import urllib.error

DEFAULT_HOST = "http://127.0.0.1:8000"


def send_reading(
    host: str,
    temp: float,
    humidity: float,
    soil: float,
    pressure: float = 854.27,
    device_id: str = "esp32-simulated",
) -> dict:
    url = f"{host.rstrip('/')}/predict"
    payload = {
        "temperature": round(temp, 2),
        "humidity": round(humidity, 2),
        "soilMoisture": round(soil, 2),
        "pressure": round(pressure, 2),
        "device_id": device_id,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as err:
        print(f"[ERROR] Could not connect to {url}: {err}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate live ESP32 greenhouse telemetry.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="API base URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--once", action="store_true", help="Send a single reading and exit immediately.")
    parser.add_argument("--interval", type=float, default=5.0, help="Interval in seconds between packets (default: 5.0).")
    parser.add_argument("--count", type=int, default=0, help="Number of packets to send (0 = infinite loop).")
    parser.add_argument("--soil", type=float, default=None, help="Explicit soil moisture percentage to test (e.g. 0.0, 35.0, 70.0).")
    parser.add_argument("--dry", action="store_true", help="Force dry soil reading (<40%) to trigger irrigation.")
    parser.add_argument("--wet", action="store_true", help="Force wet soil reading (>75%) to hold off irrigation.")

    args = parser.parse_args()

    print("=" * 70)
    print(f"  Smart Tomato Irrigation — ESP32 Telemetry Simulator")
    print(f"  Target: {args.host}/predict")
    print(f"  Mode: {'Single Shot' if args.once else f'Streaming every {args.interval}s'}")
    if args.soil is not None:
        print(f"  Fixed Soil Moisture: {args.soil:.1f}%")
    print("=" * 70)

    # Initial realistic Kathmandu greenhouse baseline
    temp = 29.5
    humidity = 48.0
    if args.soil is not None:
        soil = float(args.soil)
    elif args.dry:
        soil = 38.0
    elif args.wet:
        soil = 78.0
    else:
        soil = 58.0
    pressure = 854.27
    sent_count = 0

    try:
        while True:
            sent_count += 1

            # Natural greenhouse fluctuations if not fixed
            if args.soil is None and not args.dry and not args.wet:
                temp += random.uniform(-0.3, 0.3)
                temp = max(18.0, min(36.0, temp))

                humidity += random.uniform(-0.5, 0.5)
                humidity = max(30.0, min(85.0, humidity))

                # Soil slowly dries unless pump runs
                soil += random.uniform(-0.4, 0.1)
                soil = max(25.0, min(82.0, soil))

                pressure += random.uniform(-0.1, 0.1)

            res = send_reading(args.host, temp, humidity, soil, pressure)

            decision = "WATER NOW (PUMP ON)" if res.get("water_needed") else "STANDBY (PUMP OFF)"
            prob = res.get("probability", 0.0)
            headline = res.get("headline", "")
            reasons = res.get("reasons", [])
            reason_txt = f" | {reasons[0]}" if reasons else ""

            print(
                f"[{sent_count:03d}] Sent: Temp={temp:.1f}°C, Hum={humidity:.1f}%, Soil={soil:.1f}% "
                f"-> Decision: {decision} (p={prob:.2f}) | {headline}{reason_txt}"
            )

            # If watering turned ON and not fixed mode, simulate water infiltration
            if res.get("water_needed") and args.soil is None and not args.dry:
                soil += 3.5  # Simulate water infiltration into root zone

            if args.once or (args.count > 0 and sent_count >= args.count):
                print(f"\n[DONE] Successfully sent {sent_count} reading(s). Live status is now active on {args.host}/health.")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n[STOPPED] Simulator terminated by user after {sent_count} packet(s).")


if __name__ == "__main__":
    main()
