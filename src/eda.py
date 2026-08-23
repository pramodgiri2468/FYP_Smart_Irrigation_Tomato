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
    ax.axvline(55, color="#C1121F", ls="--", lw=1.4, label="55% FAO start band")
    ax.set_xlabel("Soil moisture (%)")
    ax.set_title("When soil is dry the tomato rule says irrigate")
    ax.legend(title="Irrigate", fontsize=9)
    _save(fig, "09_soil_moisture_kde.png")

    irrigate_map = {0: "Don't irrigate", 1: "Irrigate"}
    df = df.copy()
    df["irrigate_name"] = df["irrigate"].map(irrigate_map)
    df["pump_name"] = df["pump_historical"].map({0: "Pump OFF", 1: "Pump ON"})
    df["soil_band"] = pd.cut(
        df["soilMoisture"],
        bins=[-0.1, 30, 55, 75, 100.1],
        labels=["Dry (0–30%)", "Low (30–55%)", "OK (55–75%)", "Wet (75–100%)"],
    )
    disagree_pump_on = int(((df["pump_historical"] == 1) & (df["irrigate"] == 0)).sum())
    disagree_pump_off = int(((df["pump_historical"] == 0) & (df["irrigate"] == 1)).sum())

    # 15. average sensors: irrigate vs not (easy comparison)
    mean_cols = ["soilMoisture", "temperature", "humidity", "vpd_kpa"]
    means = df.groupby("irrigate_name")[mean_cols].mean().reindex(["Don't irrigate", "Irrigate"])
    fig, axes = plt.subplots(1, 4, figsize=(14, 4.2))
    titles = [
        ("soilMoisture", "Soil moisture (%)", "Drier soil → irrigate"),
        ("temperature", "Air temperature (°C)", "Warmer air → more water use"),
        ("humidity", "Humidity (%)", "Drier air → irrigate sooner"),
        ("vpd_kpa", "VPD (kPa)", "High VPD = thirsty air"),
    ]
    colors = ["#89C2D9", "#01497C"]
    for ax, (col, ylabel, subtitle) in zip(axes, titles):
        ax.bar(means.index, means[col], color=colors)
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle, fontsize=10)
        ax.tick_params(axis="x", labelrotation=15)
        for i, val in enumerate(means[col]):
            ax.text(i, val, f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("Simple picture: what is different when we irrigate?", y=1.05)
    _save(fig, "15_mean_by_label.png")

    # 16. irrigation rate by soil band
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    rates = df.groupby("soil_band", observed=False)["irrigate"].mean()
    counts = df.groupby("soil_band", observed=False)["irrigate"].size()
    bars = ax.bar(rates.index.astype(str), rates.values, color="#2A6F97")
    ax.set_ylabel("Share of rows labeled irrigate")
    ax.set_xlabel("How wet is the soil?")
    ax.set_ylim(0, 1.15)
    ax.set_title("Dry soil almost always needs water; wet soil almost never does")
    for bar, rate, n in zip(bars, rates.values, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, rate + 0.03, f"{rate:.0%}\n(n={n})", ha="center", va="bottom", fontsize=9)
    _save(fig, "16_irrigate_rate_by_soil_bin.png")

    # 17. pump vs tomato agreement (2x2)
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ct = pd.crosstab(df["pump_name"], df["irrigate_name"])
    ct = ct.reindex(index=["Pump OFF", "Pump ON"], columns=["Don't irrigate", "Irrigate"])
    sns.heatmap(ct, annot=True, fmt="d", cmap="Blues", ax=ax, cbar=False)
    ax.set_xlabel("Tomato FAO label")
    ax.set_ylabel("Historical pump")
    ax.set_title(f"Same decision on {summary['label_agreement']:.1%} of rows\nDisagreements are the FYP improvement")
    _save(fig, "17_pump_vs_tomato_agreement.png")

    # 18. only the disagreements
    mismatch = df.copy()
    mismatch["story"] = "Agree"
    mismatch.loc[(mismatch["pump_historical"] == 1) & (mismatch["irrigate"] == 0), "story"] = (
        "Pump watered, tomato says skip"
    )
    mismatch.loc[(mismatch["pump_historical"] == 0) & (mismatch["irrigate"] == 1), "story"] = (
        "Pump skipped, tomato says water"
    )
    mismatch = mismatch[mismatch["story"] != "Agree"]
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    sns.scatterplot(
        data=mismatch,
        x="soilMoisture",
        y="vpd_kpa",
        hue="story",
        palette=["#C1121F", "#2A6F97"],
        ax=ax,
        s=36,
        alpha=0.8,
        edgecolor=None,
    )
    ax.set_xlabel("Soil moisture (%)")
    ax.set_ylabel("Vapor pressure deficit (kPa)")
    ax.set_title("Where the old pump and the tomato rule disagree")
    ax.legend(title="", fontsize=8, loc="upper right")
    _save(fig, "18_label_disagreements.png")

    # 19. what actually predicts irrigation (easy bar, not a heatmap)
    corr_cols = [
        "soilMoisture",
        "temperature",
        "humidity",
        "pressure",
        "vpd_kpa",
        "et0_proxy",
        "heat_stress",
        "moisture_deficit",
        "dry_hot_index",
    ]
    corr_irrigate = df[corr_cols].corrwith(df["irrigate"]).sort_values()
    corr_pump = df[corr_cols].corrwith(df["pump_historical"]).reindex(corr_irrigate.index)
    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    y = np.arange(len(corr_irrigate))
    ax.barh(y - 0.18, corr_pump.values, height=0.36, color="#ADB5BD", label="Historical pump")
    ax.barh(y + 0.18, corr_irrigate.values, height=0.36, color="#01497C", label="Tomato irrigate label")
    ax.set_yticks(y)
    ax.set_yticklabels(corr_irrigate.index)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel("Correlation (closer to −1 or +1 = stronger link)")
    ax.set_title("Pump follows soil only; tomato label also follows climate")
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, "19_what_predicts_irrigation.png")

    # 20. engineered features in plain language
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4))
    feat_specs = [
        ("vpd_kpa", "VPD (kPa)", "How thirsty is the air?"),
        ("heat_stress", "Heat stress (0–1)", "How far above 27 °C?"),
        ("dry_hot_index", "Dry-hot index (0–1)", "Dry soil × thirsty air"),
    ]
    for ax, (col, ylabel, title) in zip(axes, feat_specs):
        sns.boxplot(
            data=df,
            x="irrigate_name",
            y=col,
            hue="irrigate_name",
            ax=ax,
            palette=["#89C2D9", "#01497C"],
            legend=False,
        )
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=11)
        ax.tick_params(axis="x", labelrotation=12)
    fig.suptitle("FAO-56 features: extra climate signal the old pump ignored", y=1.04)
    _save(fig, "20_engineered_features.png")

    # 21. hour of day from simulated season
    season = season.copy()
    season["hour"] = season["timestamp"].dt.hour
    hourly = season.groupby("hour")["irrigate"].mean()
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.bar(hourly.index, hourly.values, color="#2A6F97")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Share of 15-min slots labeled irrigate")
    ax.set_title("Simulated season: irrigation is a morning job (cooler, less waste)")
    ax.set_xticks(range(0, 24, 2))
    _save(fig, "21_hourly_irrigation_season.png")

    # 22. tomato comfort band on temp vs humidity
    sample = df.sample(900, random_state=42)
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    sns.scatterplot(
        data=sample,
        x="temperature",
        y="humidity",
        hue="irrigate_name",
        palette=["#ADB5BD", "#01497C"],
        ax=ax,
        s=22,
        alpha=0.7,
        edgecolor=None,
    )
    ax.axvspan(18, 27, color="#2A9D8F", alpha=0.12, label="Tomato comfort 18–27 °C")
    ax.set_xlabel("Air temperature (°C)")
    ax.set_ylabel("Relative humidity (%)")
    ax.set_title("Tomatoes like 18–27 °C; hotter air usually means irrigate more")
    ax.legend(fontsize=8)
    _save(fig, "22_temp_humidity_comfort.png")

    # 23. soil × temperature irrigate rate heatmap
    df["temp_band"] = pd.cut(
        df["temperature"],
        bins=[17, 24, 30, 35, 40],
        labels=["Cool\n18–24 °C", "Mild\n24–30 °C", "Warm\n30–35 °C", "Hot\n35–40 °C"],
    )
    heat = (
        df.groupby(["temp_band", "soil_band"], observed=False)["irrigate"]
        .mean()
        .unstack()
    )
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    sns.heatmap(heat, annot=True, fmt=".0%", cmap="Blues", vmin=0, vmax=1, ax=ax)
    ax.set_xlabel("Soil moisture band")
    ax.set_ylabel("Air temperature band")
    ax.set_title("Read this like a table: dry + hot → irrigate; wet → don't")
    _save(fig, "23_soil_temp_irrigate_heatmap.png")

    band_rates = {str(k): float(v) for k, v in rates.items()}
    summary.update(
        {
            "plain_language": {
                "rows": "3,000 Kathmandu sensor logs. No missing values.",
                "pressure": "845–865 hPa matches Kathmandu (~1,400 m), not sea level.",
                "pump": "Old pump is almost a soil-moisture switch (corr ≈ −0.85).",
                "tomato_label": "FAO tomato rule also uses heat and dry air (VPD).",
                "agreement": f"Pump and tomato label match on {summary['label_agreement']:.1%} of rows.",
                "disagreements": (
                    f"{disagree_pump_off} times the tomato rule waters when the pump did not; "
                    f"{disagree_pump_on} times it holds back when the pump ran."
                ),
                "soil_bands": band_rates,
                "model_target": "Train on irrigate, not pump_historical.",
            },
            "disagree_pump_on_tomato_off": disagree_pump_on,
            "disagree_pump_off_tomato_on": disagree_pump_off,
        }
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = RESULTS_DIR / "eda_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"EDA complete. Figures in {FIGURES_DIR}")
    print(f"Summary: {summary_path}")
    for line in summary["plain_language"].values():
        if isinstance(line, str):
            print(" -", line)
    return summary


if __name__ == "__main__":
    run_eda()
