"""Turn live ESP32 CSV rows into training data, then optionally train XGBoost."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import PROJECT_ROOT
from src.features import add_agronomic_features, tomato_irrigation_label
from src.preprocess import PROCESSED_CSV, build_processed, load_raw

LIVE_CSV = PROJECT_ROOT / "data" / "live" / "irrigation_log.csv"

KEEP = [
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


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["relayStatus"] = np.where(out["irrigate"] == 1, "ON", "OFF")
    out["targetValue"] = np.where(out["irrigate"] == 1, 100.0, 0.0)
    if "device_id" not in out.columns:
        out["device_id"] = "esp32-irrigation"
    out["device_id"] = out["device_id"].fillna("esp32-irrigation")
    return out[KEEP]


def live_to_training(path: Path | None = None) -> pd.DataFrame:
    """Map irrigation_log.csv to the processed training schema.

    soilMoisture from the ESP32 is already 0-100 percent. Labels come from
    the tomato FAO rule, not from the model's previous water_needed column.
    """
    path = path or LIVE_CSV
    if not path.exists():
        raise FileNotFoundError(f"No live log at {path}. Start FastAPI and flash the ESP32.")

    live = pd.read_csv(path)
    needed = {"temperature", "humidity", "soilMoisture"}
    missing = needed - set(live.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")

    live["temperature"] = pd.to_numeric(live["temperature"], errors="coerce")
    live["humidity"] = pd.to_numeric(live["humidity"], errors="coerce")
    live["soilMoisture"] = pd.to_numeric(live["soilMoisture"], errors="coerce")
    if "pressure" in live.columns:
        live["pressure"] = pd.to_numeric(live["pressure"], errors="coerce")
    else:
        live["pressure"] = 0.0

    live = live.dropna(subset=["temperature", "humidity", "soilMoisture"]).copy()
    live = live[(live["temperature"] > 0) & (live["humidity"] > 0)]
    live = live[(live["soilMoisture"] >= 0) & (live["soilMoisture"] <= 100)]
    live = live.drop_duplicates(
        subset=["temperature", "humidity", "soilMoisture", "pressure"]
    )
    if live.empty:
        raise ValueError(f"No usable sensor rows in {path}.")

    live["soil_raw"] = live["soilMoisture"]
    if "relayStatus" in live.columns:
        live["pump_historical"] = (
            live["relayStatus"].astype(str).str.upper().eq("ON").astype(int)
        )
    elif "water_needed" in live.columns:
        live["pump_historical"] = pd.to_numeric(live["water_needed"], errors="coerce").fillna(0).astype(int)
    else:
        live["pump_historical"] = 0

    live = add_agronomic_features(live)
    live["irrigate"] = tomato_irrigation_label(live)
    if "device_id" not in live.columns:
        live["device_id"] = "esp32-irrigation"
    return _finalize(live)


def ingest(*, live_only: bool = False, min_rows: int = 50) -> Path:
    live = live_to_training()
    n_live = len(live)
    if n_live < min_rows:
        print(
            f"Warning: only {n_live} unique live rows "
            f"(want {min_rows}+ covering dry/wet and hot/cool)."
        )

    if live_only:
        combined = live
    else:
        if PROCESSED_CSV.exists():
            old = pd.read_csv(PROCESSED_CSV)
        else:
            old = _finalize(build_processed(load_raw()))
        combined = pd.concat([old[KEEP], live], ignore_index=True)

    PROCESSED_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(PROCESSED_CSV, index=False)
    print(f"Wrote {PROCESSED_CSV}")
    print(f"  live_rows={n_live}  total_rows={len(combined)}  irrigate_rate={combined['irrigate'].mean():.3f}")
    return PROCESSED_CSV


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge live ESP32 readings into the training CSV and optionally train."
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Train only on Arduino rows (skip the Kathmandu workbook).",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=50,
        help="Warn if unique live rows are below this count.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Run src.train after merging (saves models/irrigation_model.joblib).",
    )
    args = parser.parse_args()
    ingest(live_only=args.live_only, min_rows=args.min_rows)
    if args.train:
        from src.train import train

        train()


if __name__ == "__main__":
    main()
