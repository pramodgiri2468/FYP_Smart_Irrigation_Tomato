"""Short farmer-facing sentences for live greenhouse readings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def soil_plain(soil: float) -> str:
    if soil <= 0.5:
        return "Probe / calibration?"
    if soil < 40:
        return "Too dry"
    if soil < 55:
        return "A little dry"
    if soil < 75:
        return "Good for tomato"
    return "Wet enough"


def temp_plain(temp: float) -> str:
    if temp < 18:
        return "Cool"
    if temp >= 30:
        return "Hot"
    return "Comfortable"


def humidity_plain(humidity: float) -> str:
    if humidity < 45:
        return "Dry air"
    if humidity > 80:
        return "Very humid"
    return "Comfortable"


def advice_headline(water_needed: bool) -> str:
    if water_needed:
        return "Water the plants now"
    return "Soil is fine — keep the pump off"


def farmer_reasons(temperature: float, humidity: float, soil_moisture: float) -> list[str]:
    reasons: list[str] = []
    if soil_moisture <= 0.5:
        reasons.append(
            "Soil reads 0%. Check the probe is in the soil, and set DRY_SOIL / WET_SOIL in soil_moisture.cpp."
        )
    elif soil_moisture < 40:
        reasons.append("The soil is too dry for tomato roots.")
    elif soil_moisture < 55:
        reasons.append("The soil is getting dry. Tomatoes may need water soon.")
    elif soil_moisture >= 75:
        reasons.append("The soil already has enough water.")
    else:
        reasons.append("Soil moisture looks comfortable for tomato.")

    if temperature >= 30:
        reasons.append("The air is hot, so plants drink more water.")
    elif temperature < 18:
        reasons.append("The air is cool, so extra watering is usually not needed.")

    if humidity <= 45:
        reasons.append("The air is dry, so water leaves the leaves faster.")
    elif humidity > 80 and soil_moisture >= 55:
        reasons.append("The air is already very humid; extra watering can harm roots.")

    return reasons


def confidence_plain(probability: float, irrigate: bool) -> str:
    sure = probability if irrigate else 1.0 - probability
    if sure >= 0.85:
        return "The computer is quite sure."
    if sure >= 0.65:
        return "The computer is fairly sure."
    return "The computer is a bit unsure, but this is its best guess."


def age_seconds(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    text = str(timestamp).replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def is_live(timestamp: str | None, max_age: float = 90.0) -> bool:
    age = age_seconds(timestamp)
    return age is not None and 0 <= age <= max_age


def farmer_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    soil = float(row.get("soilMoisture") or 0)
    temp = float(row.get("temperature") or 0)
    hum = float(row.get("humidity") or 0)
    need = str(row.get("water_needed")) in {"1", "True", "true"} or str(
        row.get("relayStatus", "")
    ).upper() == "ON"
    prob = float(row.get("probability") or 0)
    age = age_seconds(row.get("timestamp"))
    return {
        "headline": advice_headline(need),
        "reason": row.get("reason") or farmer_reasons(temp, hum, soil)[0],
        "soil_plain": soil_plain(soil),
        "temp_plain": temp_plain(temp),
        "humidity_plain": humidity_plain(hum),
        "pump_plain": "Running" if need else "Stopped",
        "confidence_plain": confidence_plain(prob, need),
        "live": is_live(row.get("timestamp")),
        "age_seconds": None if age is None else round(age),
    }
