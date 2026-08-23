"""Train and compare irrigation classifiers. Saves the best model for the API."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from src import FIGURES_DIR, MODELS_DIR, RANDOM_SEED, RESULTS_DIR
from src.features import FEATURE_COLUMNS, FeatureEngineer
from src.preprocess import PROCESSED_CSV, main as preprocess_main

sns.set_theme(style="whitegrid", context="talk")


def metrics_dict(y_true, y_pred, y_prob) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
    }


def soil_threshold_predict(soil: np.ndarray, cut: float = 55.0) -> np.ndarray:
    return (soil < cut).astype(int)


def build_models() -> dict:
    """Compare XGBoost, SVM, and Random Forest on the tomato irrigation label."""
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "svm": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    CalibratedClassifierCV(
                        SVC(
                            kernel="rbf",
                            C=1.0,
                            gamma="scale",
                            class_weight="balanced",
                            random_state=RANDOM_SEED,
                        ),
                        method="sigmoid",
                        ensemble=False,
                        cv=5,
                    ),
                ),
            ]
        ),
        "xgboost": XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
    }


def plot_confusion(cm, title, path):
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        ax=ax,
        xticklabels=["No irrigate", "Irrigate"],
        yticklabels=["No irrigate", "Irrigate"],
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_roc(curves: dict, path: Path):
    fig, ax = plt.subplots(figsize=(7.2, 5.5))
    for name, (fpr, tpr, auc) in curves.items():
        ax.plot(fpr, tpr, lw=2, label=f"{name} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="#ADB5BD", lw=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curves — tomato irrigation models")
    ax.legend(fontsize=9, loc="lower right")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_importance(names, values, title, path):
    order = np.argsort(values)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(np.array(names)[order], np.array(values)[order], color="#01497C")
    ax.set_xlabel("Importance")
    ax.set_title(title)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def train() -> dict:
    if not PROCESSED_CSV.exists():
        preprocess_main()
    df = pd.read_csv(PROCESSED_CSV)
    y = df["irrigate"].to_numpy(dtype=int)
    X_sensor = df[["temperature", "humidity", "soilMoisture", "pressure"]]

    engineer = FeatureEngineer()
    X = pd.DataFrame(engineer.transform(X_sensor), columns=FEATURE_COLUMNS)

    X_train, X_test, y_train, y_test, soil_train, soil_test = train_test_split(
        X,
        y,
        df["soilMoisture"].to_numpy(),
        test_size=0.2,
        stratify=y,
        random_state=RANDOM_SEED,
    )

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    leaderboard = []
    roc_curves = {}
    fitted = {}

    # agronomic threshold baseline (not an sklearn model)
    y_thr = soil_threshold_predict(soil_test)
    thr_prob = np.clip((55.0 - soil_test) / 55.0, 0, 1)
    thr_metrics = metrics_dict(y_test, y_thr, thr_prob)
    thr_metrics["model"] = "soil_threshold_55pct"
    thr_metrics["cv_f1_mean"] = None
    leaderboard.append(thr_metrics)
    fpr, tpr, _ = roc_curve(y_test, thr_prob)
    roc_curves["soil_threshold_55pct"] = (fpr, tpr, thr_metrics["roc_auc"])

    for name, model in build_models().items():
        cv_f1 = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1")
        model.fit(X_train, y_train)
        fitted[name] = model
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X_test)[:, 1]
        else:
            prob = model.predict(X_test).astype(float)
        pred = (prob >= 0.5).astype(int)
        row = metrics_dict(y_test, pred, prob)
        row["model"] = name
        row["cv_f1_mean"] = float(cv_f1.mean())
        row["cv_f1_std"] = float(cv_f1.std())
        leaderboard.append(row)
        fpr, tpr, _ = roc_curve(y_test, prob)
        roc_curves[name] = (fpr, tpr, row["roc_auc"])
        print(f"{name:24s}  f1={row['f1']:.3f}  auc={row['roc_auc']:.3f}  cv_f1={cv_f1.mean():.3f}")

    table = pd.DataFrame(leaderboard).sort_values("f1", ascending=False)
    table.to_csv(RESULTS_DIR / "model_leaderboard.csv", index=False)

    best_name = None
    for _, row in table.iterrows():
        if row["model"] != "soil_threshold_55pct":
            best_name = row["model"]
            break
    if best_name is None:
        raise RuntimeError("No sklearn model produced a leaderboard row.")
    best_model = fitted[best_name]

    pipe = Pipeline([("features", FeatureEngineer()), ("clf", best_model)])
    # refit on full data so the API sees all labeled examples
    pipe.fit(X_sensor, y)
    model_path = MODELS_DIR / "irrigation_model.joblib"
    joblib.dump(
        {
            "pipeline": pipe,
            "model_name": best_name,
            "feature_columns": FEATURE_COLUMNS,
            "target": "irrigate",
            "metrics": table.set_index("model").to_dict(orient="index")[best_name],
        },
        model_path,
    )

    # plots for the held-out test split of the selected sklearn model
    test_model = fitted[best_name]
    prob = test_model.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)
    plot_confusion(
        confusion_matrix(y_test, pred),
        f"Confusion matrix — {best_name} (test)",
        FIGURES_DIR / "10_confusion_matrix.png",
    )
    plot_roc(roc_curves, FIGURES_DIR / "11_roc_curves.png")

    importances = None
    inner = test_model[-1] if hasattr(test_model, "named_steps") else test_model
    if hasattr(inner, "feature_importances_"):
        importances = inner.feature_importances_
    elif hasattr(inner, "coef_"):
        importances = np.abs(inner.coef_.ravel())
    if importances is not None:
        plot_importance(
            FEATURE_COLUMNS,
            importances,
            f"Feature importance — {best_name}",
            FIGURES_DIR / "12_feature_importance.png",
        )
    else:
        perm = permutation_importance(
            test_model,
            X_test.to_numpy(),
            y_test,
            n_repeats=15,
            random_state=RANDOM_SEED,
            scoring="f1",
        )
        plot_importance(
            FEATURE_COLUMNS,
            perm.importances_mean,
            f"Permutation importance (F1 drop) — {best_name}",
            FIGURES_DIR / "12_feature_importance.png",
        )

    # comparison bar chart
    fig, ax = plt.subplots(figsize=(9, 5))
    plot_df = table.copy()
    sns.barplot(data=plot_df, x="f1", y="model", ax=ax, color="#01497C")
    ax.set_xlabel("Test F1")
    ax.set_ylabel("Model")
    ax.set_title("Tomato irrigation — test F1 by model")
    fig.savefig(FIGURES_DIR / "13_f1_leaderboard.png", bbox_inches="tight")
    plt.close(fig)

    compare = table[table["model"].isin(["xgboost", "svm", "random_forest"])].copy()
    melted = compare.melt(
        id_vars="model",
        value_vars=["accuracy", "precision", "recall", "f1", "roc_auc"],
        var_name="metric",
        value_name="score",
    )
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    sns.barplot(data=melted, x="metric", y="score", hue="model", ax=ax)
    ax.set_ylim(0.95, 1.001)
    ax.set_xlabel("Metric")
    ax.set_ylabel("Test score")
    ax.set_title("XGBoost vs SVM vs Random Forest")
    ax.legend(title="Model", loc="lower right")
    fig.savefig(FIGURES_DIR / "14_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    report = classification_report(y_test, pred, target_names=["no_irrigate", "irrigate"])
    (RESULTS_DIR / "classification_report.txt").write_text(report)

    # Second experiment: clone the historical pump (mostly a soil threshold)
    y_pump = df["pump_historical"].to_numpy(dtype=int)
    Xp_train, Xp_test, yp_train, yp_test = train_test_split(
        X, y_pump, test_size=0.2, stratify=y_pump, random_state=RANDOM_SEED
    )
    pump_rows = []
    for name, factory in build_models().items():
        model = factory
        model.fit(Xp_train, yp_train)
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(Xp_test)[:, 1]
        else:
            prob = model.predict(Xp_test).astype(float)
        pred = (prob >= 0.5).astype(int)
        row = metrics_dict(yp_test, pred, prob)
        row["model"] = name
        pump_rows.append(row)
    pump_table = pd.DataFrame(pump_rows).sort_values("f1", ascending=False)
    pump_table.to_csv(RESULTS_DIR / "pump_leaderboard.csv", index=False)

    payload = {
        "best_model": best_name,
        "model_path": str(model_path),
        "test_size": int(len(y_test)),
        "leaderboard": table.to_dict(orient="records"),
        "historical_pump_leaderboard": pump_table.to_dict(orient="records"),
        "classification_report": report,
    }
    (RESULTS_DIR / "train_summary.json").write_text(json.dumps(payload, indent=2))
    print(f"\nBest model: {best_name}")
    print(f"Saved {model_path}")
    return payload


if __name__ == "__main__":
    train()
