"""Retrain the deployed XGBoost model from the live greenhouse CSV."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from api import storage
from src import PROJECT_ROOT

STATE_PATH = PROJECT_ROOT / "data" / "live" / "learn_state.json"
MIN_LIVE_ROWS = 50
MIN_NEW_ROWS = 50

_lock = threading.Lock()
_busy = False
_last_error = ""


def _read_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"last_row_count": 0, "last_train_iso": None, "busy": False}
    try:
        return json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError:
        return {"last_row_count": 0, "last_train_iso": None, "busy": False}


def _write_state(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2))


def status() -> dict[str, Any]:
    state = _read_state()
    rows = storage.log_count()
    last = int(state.get("last_row_count") or 0)
    new_rows = max(rows - last, 0)
    trained = bool(state.get("last_train_iso"))
    ready = rows >= MIN_LIVE_ROWS
    can_learn = ready and not _busy and (not trained or new_rows >= MIN_NEW_ROWS)
    return {
        "busy": _busy,
        "live_rows": rows,
        "min_rows": MIN_LIVE_ROWS,
        "new_rows_since_learn": new_rows,
        "ready": ready,
        "can_learn": can_learn,
        "last_train_iso": state.get("last_train_iso"),
        "last_error": _last_error or None,
    }


def start(force: bool = False) -> dict[str, Any]:
    global _busy
    info = status()
    if _busy:
        return {"started": False, "reason": "The model is already updating. Please wait.", **info}
    if not force and info["live_rows"] < MIN_LIVE_ROWS:
        return {
            "started": False,
            "reason": (
                f"Need at least {MIN_LIVE_ROWS} live greenhouse readings first "
                f"(now {info['live_rows']}). Keep the ESP32 sending."
            ),
            **info,
        }
    if not force and info["new_rows_since_learn"] < MIN_NEW_ROWS and info["last_train_iso"]:
        return {
            "started": False,
            "reason": "Not enough new readings since the last update. Keep collecting.",
            **info,
        }

    with _lock:
        if _busy:
            return {"started": False, "reason": "The model is already updating. Please wait.", **status()}
        _busy = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"started": True, "reason": "Updating the model from today's greenhouse log.", **status()}


def maybe_schedule() -> None:
    info = status()
    if info["busy"] or not info["ready"]:
        return
    if info["last_train_iso"] and info["new_rows_since_learn"] < MIN_NEW_ROWS:
        return
    start(force=False)


def _run() -> None:
    global _busy, _last_error
    try:
        from src.ingest_live import ingest
        from src.train import train

        ingest(live_only=False, min_rows=MIN_LIVE_ROWS)
        train()
        from api.app import reset_bundle

        reset_bundle()
        _last_error = ""
        _write_state(
            {
                "last_row_count": storage.log_count(),
                "last_train_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
    except Exception as exc:  # noqa: BLE001 — surface to the dashboard
        _last_error = str(exc)
    finally:
        _busy = False
