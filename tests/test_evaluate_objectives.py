"""Interim-report objectives: XGBoost not LSTM."""

import pandas as pd

from src.evaluate_objectives import (
    WATER_SAVING_TARGET,
    objective_3_water,
    why_not_lstm,
)


def test_why_not_lstm_points_at_this_repo():
    reasons = why_not_lstm()
    joined = " ".join(reasons.values())
    assert "src/train.py" in joined
    assert "water_needed" in joined
    assert "timestamp" in joined.lower()


def test_calendar_water_saving_meets_thirty_percent():
    df = pd.DataFrame(
        {
            "irrigate": [1, 1, 0, 0, 0] * 20,
            "pump_historical": [1, 0, 1, 0, 1] * 20,
            "soilMoisture": [20, 40, 80, 90, 55] * 20,
        }
    )
    out = objective_3_water(df)
    assert out["saving_vs_calendar"] >= WATER_SAVING_TARGET
    assert out["status"] == "met"
    assert abs(out["model_on_fraction"] - 0.4) < 1e-9
