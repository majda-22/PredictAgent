from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.esp32_feature_mapper import (
    REDUCED_FEATURE_COLUMNS,
    RATIO_FEATURES,
    build_reduced_features_from_dataset,
)


NEW_NORMAL_FILE = Path("data/clean/clean_data_new.csv")
OLD_LABELED_FILE = Path("data/clean/clean_data.csv")
MODEL_FILE = Path("models/model_reduced.pkl")
SCALER_FILE = Path("models/scaler_reduced.pkl")
VIB_SCALER_FILE = Path("models/vib_scaler.pkl")
FEATURE_COLUMNS_FILE = Path("models/reduced_feature_columns.joblib")
RATIO_CLIP_BOUNDS_FILE = Path("models/reduced_ratio_clip_bounds.joblib")
THRESHOLD_FILE = Path("models/reduced_threshold.npy")
REPORT_FILE = Path("reports/reduced_model_evaluation.csv")
RANDOM_STATE = 42
CONTAMINATION = 0.05


def print_regime_check(features: pd.DataFrame, labels: pd.Series) -> None:
    print("\n-- Regime check before training --")
    for column in ["current_per_rpm", "power_per_rpm", "temp_per_current"]:
        normal_values = features.loc[labels == 0, column]
        anomaly_values = features.loc[labels == 1, column]
        normal_mean = normal_values.mean()
        normal_std = normal_values.std()
        anomaly_mean = anomaly_values.mean()
        separation = abs(anomaly_mean - normal_mean) / (normal_std + 1e-9)
        print(f"{column}:")
        print(f"  normal:  {normal_mean:.5f} +/- {normal_std:.5f}")
        print(f"  anomaly: {anomaly_mean:.5f}")
        print(f"  separation: {separation:.2f} sigma")


def build_ratio_clip_bounds(normal_features: pd.DataFrame) -> dict[str, float]:
    bounds = {
        column: float(normal_features[column].quantile(0.99))
        for column in RATIO_FEATURES
    }
    bounds["temp_per_current"] = min(bounds["temp_per_current"], 80.0)
    return bounds


def print_ratio_explosion_check(features: pd.DataFrame, title: str) -> None:
    print(f"\n-- Ratio feature range check: {title} --")
    for column in RATIO_FEATURES:
        print(
            f"{column}: "
            f"min={features[column].min():.3f} "
            f"max={features[column].max():.3f} "
            f"99pct={features[column].quantile(0.99):.3f}"
        )


def main() -> None:
    new_df = pd.read_csv(NEW_NORMAL_FILE, parse_dates=["Date"])
    old_df = pd.read_csv(OLD_LABELED_FILE, parse_dates=["Date"])
    old_normal_df = old_df[old_df["target"] == 0].copy()
    normal_fit_df = pd.concat([new_df, old_normal_df], axis=0, ignore_index=True)

    vib_scaler = MinMaxScaler()
    vib_scaler.fit(normal_fit_df[["1x[Vibration]"]])

    x_train_unclipped = build_reduced_features_from_dataset(
        normal_fit_df,
        vib_scaler=vib_scaler,
    )
    ratio_clip_bounds = build_ratio_clip_bounds(x_train_unclipped)
    print_ratio_explosion_check(x_train_unclipped, "normal training data before clipping")
    print("\n-- Ratio clip bounds from normal-only 99th percentiles --")
    for column, upper_bound in ratio_clip_bounds.items():
        print(f"{column}: upper={upper_bound:.3f}")

    x_train = build_reduced_features_from_dataset(
        normal_fit_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    old_reduced = build_reduced_features_from_dataset(
        old_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    y_true = old_df.loc[old_reduced.index, "target"]
    print_regime_check(old_reduced, y_true)

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)

    model = IsolationForest(
        n_estimators=150,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train_scaled)

    old_scaled = scaler.transform(old_reduced)
    y_pred = (model.predict(old_scaled) == -1).astype(int)
    scores = model.decision_function(old_scaled)

    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)
    joblib.dump(vib_scaler, VIB_SCALER_FILE)
    joblib.dump(REDUCED_FEATURE_COLUMNS, FEATURE_COLUMNS_FILE)
    joblib.dump(ratio_clip_bounds, RATIO_CLIP_BOUNDS_FILE)
    np.save(THRESHOLD_FILE, 0.0)

    report = pd.DataFrame(
        {
            "Date": old_df.loc[old_reduced.index, "Date"],
            "target": y_true,
            "reduced_score": scores,
            "is_anomaly": y_pred,
        }
    )
    report.to_csv(REPORT_FILE, index=False)

    print(f"Training rows: {len(x_train)}")
    print(f"Reduced feature count: {len(REDUCED_FEATURE_COLUMNS)}")
    print(f"Reduced features: {REDUCED_FEATURE_COLUMNS}")
    print("Validation on old labeled dataset:")
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"F1: {f1_score(y_true, y_pred, zero_division=0):.4f}")
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(confusion_matrix(y_true, y_pred))
    print()
    print(classification_report(y_true, y_pred, target_names=["Normal", "Anomaly"], zero_division=0))
    print(f"Saved model: {MODEL_FILE}")
    print(f"Saved scaler: {SCALER_FILE}")
    print(f"Saved vibration scaler: {VIB_SCALER_FILE}")
    print(f"Saved feature columns: {FEATURE_COLUMNS_FILE}")
    print(f"Saved ratio clip bounds: {RATIO_CLIP_BOUNDS_FILE}")
    print(f"Saved default reduced threshold: {THRESHOLD_FILE}")
    print(f"Saved evaluation: {REPORT_FILE}")


if __name__ == "__main__":
    main()
