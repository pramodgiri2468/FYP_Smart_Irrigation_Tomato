"""Append live ESP32 readings and ML decisions to a local CSV."""

from __future__ import annotations

import csv
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import PROJECT_ROOT

LIVE_DIR = PROJECT_ROOT / "data" / "live"
LOG_CSV = LIVE_DIR / "irrigation_log.csv"
_LOCK = threading.Lock()

COLUMNS = [
    "timestamp",
    "device_id",
    "temperature",
    "humidity",
    "soilMoisture",
    "pressure",
    "water_needed",
    "irrigate",
    "probability",
    "relayStatus",
    "model",
    "reason",
]


def _ensure_file() -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_CSV.exists():
        with LOG_CSV.open("w", newline="") as handle:
            csv.DictWriter(handle, fieldnames=COLUMNS).writeheader()


def append_decision(row: dict[str, Any]) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device_id": row.get("device_id") or "esp32-irrigation",
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "soilMoisture": row["soilMoisture"],
        "pressure": row["pressure"],
        "water_needed": int(row["water_needed"]),
        "irrigate": int(bool(row["irrigate"])),
        "probability": row["probability"],
        "relayStatus": row["relayStatus"],
        "model": row["model"],
        "reason": row.get("reason") or "",
    }
    with _LOCK:
        _ensure_file()
        with LOG_CSV.open("a", newline="") as handle:
            csv.DictWriter(handle, fieldnames=COLUMNS).writerow(record)
    return record


def read_logs(limit: int = 200) -> list[dict[str, Any]]:
    with _LOCK:
        if not LOG_CSV.exists():
            return []
        with LOG_CSV.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    return rows[-max(1, limit) :]


def latest() -> dict[str, Any] | None:
    rows = read_logs(limit=1)
    return rows[-1] if rows else None


def log_count() -> int:
    with _LOCK:
        if not LOG_CSV.exists():
            return 0
        with LOG_CSV.open(newline="") as handle:
            return max(sum(1 for _ in handle) - 1, 0)
