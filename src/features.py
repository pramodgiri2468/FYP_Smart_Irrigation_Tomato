"""Agronomic feature engineering for tomato irrigation.

Formulas follow FAO-56 (Allen et al., 1998):
- saturation vapor pressure and VPD from air temperature and RH
- ET0 proxy when wind/solar sensors are unavailable on the ESP32
- tomato comfort band 18-27 C; water demand rises with heat
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

KATHMANDU_PRESSURE_HPA = 854.27

FEATURE_COLUMNS = [
    "temperature",
    "humidity",
    "soilMoisture",
    "pressure",
    "vpd_kpa",
    "et0_proxy",
    "heat_stress",
    "moisture_deficit",
    "dry_hot_index",
]


def saturation_vapor_pressure_kpa(temp_c: np.ndarray) -> np.ndarray:
    """Tetens formula, FAO-56 Eq. 11. Result in kPa."""
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def vapor_pressure_deficit_kpa(temp_c: np.ndarray, rh_pct: np.ndarray) -> np.ndarray:
    es = saturation_vapor_pressure_kpa(temp_c)
    return es * (1.0 - np.clip(rh_pct, 0.0, 100.0) / 100.0)


def add_agronomic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add tomato-relevant features. Keeps original sensor columns."""
    out = df.copy()
    t = out["temperature"].to_numpy(dtype=float)
    rh = out["humidity"].to_numpy(dtype=float)
    sm = out["soilMoisture"].to_numpy(dtype=float)

    if "pressure" not in out.columns:
        out["pressure"] = KATHMANDU_PRESSURE_HPA
    else:
        pressure = out["pressure"].to_numpy(dtype=float)
        out["pressure"] = np.where(pressure <= 0, KATHMANDU_PRESSURE_HPA, pressure)

    vpd = vapor_pressure_deficit_kpa(t, rh)
    et0_proxy = np.clip(0.0023 * (t + 17.8) * np.sqrt(np.maximum(t * 0.35, 0.1)) * 15.0, 0, 12)
    et0_proxy = et0_proxy * (0.6 + 0.4 * np.clip(vpd / 2.5, 0, 1))
    heat_stress = np.clip((t - 27.0) / 8.0, 0.0, 1.0)
    moisture_deficit = np.clip((60.0 - sm) / 60.0, 0.0, 1.0)
    dry_hot_index = moisture_deficit * (0.5 + 0.5 * np.clip(vpd / 2.0, 0, 1))

    out["vpd_kpa"] = vpd
    out["et0_proxy"] = et0_proxy
    out["heat_stress"] = heat_stress
    out["moisture_deficit"] = moisture_deficit
    out["dry_hot_index"] = dry_hot_index
    return out


def tomato_irrigation_label(df: pd.DataFrame) -> np.ndarray:
    """FAO-style tomato irrigation decision on 0-100 percent soil moisture.

    Management allowed depletion for tomato is about 0.40, so irrigation
    starts near 55-60 percent relative moisture. The threshold rises on
    high-VPD / hot days and falls when air is humid. Waterlogged soil is
    never irrigated.
    """
    t = df["temperature"].to_numpy(dtype=float)
    sm = df["soilMoisture"].to_numpy(dtype=float)
    vpd = df["vpd_kpa"].to_numpy(dtype=float)
    threshold = 55.0 + 10.0 * np.tanh((vpd - 1.1) / 0.7) + 5.0 * np.clip((t - 30.0) / 8.0, 0, 1)
    threshold = np.clip(threshold, 42.0, 72.0)
    return ((sm < threshold) & (sm < 88.0)).astype(int)


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """sklearn transformer stored inside the inference pipeline."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if isinstance(X, pd.DataFrame):
            frame = X.copy()
        else:
            arr = np.asarray(X, dtype=float)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            cols = ["temperature", "humidity", "soilMoisture"]
            n = arr.shape[1]
            if n >= 4:
                cols = cols + ["pressure"]
                frame = pd.DataFrame(arr[:, :4], columns=cols)
            else:
                frame = pd.DataFrame(arr[:, :3], columns=cols)
                frame["pressure"] = KATHMANDU_PRESSURE_HPA
        if "pressure" not in frame.columns:
            frame["pressure"] = KATHMANDU_PRESSURE_HPA
        frame = add_agronomic_features(frame)
        return frame[FEATURE_COLUMNS].to_numpy(dtype=float)
