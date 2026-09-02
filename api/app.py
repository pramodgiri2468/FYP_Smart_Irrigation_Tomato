"""FastAPI service: infer irrigation, store CSV logs, serve the farmer dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import storage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "irrigation_model.joblib"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Smart Irrigation Tomato API",
    description="Local FastAPI service: ESP32 JSON in, water_needed out, farmer dashboard.",
    version="2.0.0",
)

_bundle = None


def load_bundle():
    global _bundle
    if _bundle is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run: python -m src.train"
            )
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


class SensorReading(BaseModel):
    temperature: float = Field(..., description="Air temperature in C (DHT11)")
    humidity: float = Field(..., ge=0, le=100, description="Relative humidity % (DHT11)")
    soilMoisture: float = Field(..., ge=0, le=100, description="Soil moisture % from ESP32")
    pressure: Optional[float] = Field(
        default=None,
        description="BMP280 air pressure hPa. 0 or omitted → Kathmandu mean 854.27.",
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


def _reasons(reading: SensorReading) -> list[str]:
    reasons = []
    if reading.soilMoisture < 45:
        reasons.append("Soil moisture is below the tomato readily-available-water band.")
    elif reading.soilMoisture < 60:
        reasons.append("Soil moisture is approaching the FAO tomato depletion threshold.")
    if reading.temperature >= 30:
        reasons.append("Air temperature is in the tomato heat-stress range; crop water use is high.")
    if reading.humidity <= 45:
        reasons.append("Dry air (low humidity) increases vapor pressure deficit.")
    if not reasons:
        reasons.append("Combined soil and climate features drive this decision.")
    return reasons


@app.get("/health")
def health():
    model_ok = MODEL_PATH.exists()
    return {
        "status": "ok" if model_ok else "degraded",
        "model_loaded": model_ok,
        "log_rows": storage.log_count(),
    }


@app.get("/api")
def api_info():
    return {
        "project": "Smart Irrigation for Tomato",
        "dashboard": "/",
        "predict": "POST /predict",
        "health": "/health",
        "logs": "/api/logs",
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
    reasons = _reasons(reading)
    model_name = bundle.get("model_name", "unknown")
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
    )


@app.get("/api/status")
def status():
    model_ok = MODEL_PATH.exists()
    row = storage.latest()
    return {
        "model_loaded": model_ok,
        "model_path": str(MODEL_PATH.name),
        "log_rows": storage.log_count(),
        "latest": row,
        "pump": (row or {}).get("relayStatus") if row else None,
        "water_needed": int((row or {}).get("water_needed", 0)) if row else None,
    }


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
    return FileResponse(index)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
