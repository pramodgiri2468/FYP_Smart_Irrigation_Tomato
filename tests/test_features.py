"""Sensing-to-label checks used by both training and live ingest."""

from __future__ import annotations

import pandas as pd

from src.features import FeatureEngineer, add_agronomic_features, tomato_irrigation_label
from src.ingest_live import live_to_training


def test_dry_soil_is_irrigate():
    df = add_agronomic_features(
        pd.DataFrame(
            {
                "temperature": [28.0],
                "humidity": [50.0],
                "soilMoisture": [20.0],
                "pressure": [865.0],
            }
        )
    )
    assert int(tomato_irrigation_label(df)[0]) == 1


def test_waterlogged_soil_is_not_irrigate():
    df = add_agronomic_features(
        pd.DataFrame(
            {
                "temperature": [28.0],
                "humidity": [50.0],
                "soilMoisture": [95.0],
                "pressure": [865.0],
            }
        )
    )
    assert int(tomato_irrigation_label(df)[0]) == 0


def test_feature_engineer_nine_columns():
    x = pd.DataFrame(
        {
            "temperature": [25.0],
            "humidity": [60.0],
            "soilMoisture": [50.0],
            "pressure": [865.0],
        }
    )
    out = FeatureEngineer().transform(x)
    assert out.shape == (1, 9)


def test_live_csv_becomes_training_rows(tmp_path):
    path = tmp_path / "irrigation_log.csv"
    path.write_text(
        "timestamp,device_id,temperature,humidity,soilMoisture,pressure,"
        "water_needed,irrigate,probability,relayStatus,model,reason\n"
        "2026-09-12T00:00:00+00:00,esp32,31,42,28,865,1,1,1.0,ON,xgboost,dry\n"
        "2026-09-12T00:00:15+00:00,esp32,22,70,82,865,0,0,0.0,OFF,xgboost,wet\n"
    )
    trained = live_to_training(path)
    assert len(trained) == 2
    assert set(trained["irrigate"].unique()).issubset({0, 1})
    # Live labels follow the tomato rule, not the model's previous water_needed.
    dry = trained.loc[trained["soilMoisture"] == 28].iloc[0]
    wet = trained.loc[trained["soilMoisture"] == 82].iloc[0]
    assert int(dry["irrigate"]) == 1
    assert int(wet["irrigate"]) == 0
