# Smart Irrigation for Tomato

Final-year project: an ESP32 farm node (DHT11 + BMP280 + capacitive soil probe + relay/pump) talks to a **local FastAPI service on this Mac**. The service logs every reading to CSV, runs the trained **XGBoost** model, and returns `water_needed` (1 = pump ON, 0 = OFF). A farmer dashboard reads that same log. No AWS EC2.

## Architecture

Tomato farm / IoT layer on the left, local Docker deployment on this MacBook on the right. HTTP JSON is the only link.

![Smart Irrigation Tomato — local deployment](docs/deployment-architecture.png)

```mermaid
flowchart LR
  subgraph farm["Tomato farm / IoT"]
    bmp[BMP280 pressure]
    dht[DHT11 temp / RH]
    soil[Soil moisture]
    esp[ESP32]
    pump[Irrigation pump]
    bmp --> esp
    dht --> esp
    soil --> esp
    pump -.-> soil
  end

  esp -->|"Wi-Fi HTTP JSON"| api
  api -->|"water_needed 1/0"| pump

  subgraph mac["This Mac — Docker"]
    api[FastAPI REST]
    csv[CSV local storage]
    prep[Preprocess + FAO-56]
    model[XGBoost / RF / SVM]
    dash[Web dashboard]
    farmer[Farmer]
    api --> csv
    api --> prep --> model
    model --> api
    csv --> dash
    model --> dash
    dash --> farmer
  end
```

| Side | Block | What it does |
| --- | --- | --- |
| Farm | BMP280, DHT11, soil probe | Pressure, temperature, humidity, soil moisture |
| Farm | ESP32 | Packs JSON, `POST /predict` every 15 s, drives the relay |
| Farm | Pump | ON/OFF from `water_needed`; watered soil is the feedback |
| Mac | Docker + FastAPI | Receives JSON, writes CSV, runs the model |
| Mac | Trained model | Production artefact: XGBoost in `models/irrigation_model.joblib` |
| Mac | Web dashboard | `/` — live sensors, pump, decision log for the farmer |

If FastAPI is unreachable, the ESP32 falls back to pump ON only when `soilMoisture <= 0`. Training still uses the 3,000 Kathmandu logs under `data/raw/`. Live operation uses `data/live/irrigation_log.csv`.

## Folder structure

The Arduino sketch stays in one folder so it still compiles. Sensor drivers, Wi-Fi, and the relay therefore live with the ESP32 even though they belong to different layers.

```
Smart-Irrigation-Tomato/
│
├── docs/
│   ├── deployment-architecture.png      # farm IoT + local Mac Docker
│   └── system-architecture.png          # earlier six-layer sketch
│
├── Sensor_reading_arduino/              # farm / IoT layer
│   ├── aht10.cpp                        # DHT11 temperature & humidity
│   ├── bmp280.cpp                       # BMP280 pressure (I2C)
│   ├── soil_moisture.cpp                # soil probe + relay / pump
│   └── SmartIrrigation.ino              # Wi-Fi, POST /predict, fallback
│
├── data/
│   ├── raw/                             # Kathmandu workbook (training)
│   ├── processed/                       # model-ready CSV
│   └── live/                            # irrigation_log.csv from the API
│
├── src/                                 # preprocess, FAO-56 features, train
├── notebooks/
├── api/                                 # FastAPI + farmer dashboard
│   ├── app.py
│   ├── storage.py
│   └── static/                          # dashboard HTML / CSS / JS
├── models/                              # irrigation_model.joblib (XGBoost)
├── results/
│
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

| System piece | Folder / file |
| --- | --- |
| Farm sensors | `aht10.cpp`, `bmp280.cpp`, `soil_moisture.cpp` |
| ESP32 + Wi-Fi | `SmartIrrigation.ino` |
| Pump / relay | `soil_moisture.cpp` (`setRelay`) |
| FastAPI + CSV | `api/app.py`, `api/storage.py`, `data/live/` |
| Farmer dashboard | `api/static/` at `GET /` |
| Trained model | `models/irrigation_model.joblib` |

## Hardware

Firmware lives in `Sensor_reading_arduino/`.

| Device | Role | Pin |
| --- | --- | --- |
| ESP32 | Wi-Fi node, JSON to FastAPI, relay | — |
| DHT11 | Air temperature and relative humidity | GPIO 4 |
| BMP280 | Atmospheric pressure (I2C) | SDA GPIO 8, SCL GPIO 9 |
| Capacitive soil moisture | Analog moisture (AO) | GPIO 20 |
| Capacitive soil moisture | Digital threshold (DO) | GPIO 36 |
| Relay (active-low) | Pump ON/OFF | GPIO 1 |

- Soil ADC is 12-bit. Dry calibration is 3800; wet is 1400. Moisture is mapped to 0–100 %.
- Samples every 2 s; `POST /predict` every 15 s. Pump follows `water_needed`.
- If the BMP280 is missing, firmware sends `pressure: 0` and the API uses the Kathmandu mean (854.27 hPa).
- Arduino Library Manager: **DHT sensor library**, **Adafruit BMP280 Library**, **Adafruit Unified Sensor**.

## Dataset

`data/raw/Soil_Moisture_Temp_Humidity_Pressure_MotorOnOff.xlsx` — 3,000 Kathmandu field readings:

| Column | Role |
| --- | --- |
| Soil Moisture | Analog probe (converted to 0–100 %) |
| Temperature | Air temperature (°C) |
| Air Humidity | Relative humidity (%) |
| Atmospheric Pressure (Kathmandu) | Air pressure (hPa) |
| Pump Data | Historical pump ON/OFF |

`data/processed/tomato_season_simulated.csv` is a FAO-56 soil-water-balance simulation of a Kathmandu spring tomato crop at the same 15-minute interval as the ESP32 uploader. It is used only for time-series EDA (diurnal cycle and growth stages). **The production model is trained on the 3,000 real logs.**

## Irrigation target

The historical pump column is close to a single soil-moisture threshold. The project label `irrigate` is a tomato-specific rule:

- management allowed depletion ≈ 0.40 (FAO-56 tomato)
- irrigate sooner on high vapor-pressure deficit or heat stress
- do not irrigate waterlogged soil

Engineered features (Tetens VPD, ET0 proxy, heat stress, moisture deficit) live in `src/features.py` and are applied both at training time and inside the saved sklearn pipeline.

## What the data shows (EDA)

Walkthrough with captions: [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb). Rebuild figures with `PYTHONPATH=. python3 -m src.eda`.

| Finding | In plain English |
| --- | --- |
| 3,000 complete rows | No missing values; pressure 845–865 hPa matches Kathmandu, not sea level |
| Old pump ≈ soil switch | Correlation with soil moisture ≈ −0.85; heat and humidity were ignored |
| Tomato FAO label | Water near 55–60% moisture, sooner if air is hot/dry (high VPD), never if soil is waterlogged |
| They match 92.2% of the time | 207 extra “water now” decisions in heat; 26 times the tomato rule holds back |
| Soil buckets | Dry (0–30%): always irrigate. Wet (75–100%): never. The 55–75% band is where climate matters |
| No timestamps on the logs | Use a stratified 80/20 split; the simulated season is EDA-only |

Easy plots (titles are the finding, not the chart type):

- `results/figures/15_mean_by_label.png` — irrigate vs don’t, four averages
- `results/figures/16_irrigate_rate_by_soil_bin.png` — dry / low / OK / wet
- `results/figures/17_pump_vs_tomato_agreement.png` — 2×2 agreement
- `results/figures/19_what_predicts_irrigation.png` — pump follows soil only
- `results/figures/23_soil_temp_irrigate_heatmap.png` — dry+hot → water

## Setup

Python 3.12 is recommended (the Docker image uses `python:3.12-slim`).

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Place the raw workbook at `data/raw/Soil_Moisture_Temp_Humidity_Pressure_MotorOnOff.xlsx` before preprocessing.

## Pipeline

```bash
python3 -m src.preprocess
python3 -m src.generate_season
python3 -m src.eda
PYTHONPATH=. python3 -m src.train
```

| Command | What it does |
| --- | --- |
| `src.preprocess` | Loads the workbook, maps ADC to 0–100 %, adds agronomic features, writes tomato labels |
| `src.generate_season` | FAO-56 Kathmandu spring simulation (EDA only) |
| `src.eda` | Easy-read figures 01–09 and 15–23 plus `results/eda_summary.json` |
| `src.train` | Compares XGBoost, Random Forest, and RBF SVM; saves the best pipeline |

Outputs:

- `data/processed/tomato_irrigation.csv`
- `data/processed/tomato_season_simulated.csv`
- `results/figures/` — EDA (including soil bins, agreement, climate heatmap), ROC, F1, three-model comparison
- `results/model_leaderboard.csv`
- `models/irrigation_model.joblib` (XGBoost)

Notebooks (same analysis, for the report/viva):

- `notebooks/01_eda.ipynb` — EDA only; runs in Google Colab without training or the API ([Open in Colab](https://colab.research.google.com/github/pramodgiri2468/FYP_Smart_Irrigation_Tomato/blob/main/notebooks/01_eda.ipynb))
- `notebooks/02_model_training.ipynb`

## Results

Held-out test set (600 rows). The Decision layer compares three classifiers against a 55 % soil-moisture cutoff. **XGBoost** is saved for the API.

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | 5-fold CV F1 |
| --- | --- | --- | --- | --- | --- | --- |
| **xgboost** | **0.992** | 0.989 | **0.997** | **0.993** | **1.000** | **0.993** |
| random_forest | 0.988 | **0.994** | 0.986 | 0.990 | 1.000 | 0.990 |
| svm | 0.985 | 0.989 | 0.986 | 0.987 | 0.999 | 0.986 |
| soil_threshold_55pct | 0.923 | 0.987 | 0.880 | 0.931 | 0.939 | — |

- **XGBoost** — best F1 and recall; production model in `models/irrigation_model.joblib`
- **Random Forest** — highest precision; close second
- **RBF SVM** — scaled features + calibrated probabilities; still well above the moisture-only baseline

All three learned models beat the agronomic 55 % cutoff by using vapor-pressure deficit and heat as well as soil moisture.

![Test F1 by model](results/figures/13_f1_leaderboard.png)

![XGBoost vs SVM vs Random Forest](results/figures/14_model_comparison.png)

## Deploy on this PC (no AWS)

The model file is `models/irrigation_model.joblib`. You serve it with FastAPI on **this computer**. Nothing is uploaded to EC2 or any cloud GPU.

**Option A — Docker (recommended).** Docker Desktop must be running (whale icon in the menu bar).

```bash
cd ~/Desktop/Smart-Irrigation-Tomato
open -a Docker          # skip if already running
docker compose up -d --build
```

Check: farmer dashboard http://127.0.0.1:8000/ — health JSON http://127.0.0.1:8000/health

If you see `Bind for 0.0.0.0:8000 failed: port is already allocated`, the API is **already up**. Do not run `docker run ...` as well. Use:

```bash
docker compose ps
docker compose logs -f api
```

Stop it with `docker compose down`.

**Option B — Python venv (no Docker).** Use this if Docker is not running. Stop Option A first so port 8000 is free.

```bash
cd ~/Desktop/Smart-Irrigation-Tomato
source .venv/bin/activate
PYTHONPATH=. python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` lets the ESP32 on the same Wi-Fi call this Mac. `--reload` is only for development.

Do not prefix the command with `. ` (bash `source`). That tries to run the uvicorn file as a shell script and fails.

**Call it from another device (ESP32 / phone).** Find this Mac’s LAN IP (System Settings → Network, or `ipconfig getifaddr en0`). Example:

```bash
curl -sS http://192.168.1.79:8000/health
curl -sS -X POST http://192.168.1.79:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"temperature":29.2,"humidity":48.0,"soilMoisture":38.5,"pressure":0}'
```

Keep the Mac awake and on the same Wi-Fi as the ESP32. macOS Firewall (System Settings → Network → Firewall) must allow incoming connections on port 8000. This is a home/LAN service, not a public internet deployment.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Farmer dashboard |
| GET | `/health` | Model file present or degraded |
| POST | `/predict` | Irrigation decision + CSV log |
| GET | `/api/status` | Latest reading and pump state |
| GET | `/api/logs` | Recent CSV rows as JSON |
| GET | `/api/logs.csv` | Download the live log |
| GET | `/docs` | Interactive OpenAPI UI |

### `POST /predict`

Request (ESP32-compatible field names):

```json
{
  "temperature": 29.2,
  "humidity": 48.0,
  "soilMoisture": 38.5,
  "pressure": 0
}
```

`pressure` of `0` or omitted is treated as missing and replaced with 854.27 hPa.

Example response:

```json
{
  "water_needed": 1,
  "irrigate": true,
  "probability": 0.97,
  "relayStatus": "ON",
  "targetValue": 100.0,
  "model": "xgboost",
  "logged": true,
  "reasons": [
    "Soil moisture is below the tomato readily-available-water band."
  ]
}
```

`water_needed` is `1` (pump ON) or `0` (pump OFF). Every call is appended to `data/live/irrigation_log.csv`.

## Firmware configuration

Edit `Sensor_reading_arduino/SmartIrrigation.ino` before flashing:

- `WIFI_SSID` / `WIFI_PASS` — same Wi-Fi as this Mac
- `API_HOST` — this Mac’s LAN IP (`ipconfig getifaddr en0`), default port 8000

Install the three Adafruit/DHT libraries, wire BMP280 to GPIO 8/9 (or change `BMP_SDA` / `BMP_SCL` in `bmp280.cpp`), then flash. Keep Docker Compose running so `/predict` is reachable. Do not commit real passwords.
