"""FastAPI service: live ESP32 sensors, XGBoost on this Mac, farmer dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import learn, plain, storage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "irrigation_model.joblib"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Smart Irrigation Tomato API",
    description="Live greenhouse sensors → XGBoost on this Mac → farmer dashboard.",
    version="2.1.0",
)

_bundle = None
_bundle_mtime = None


def reset_bundle() -> None:
    global _bundle, _bundle_mtime
    _bundle = None
    _bundle_mtime = None


def load_bundle():
    global _bundle, _bundle_mtime
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run: python -m src.train"
        )
    mtime = MODEL_PATH.stat().st_mtime
    if _bundle is None or _bundle_mtime != mtime:
        _bundle = joblib.load(MODEL_PATH)
        _bundle_mtime = mtime
    return _bundle


class SensorReading(BaseModel):
    temperature: float = Field(..., description="Air temperature in C (DHT11)")
    humidity: float = Field(..., ge=0, le=100, description="Relative humidity % (DHT11)")
    soilMoisture: float = Field(..., ge=0, le=100, description="Soil moisture % from ESP32")
    pressure: Optional[float] = Field(
        default=None,
        description="Air pressure hPa. 0 or omitted → Kathmandu mean 854.27.",
    )
    device_id: Optional[str] = Field(default="esp32-irrigation")


class IrrigationDecision(BaseModel):
    water_needed: int
    irrigate: bool
    probability: float
    relayStatus: str
    targetValue: float
    model: str
    reasons: list[str]
    logged: bool = True
    headline: str
    soil_plain: str
    pump_plain: str


@app.get("/health")
def health():
    model_ok = MODEL_PATH.exists()
    row = storage.latest()
    return {
        "status": "ok" if model_ok else "degraded",
        "model_loaded": model_ok,
        "log_rows": storage.log_count(),
        "live": plain.is_live((row or {}).get("timestamp")),
    }


@app.get("/api")
def api_info():
    return {
        "project": "Smart Irrigation for Tomato",
        "dashboard": "/",
        "predict": "POST /predict",
        "health": "/health",
        "logs": "/api/logs",
        "learn": "POST /api/learn",
        "docs": "/docs",
    }


@app.post("/predict", response_model=IrrigationDecision)
def predict(reading: SensorReading):
    try:
        bundle = load_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    pressure = reading.pressure if reading.pressure not in (None, 0) else 854.27
    frame = pd.DataFrame(
        [
            {
                "temperature": reading.temperature,
                "humidity": reading.humidity,
                "soilMoisture": reading.soilMoisture,
                "pressure": pressure,
            }
        ]
    )
    pipeline = bundle["pipeline"]
    prob = float(pipeline.predict_proba(frame)[0, 1])
    irrigate = prob >= 0.5
    water_needed = 1 if irrigate else 0
    reasons = plain.farmer_reasons(reading.temperature, reading.humidity, reading.soilMoisture)
    model_name = bundle.get("model_name", "xgboost")
    relay_status = "ON" if irrigate else "OFF"

    storage.append_decision(
        {
            "device_id": reading.device_id,
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "soilMoisture": reading.soilMoisture,
            "pressure": pressure,
            "water_needed": water_needed,
            "irrigate": irrigate,
            "probability": round(prob, 4),
            "relayStatus": relay_status,
            "model": model_name,
            "reason": reasons[0],
        }
    )
    return IrrigationDecision(
        water_needed=water_needed,
        irrigate=irrigate,
        probability=round(prob, 4),
        relayStatus=relay_status,
        targetValue=100.0 if irrigate else 0.0,
        model=model_name,
        reasons=reasons,
        logged=True,
        headline=plain.advice_headline(irrigate),
        soil_plain=plain.soil_plain(reading.soilMoisture),
        pump_plain="Running" if irrigate else "Stopped",
    )


@app.get("/api/status")
def status():
    model_ok = MODEL_PATH.exists()
    row = storage.latest()
    farmer = plain.farmer_view(row)
    return {
        "model_loaded": model_ok,
        "model_path": str(MODEL_PATH.name),
        "model_name": "xgboost",
        "log_rows": storage.log_count(),
        "latest": row,
        "farmer": farmer,
        "pump": (row or {}).get("relayStatus") if row else None,
        "water_needed": int((row or {}).get("water_needed", 0)) if row else None,
        "learn": learn.status(),
    }


@app.post("/api/learn")
def learn_now():
    return learn.start(force=False)


@app.get("/api/logs")
def logs(limit: int = Query(default=120, ge=1, le=2000)):
    return {"rows": storage.read_logs(limit=limit), "count": storage.log_count()}


@app.get("/api/logs.csv")
def logs_csv():
    storage._ensure_file()
    return FileResponse(
        storage.LOG_CSV,
        media_type="text/csv",
        filename="irrigation_log.csv",
    )


@app.get("/")
def dashboard():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(index, headers={"Cache-Control": "no-store"})


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
