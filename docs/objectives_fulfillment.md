# Interim-report objectives — how this code meets them (no LSTM)

Source: `docs/Pramod_Giri_Interim_Report.pdf` §3.3. Re-score any time with:

```bash
PYTHONPATH=. python3 -m src.evaluate_objectives
```

Output: `results/objectives_evaluation.json`.

## Why not LSTM

Interim Objective 2 asked for a deep-learning **LSTM** and RMSE on a 24-hour water forecast, then TensorFlow Lite on the ESP32. That plan does not match the artefact that was built.

| Reason | Code that forces the choice |
| --- | --- |
| The pump needs **ON/OFF now**, not a 24 h volume | `api/app.py` `POST /predict` returns `water_needed` 0/1. Firmware `setRelay` in `soil_moisture.cpp`. |
| Training rows have **no timestamps** | `src/preprocess.py` + stratified 80/20 split in `src/train.py`. LSTM needs a sequence. |
| Features are **FAO-56 snapshots** (VPD, ET0 proxy, heat, moisture deficit) | `src/features.py` `FeatureEngineer` inside the saved sklearn pipeline. |
| Inference is **XGBoost joblib on this Mac**, not TFLite on-device | `models/irrigation_model.joblib` loaded by FastAPI. |
| The decision layer already **compares XGBoost, RF, SVM, and a 55% soil cutoff** | `src/train.py`. XGBoost wins F1. |

RMSE of a rainfall series is the wrong metric for a relay. This project reports **classification F1 / ROC-AUC**, and as a stand-in for interim M1, **RMSE between predicted probability and the 0/1 label** (~0.012 on the 20% split).

## Objective 1 — live ESP32 sensing

**Interim:** low-power ESP32 collecting soil moisture, temperature, humidity on a Nepalese farm.

**Code:** `aht10.cpp` (DHT11), `soil_moisture.cpp`, `bmp280.cpp`, `SmartIrrigation.ino` `POST /predict` every 15 s → `api/storage.py` → `data/live/irrigation_log.csv`.

**Evidence:** thousands of live rows with `temperature`, `humidity`, `soilMoisture` from `device_id=esp32-irrigation`.

**Still open:** almost all live soil values are 0%. Recalibrate `DRY_SOIL` / `WET_SOIL` in `soil_moisture.cpp` from Serial `Soil Raw`, or the probe is not in the soil. Temperature and humidity are arriving.

## Objective 2 — ML irrigation forecast (XGBoost, not LSTM)

**Interim:** LSTM with RMSE on a held-out set.

**Code:** `src/train.py` (`XGBClassifier`), labels from `tomato_irrigation_label` in `src/features.py`, served by `api/app.py`.

**Evidence (held-out 600 rows, from `results/train_summary.json`):**

| Model | Accuracy | F1 | ROC-AUC |
| --- | --- | --- | --- |
| **xgboost** | 0.992 | **0.993** | 1.000 |
| random_forest | 0.988 | 0.990 | 1.000 |
| svm | 0.985 | 0.987 | 0.999 |
| soil_threshold_55pct | 0.923 | 0.931 | 0.939 |

F1 target used in code: ≥ 0.90. Probability RMSE vs label ≈ 0.012.

Live learning (Phase 2 in the interim): `src/ingest_live.py` and `POST /api/learn` merge greenhouse CSV using the **same FAO labels**, not the model's previous `water_needed`.

## Objective 3 — ≥30% less water than a calendar schedule

**Interim:** 30% less water than schedule-only watering.

**Code:** model/FAO only turns the pump on when `irrigate==1` (`src/features.py`, `POST /predict`).

**Evidence on 3,000 Kathmandu rows:**

- Model ON fraction ≈ **0.583**
- Calendar baseline = always ON → saving **1 − 0.583 = 41.7%** (≥ 30%)
- Wet soil (≥75%) never irrigated: ≈ **25.7%** of rows (water a schedule would waste)
- Historical pump ON ≈ 0.523 — the tomato rule waters a bit more in heat (FAO), which is crop need, not calendar waste

## Objective 4 — correct timing (and one-zone spatial)

**Interim:** right time and spatial distribution on the monitored ground.

**Code:** ESP32 applies `water_needed` to the relay within the 8 s HTTP timeout (interim M4 was < 10 s).

**Evidence:** live log `relayStatus` matches `water_needed` on **100%** of rows. **One** `device_id` / one probe / one relay = **one tomato bed**. Multi-zone fields are out of scope (interim §3.4).

## Objective 5 — reliability in wet and dry conditions

**Interim:** uptime, sensor reachability, prediction quality across seasons (target 95% uptime).

**Code:** `/health`, `/api/status`, live CSV timestamps, `tests/test_api.py`.

**Evidence:**

- Sensor T/RH readable on ≈ **99.96%** of live rows
- Median gap between posts ≈ **16 s** (target 15 s) when the Mac and ESP32 are up
- Uptime vs a continuous 15 s schedule over the whole log span is **low** (~4%) because of long gaps (Mac asleep, Wi-Fi, older firmware that called `ESP.restart()` after Sheets)
- Wet/dry **proxy** until two real seasons exist: RH ≥ 70 vs RH ≤ 50 in the live log

Fix remaining uptime: keep this Mac awake, keep Docker/uvicorn running, use the firmware that no longer restarts after Google Sheets.

## Map to interim metrics M1–M5

| Interim metric | This repo |
| --- | --- |
| M1 RMSE / MAE | XGBoost F1 + probability RMSE vs 0/1 label |
| M2 30% water saving | ON-time vs always-on calendar |
| M3 95% uptime | timestamp gaps in `irrigation_log.csv` |
| M4 <10 s latency | 8 s firmware HTTP timeout; 15 s predict period |
| M5 wet/dry seasons | RH proxy now; full seasons need longer logs |
