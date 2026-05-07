from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.esp32_feature_mapper import build_reduced_features_from_dataset


OLD_LABELED_FILE = Path("data/clean/clean_data.csv")
MODEL_FILE = Path("models/model_reduced.pkl")
SCALER_FILE = Path("models/scaler_reduced.pkl")
VIB_SCALER_FILE = Path("models/vib_scaler.pkl")
RATIO_CLIP_BOUNDS_FILE = Path("models/reduced_ratio_clip_bounds.joblib")
THRESHOLD_FILE = Path("models/reduced_threshold.npy")
REPORT_FILE = Path("reports/reduced_counter_evaluation.csv")


def main() -> None:
    model = joblib.load(MODEL_FILE)
    scaler = joblib.load(SCALER_FILE)
    vib_scaler = joblib.load(VIB_SCALER_FILE)
    ratio_clip_bounds = joblib.load(RATIO_CLIP_BOUNDS_FILE)
    threshold = float(np.load(THRESHOLD_FILE))

    old_df = pd.read_csv(OLD_LABELED_FILE, parse_dates=["Date"])
    x_old = build_reduced_features_from_dataset(
        old_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    eval_df = old_df.loc[x_old.index].copy()
    scores = model.decision_function(scaler.transform(x_old))
    eval_df["score"] = scores
    eval_df["predicted"] = (scores < threshold).astype(int)
    eval_df["fp"] = (
        (eval_df["predicted"] == 1) & (eval_df["target"] == 0)
    ).astype(int)

    normal_rows = eval_df[eval_df["target"] == 0]
    fp_rate = float(normal_rows["fp"].mean())
    consecutive_fp_probability = fp_rate**5

    counter = 0
    false_alerts = 0
    true_alerts = 0
    alert_rows = []
    counters = []
    for index, row in eval_df.iterrows():
        is_anomaly = row["score"] < threshold
        if is_anomaly:
            counter = min(counter + 2, 10)
        else:
            counter = max(counter - 1, 0)

        counters.append(counter)
        if counter >= 5:
            is_true_alert = int(row["target"]) == 1
            if is_true_alert:
                true_alerts += 1
            else:
                false_alerts += 1
            alert_rows.append(
                {
                    "Date": row["Date"],
                    "target": row["target"],
                    "score": row["score"],
                    "threshold": threshold,
                    "counter": counter,
                    "alert_type": "true_alert" if is_true_alert else "false_alert",
                    "speed_rpm": row.get("speed_rpm"),
                    "Current": row.get("Current"),
                    "temp_mot": row.get("temp_mot"),
                    "1x[Vibration]": row.get("1x[Vibration]"),
                    "Anomaly_Details": row.get("Anomaly_Details"),
                }
            )
            counter = 0

    eval_df["counter_before_alert_reset"] = counters
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(alert_rows).to_csv(REPORT_FILE, index=False)

    print(f"Threshold: {threshold:.6f}")
    print(f"Single-row false positive rate: {fp_rate:.4f}")
    print(f"Probability of 5 consecutive false positives: {consecutive_fp_probability:.4f}")
    print(f"True  MAINTENANCE_ALERTs: {true_alerts}")
    print(f"False MAINTENANCE_ALERTs: {false_alerts}")
    print(f"Saved alert report: {REPORT_FILE}")

    normal_with_bands = normal_rows.copy()
    normal_with_bands["speed_band"] = pd.qcut(
        normal_with_bands["speed_rpm"],
        q=5,
        duplicates="drop",
    )
    print()
    print("False-positive rate by speed band:")
    print(
        normal_with_bands.groupby("speed_band", observed=False)["fp"]
        .mean()
        .to_string()
    )


if __name__ == "__main__":
    main()
