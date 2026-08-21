"""FastAPI service that decides whether a tomato plot should be irrigated."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "irrigation_model.joblib"

app = FastAPI(
    title="Smart Irrigation Tomato API",
    description="Predicts irrigation ON/OFF from ESP32 DHT11 + soil-moisture readings.",
    version="1.0.0",
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
        description="Optional air pressure hPa. ESP32 currently sends 0; Kathmandu mean is used.",
    )


class IrrigationDecision(BaseModel):
    irrigate: bool
    probability: float
    relayStatus: str
    targetValue: float
    model: str
    reasons: list[str]


@app.get("/health")
def health():
    model_ok = MODEL_PATH.exists()
    return {"status": "ok" if model_ok else "degraded", "model_loaded": model_ok}


@app.get("/")
def root():
    return {
        "project": "Smart Irrigation for Tomato",
        "docs": "/docs",
        "predict": "POST /predict",
        "health": "/health",
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

    return IrrigationDecision(
        irrigate=irrigate,
        probability=round(prob, 4),
        relayStatus="ON" if irrigate else "OFF",
        targetValue=100.0 if irrigate else 0.0,
        model=bundle.get("model_name", "unknown"),
        reasons=reasons,
    )
