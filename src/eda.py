"""Exploratory data analysis for the tomato irrigation FYP."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src import DATA_PROCESSED, FIGURES_DIR, RESULTS_DIR
from src.preprocess import PROCESSED_CSV, main as preprocess_main
from src.generate_season import OUT_CSV as SEASON_CSV, main as generate_season_main

sns.set_theme(style="whitegrid", context="talk")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 11


def _save(fig: plt.Figure, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path)
    plt.close(fig)
    return path


def run_eda() -> dict:
    if not PROCESSED_CSV.exists():
        preprocess_main()
    if not SEASON_CSV.exists():
        generate_season_main()

    df = pd.read_csv(PROCESSED_CSV)
    season = pd.read_csv(SEASON_CSV, parse_dates=["timestamp"])

    numeric = [
        "temperature",
        "humidity",
        "pressure",
        "soilMoisture",
        "vpd_kpa",
        "et0_proxy",
        "pump_historical",
        "irrigate",
    ]

    summary = {
        "n_rows": int(len(df)),
        "n_features_raw": 5,
        "missing_values": {k: int(v) for k, v in df.isna().sum().items()},
        "pump_on_rate": float(df["pump_historical"].mean()),
        "tomato_irrigate_rate": float(df["irrigate"].mean()),
        "label_agreement": float((df["pump_historical"] == df["irrigate"]).mean()),
        "describe": df[numeric].describe().round(3).to_dict(),
        "correlations": df[numeric].corr().round(3).to_dict(),
        "season_rows": int(len(season)),
        "season_irrigate_rate": float(season["irrigate"].mean()),
    }

    # 1. distributions
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    cols = ["soilMoisture", "temperature", "humidity", "pressure"]
    units = ["Soil moisture (%)", "Air temperature (C)", "Relative humidity (%)", "Pressure (hPa)"]
    for ax, col, unit in zip(axes.ravel(), cols, units):
        sns.histplot(df[col], bins=30, kde=True, ax=ax, color="#2A6F97")
        ax.set_xlabel(unit)
        ax.set_ylabel("Count")
    fig.suptitle("Sensor distributions — Kathmandu IoT logs (n=3000)", y=1.02)
    _save(fig, "01_sensor_distributions.png")

    # 2. boxplots by tomato label
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, col, unit in zip(
        axes,
        ["soilMoisture", "temperature", "vpd_kpa"],
        ["Soil moisture (%)", "Air temperature (C)", "VPD (kPa)"],
    ):
        sns.boxplot(data=df, x="irrigate", y=col, hue="irrigate", ax=ax, palette=["#89C2D9", "#01497C"], legend=False)
        ax.set_xlabel("Tomato irrigate label (0/1)")
        ax.set_ylabel(unit)
    fig.suptitle("Feature spread by FAO tomato irrigation label", y=1.03)
    _save(fig, "02_boxplots_by_label.png")

    # 3. correlation heatmap
    fig, ax = plt.subplots(figsize=(9, 7))
    corr = df[numeric].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax, square=True)
    ax.set_title("Pearson correlation — sensors, FAO features, labels")
    _save(fig, "03_correlation_heatmap.png")

    # 4. soil vs pump vs tomato rule
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    sns.scatterplot(
        data=df.sample(800, random_state=42),
        x="soilMoisture",
        y="temperature",
        hue="pump_historical",
        palette=["#ADB5BD", "#C1121F"],
        ax=axes[0],
        s=22,
        alpha=0.7,
        edgecolor=None,
    )
    axes[0].set_title("Historical pump (threshold-like)")
    axes[0].set_xlabel("Soil moisture (%)")
    axes[0].set_ylabel("Air temperature (C)")
    sns.scatterplot(
        data=df.sample(800, random_state=42),
        x="soilMoisture",
        y="temperature",
        hue="irrigate",
        palette=["#ADB5BD", "#01497C"],
        ax=axes[1],
        s=22,
        alpha=0.7,
        edgecolor=None,
    )
    axes[1].set_title("FAO tomato irrigation label")
    axes[1].set_xlabel("Soil moisture (%)")
    fig.suptitle("Historical pump vs tomato-specific irrigation decision", y=1.03)
    _save(fig, "04_soil_temp_decision_scatter.png")

    # 5. VPD vs moisture
    fig, ax = plt.subplots(figsize=(8, 5.5))
    sns.scatterplot(
        data=df.sample(900, random_state=42),
        x="soilMoisture",
        y="vpd_kpa",
        hue="irrigate",
        palette=["#ADB5BD", "#01497C"],
        ax=ax,
        s=24,
        alpha=0.75,
        edgecolor=None,
    )
    ax.set_xlabel("Soil moisture (%)")
    ax.set_ylabel("Vapor pressure deficit (kPa)")
    ax.set_title("Irrigation need rises when soil is dry and VPD is high")
    _save(fig, "05_soil_vpd_scatter.png")

    # 6. class balance
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, col, title in zip(
        axes,
        ["pump_historical", "irrigate"],
        ["Historical pump ON/OFF", "Tomato irrigate label"],
    ):
        counts = df[col].value_counts().sort_index()
        ax.bar(["OFF (0)", "ON (1)"], counts.values, color=["#89C2D9", "#01497C"])
        ax.set_ylabel("Count")
        ax.set_title(title)
        for i, v in enumerate(counts.values):
            ax.text(i, v + 20, f"{v} ({v/len(df):.1%})", ha="center", fontsize=10)
    fig.suptitle("Class balance", y=1.03)
    _save(fig, "06_class_balance.png")

    # 7. season time series (7-day window)
    window = season.iloc[: 96 * 7]
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    axes[0].plot(window["timestamp"], window["temperature"], color="#C1121F", lw=1)
    axes[0].set_ylabel("Temp (C)")
    axes[1].plot(window["timestamp"], window["soilMoisture"], color="#2A6F97", lw=1)
    axes[1].set_ylabel("Soil moisture (%)")
    axes[2].fill_between(
        window["timestamp"],
        0,
        window["irrigate"],
        color="#01497C",
        step="mid",
        alpha=0.7,
    )
    axes[2].set_ylabel("Irrigate")
    axes[2].set_xlabel("Timestamp")
    fig.suptitle("Simulated Kathmandu tomato week (15-min ESP32 interval)", y=1.01)
    _save(fig, "07_season_week_timeseries.png")

    # 8. growth stage
    fig, ax = plt.subplots(figsize=(8, 4.8))
    rates = season.groupby("growth_stage", observed=False)["irrigate"].mean()
    ax.bar(rates.index.astype(str), rates.values, color="#2A6F97")
    ax.set_ylabel("Fraction of intervals labeled irrigate")
    ax.set_xlabel("FAO tomato growth stage")
    ax.set_title("Irrigation frequency by crop stage (Kc 0.60 → 1.15 → 0.80)")
    _save(fig, "08_irrigation_by_growth_stage.png")

    # 9. pairplot-style kde of key vars
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.kdeplot(data=df, x="soilMoisture", hue="irrigate", fill=True, common_norm=False, ax=ax, palette=["#89C2D9", "#01497C"])
    ax.set_xlabel("Soil moisture (%)")
    ax.set_title("Soil moisture density by tomato irrigation label")
    _save(fig, "09_soil_moisture_kde.png")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = RESULTS_DIR / "eda_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"EDA complete. Figures in {FIGURES_DIR}")
    print(f"Summary: {summary_path}")
    return summary


if __name__ == "__main__":
    run_eda()
