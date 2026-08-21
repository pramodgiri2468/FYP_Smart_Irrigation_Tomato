"""Load the Kathmandu IoT workbook and emit a model-ready CSV."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import DATA_PROCESSED, DATA_RAW, PROJECT_ROOT
from src.features import add_agronomic_features, tomato_irrigation_label

RAW_XLSX = DATA_RAW / "Soil_Moisture_Temp_Humidity_Pressure_MotorOnOff.xlsx"
PROCESSED_CSV = DATA_PROCESSED / "tomato_irrigation.csv"

COLUMN_MAP = {
    "Soil Moisture": "soil_raw",
    "Temperature": "temperature",
    "Air Humidity": "humidity",
    "Atmospheric Pressure (Kathmandu)": "pressure",
    "Pump Data": "pump_historical",
}


def soil_raw_to_percent(raw: np.ndarray) -> np.ndarray:
    """Map this dataset ADC range to 0-100 percent moisture.

    Higher raw values coincide with pump OFF, so higher ADC = wetter soil,
    matching a typical resistive / analog moisture probe. The ESP32 firmware
    already publishes 0-100 percent, so inference uses this scale.
    """
    lo, hi = float(np.min(raw)), float(np.max(raw))
    pct = 100.0 * (raw - lo) / (hi - lo)
    return np.clip(pct, 0.0, 100.0)


def load_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or RAW_XLSX
    df = pd.read_excel(path)
    df = df.rename(columns=COLUMN_MAP)
    missing = set(COLUMN_MAP.values()) - set(df.columns)
    if missing:
        raise ValueError(f"Unexpected columns in {path}: missing {missing}")
    return df


def build_processed(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["soilMoisture"] = soil_raw_to_percent(out["soil_raw"].to_numpy(dtype=float))
    out = add_agronomic_features(out)
    out["irrigate"] = tomato_irrigation_label(out)
    out["relayStatus"] = np.where(out["irrigate"] == 1, "ON", "OFF")
    out["targetValue"] = np.where(out["irrigate"] == 1, 100.0, 0.0)
    out["device_id"] = "esp32-irrigation"
    ordered = [
        "temperature",
        "humidity",
        "pressure",
        "soil_raw",
        "soilMoisture",
        "vpd_kpa",
        "et0_proxy",
        "heat_stress",
        "moisture_deficit",
        "dry_hot_index",
        "pump_historical",
        "irrigate",
        "relayStatus",
        "targetValue",
        "device_id",
    ]
    return out[ordered]


def main() -> Path:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    processed = build_processed(load_raw())
    processed.to_csv(PROCESSED_CSV, index=False)
    print(f"Wrote {PROCESSED_CSV}  rows={len(processed)}")
    print(processed[["pump_historical", "irrigate"]].mean())
    return PROCESSED_CSV


if __name__ == "__main__":
    main()
