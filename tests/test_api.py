"""API closed-loop checks: live sensors → XGBoost → water_needed."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import storage


@pytest.fixture()
def client(tmp_path, monkeypatch):
    log = tmp_path / "irrigation_log.csv"
    monkeypatch.setattr(storage, "LIVE_DIR", tmp_path)
    monkeypatch.setattr(storage, "LOG_CSV", log)
    from api.app import app

    return TestClient(app)


def test_health_model_loaded(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["model_loaded"] is True
    assert body["status"] == "ok"


def test_dashboard_is_farmer_page(client):
    res = client.get("/")
    assert res.status_code == 200
    text = res.text
    assert "Is it time to water?" in text
    assert "Soil water" in text


def test_predict_dry_hot_turns_pump_on(client, tmp_path):
    res = client.post(
        "/predict",
        json={
            "temperature": 32.0,
            "humidity": 40.0,
            "soilMoisture": 22.0,
            "pressure": 865,
            "device_id": "test-node",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["water_needed"] == 1
    assert body["relayStatus"] == "ON"
    assert body["model"] == "xgboost"
    assert body["headline"] == "Water the plants now"
    assert Path(tmp_path / "irrigation_log.csv").exists()

    status = client.get("/api/status").json()
    assert status["farmer"]["pump_plain"] == "Running"
    assert status["farmer"]["soil_plain"] == "Too dry"


def test_predict_wet_cool_turns_pump_off(client):
    res = client.post(
        "/predict",
        json={
            "temperature": 22.0,
            "humidity": 70.0,
            "soilMoisture": 82.0,
            "pressure": 865,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["water_needed"] == 0
    assert body["relayStatus"] == "OFF"
    assert body["headline"] == "Soil is fine — keep the pump off"


def test_learn_refuses_until_enough_rows(client):
    res = client.post("/api/learn")
    assert res.status_code == 200
    body = res.json()
    assert body["started"] is False
    assert body["live_rows"] == 0
