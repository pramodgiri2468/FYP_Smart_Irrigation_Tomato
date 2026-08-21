"""Smart Irrigation for Tomato — ML pipeline package."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
RANDOM_SEED = 42
SENSOR_COLUMNS = ["temperature", "humidity", "soilMoisture"]
TARGET_COLUMN = "irrigate"
RELAY_COLUMN = "relayStatus"
