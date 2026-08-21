"""Simulate a Kathmandu tomato season at the ESP32 15-minute upload interval.

The simulation is a soil-water-balance model (FAO-56 crop coefficient × ET0
proxy) so time-series EDA has diurnal and growth-stage structure. Labels use
the same tomato irrigation rule as the historical workbook.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import DATA_PROCESSED, RANDOM_SEED
from src.features import add_agronomic_features, tomato_irrigation_label

OUT_CSV = DATA_PROCESSED / "tomato_season_simulated.csv"

# FAO-56 tomato crop coefficients (table 12, tomato)
STAGE_DAYS = {"initial": 30, "development": 40, "mid": 40, "late": 25}
KC = {"initial": 0.60, "mid": 1.15, "late": 0.80}


def kc_for_day(day: int) -> float:
    d0 = STAGE_DAYS["initial"]
    d1 = d0 + STAGE_DAYS["development"]
    d2 = d1 + STAGE_DAYS["mid"]
    d3 = d2 + STAGE_DAYS["late"]
    if day < d0:
        return KC["initial"]
    if day < d1:
        frac = (day - d0) / STAGE_DAYS["development"]
        return KC["initial"] + frac * (KC["mid"] - KC["initial"])
    if day < d2:
        return KC["mid"]
    if day < d3:
        frac = (day - d2) / STAGE_DAYS["late"]
        return KC["mid"] + frac * (KC["late"] - KC["mid"])
    return KC["late"]


def kathmandu_climate(day_of_year: np.ndarray, hour: np.ndarray, rng: np.random.Generator):
    """Approximate Kathmandu spring (Feb-Jun) temperature and humidity."""
    season = np.clip((day_of_year - 46) / 120.0, 0, 1)  # 15 Feb = doy 46
    t_mean = 16.0 + 12.0 * season
    t_amp = 6.0 + 3.0 * season
    solar = np.sin((hour - 6.0) / 24.0 * 2 * np.pi)
    solar = np.clip(solar, 0, 1)
    temp = t_mean + t_amp * (solar - 0.35) + rng.normal(0, 0.8, size=hour.shape)
    rh_mean = 72.0 - 18.0 * season
    humidity = rh_mean - 16.0 * solar + rng.normal(0, 3.5, size=hour.shape)
    humidity = np.clip(humidity, 28.0, 95.0)
    pressure = 854.3 + rng.normal(0, 1.8, size=hour.shape) - 1.2 * solar
    return temp, humidity, pressure


def generate(n_days: int = 135, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-02-15 00:00:00")
    index = pd.date_range(start, periods=n_days * 96, freq="15min")  # 96 = 24*4
    hour = (index.hour + index.minute / 60.0).to_numpy()
    clock_hour = index.hour.to_numpy()
    doy = index.dayofyear.to_numpy()
    day_idx = ((index - start).days).to_numpy()

    temp, humidity, pressure = kathmandu_climate(doy, hour, rng)

    soil = 72.0
    soils = np.empty(len(index))
    rains = np.zeros(len(index))
    kcs = np.empty(len(index))

    for i in range(len(index)):
        kc = kc_for_day(int(day_idx[i]))
        kcs[i] = kc
        # light pre-monsoon rain later in the season
        if clock_hour[i] in (14, 15, 16) and rng.random() < 0.02 + 0.04 * (day_idx[i] / max(n_days, 1)):
            rain = float(rng.uniform(0.4, 2.2))
        else:
            rain = 0.0
        rains[i] = rain

        vpd = 0.6108 * np.exp((17.27 * temp[i]) / (temp[i] + 237.3)) * (1 - humidity[i] / 100.0)
        et0_step = (0.18 + 0.55 * max(vpd, 0.1)) * kc / 96.0 * 8.0  # percent moisture / 15 min
        soil = soil - et0_step + rain * 3.5
        soil = float(np.clip(soil + rng.normal(0, 0.15), 2.0, 98.0))
        soils[i] = soil
        # irrigation in the water-balance (wetting event) if the rule fires
        tmp = pd.DataFrame(
            {"temperature": [temp[i]], "humidity": [humidity[i]], "soilMoisture": [soil], "pressure": [pressure[i]]}
        )
        tmp = add_agronomic_features(tmp)
        if tomato_irrigation_label(tmp)[0] == 1 and 6 <= hour[i] <= 10:
            soil = float(np.clip(soil + rng.uniform(10.0, 18.0), 2.0, 98.0))

    df = pd.DataFrame(
        {
            "timestamp": index,
            "temperature": np.round(temp, 2),
            "humidity": np.round(humidity, 2),
            "pressure": np.round(pressure, 2),
            "soilMoisture": np.round(soils, 2),
            "kc": np.round(kcs, 3),
            "rain_mm": np.round(rains, 2),
            "device_id": "esp32-irrigation",
        }
    )
    df = add_agronomic_features(df)
    df["irrigate"] = tomato_irrigation_label(df)
    df["relayStatus"] = np.where(df["irrigate"] == 1, "ON", "OFF")
    df["targetValue"] = np.where(df["irrigate"] == 1, 100.0, 0.0)
    df["growth_stage"] = pd.cut(
        day_idx,
        bins=[-1, 30, 70, 110, 999],
        labels=["initial", "development", "mid", "late"],
    )
    return df


def main() -> Path:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}  rows={len(df)}  irrigate_rate={df['irrigate'].mean():.3f}")
    return OUT_CSV


if __name__ == "__main__":
    main()
