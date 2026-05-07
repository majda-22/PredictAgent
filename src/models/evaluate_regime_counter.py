from pathlib import Path
import sys

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.esp32_feature_mapper import build_reduced_features_from_dataset


OLD_LABELED_FILE = Path("data/clean/clean_data.csv")
REGIME_MODEL_FILE = Path("models/regime_kmeans.joblib")
REGIME_SCALER_FILE = Path("models/regime_scaler.joblib")
REGIME_IFOREST_FILE = Path("models/regime_isolation_forests.joblib")
REGIME_FEATURE_SCALERS_FILE = Path("models/regime_feature_scalers.joblib")
REGIME_THRESHOLDS_FILE = Path("models/regime_thresholds.joblib")
REGIME1_MODEL_FILE = Path("models/regime1_kmeans.joblib")
REGIME1_IFOREST_FILE = Path("models/regime1_sub_models.joblib")
REGIME1_FEATURE_SCALERS_FILE = Path("models/regime1_sub_feature_scalers.joblib")
REGIME1_THRESHOLDS_FILE = Path("models/regime1_sub_thresholds.joblib")
VIB_SCALER_FILE = Path("models/vib_scaler.pkl")
RATIO_CLIP_BOUNDS_FILE = Path("models/reduced_ratio_clip_bounds.joblib")
REPORT_FILE = Path("reports/regime_counter_evaluation.csv")
REGIME_COLUMNS = ["speed_rpm", "current_per_rpm"]
REGIME_COUNTER_THRESHOLDS = {0: 3, 2: 5}
REGIME1_COUNTER_THRESHOLDS = {0: 7, 1: 10}


def main() -> None:
    regime_model = joblib.load(REGIME_MODEL_FILE)
    regime_scaler = joblib.load(REGIME_SCALER_FILE)
    models = joblib.load(REGIME_IFOREST_FILE)
    feature_scalers = joblib.load(REGIME_FEATURE_SCALERS_FILE)
    thresholds = joblib.load(REGIME_THRESHOLDS_FILE)
    regime1_model = joblib.load(REGIME1_MODEL_FILE)
    regime1_models = joblib.load(REGIME1_IFOREST_FILE)
    regime1_feature_scalers = joblib.load(REGIME1_FEATURE_SCALERS_FILE)
    regime1_thresholds = joblib.load(REGIME1_THRESHOLDS_FILE)
    vib_scaler = joblib.load(VIB_SCALER_FILE)
    ratio_clip_bounds = joblib.load(RATIO_CLIP_BOUNDS_FILE)

    old_df = pd.read_csv(OLD_LABELED_FILE, parse_dates=["Date"])
    x_old = build_reduced_features_from_dataset(
        old_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    eval_df = old_df.loc[x_old.index].copy()
    regimes = regime_model.predict(regime_scaler.transform(x_old[REGIME_COLUMNS]))
    eval_df["regime"] = regimes
    eval_df["sub_regime"] = -1
    eval_df["score"] = 0.0
    eval_df["threshold"] = 0.0
    eval_df["predicted"] = 0

    for regime in sorted(set(regimes)):
        mask = regimes == regime
        if int(regime) == 1:
            regime_features = x_old.loc[mask]
            sub_labels = regime1_model.predict(regime_features[REGIME_COLUMNS])
            eval_df.loc[mask, "sub_regime"] = sub_labels
            regime_indices = regime_features.index
            for sub_regime in sorted(set(sub_labels)):
                sub_indices = regime_indices[sub_labels == sub_regime]
                scores = regime1_models[int(sub_regime)].decision_function(
                    regime1_feature_scalers[int(sub_regime)].transform(x_old.loc[sub_indices])
                )
                threshold = float(regime1_thresholds[int(sub_regime)])
                eval_df.loc[sub_indices, "score"] = scores
                eval_df.loc[sub_indices, "threshold"] = threshold
                eval_df.loc[sub_indices, "predicted"] = (scores < threshold).astype(int)
        else:
            scores = models[int(regime)].decision_function(
                feature_scalers[int(regime)].transform(x_old.loc[mask])
            )
            threshold = float(thresholds[int(regime)])
            eval_df.loc[mask, "score"] = scores
            eval_df.loc[mask, "threshold"] = threshold
            eval_df.loc[mask, "predicted"] = (scores < threshold).astype(int)

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
    for _, row in eval_df.iterrows():
        if row["score"] < row["threshold"]:
            counter = min(counter + 2, 10)
        else:
            counter = max(counter - 1, 0)

        if int(row["regime"]) == 1:
            required_count = REGIME1_COUNTER_THRESHOLDS.get(
                int(row["sub_regime"]),
                7,
            )
        else:
            required_count = REGIME_COUNTER_THRESHOLDS.get(int(row["regime"]), 5)
        if counter >= required_count:
            is_true_alert = int(row["target"]) == 1
            if is_true_alert:
                true_alerts += 1
            else:
                false_alerts += 1
            alert_rows.append(
                {
                    "Date": row["Date"],
                    "target": row["target"],
                    "regime": row["regime"],
                    "sub_regime": row["sub_regime"],
                    "score": row["score"],
                    "threshold": row["threshold"],
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

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(alert_rows).to_csv(REPORT_FILE, index=False)

    print(f"Single-row false positive rate: {fp_rate:.4f}")
    print(f"Probability of 5 consecutive false positives: {consecutive_fp_probability:.4f}")
    print(f"True  MAINTENANCE_ALERTs: {true_alerts}")
    print(f"False MAINTENANCE_ALERTs: {false_alerts}")
    print(f"Saved alert report: {REPORT_FILE}")
    print()
    print("False-positive rate by regime:")
    print(
        normal_rows.groupby("regime", observed=False)["fp"]
        .mean()
        .to_string()
    )
    print()
    print("False-positive rate by regime/sub-regime:")
    print(
        normal_rows.groupby(["regime", "sub_regime"], observed=False)["fp"]
        .mean()
        .to_string()
    )
    if len(alert_rows) > 0:
        alerts = pd.DataFrame(alert_rows)
        print()
        print("False alerts by regime/sub-regime:")
        false_alerts = alerts[alerts["alert_type"] == "false_alert"]
        if false_alerts.empty:
            print("none")
        else:
            print(
                false_alerts.groupby(["regime", "sub_regime"], observed=False)
                .size()
                .to_string()
            )
        print()
        print("True alerts by regime/sub-regime:")
        true_alerts = alerts[alerts["alert_type"] == "true_alert"]
        if true_alerts.empty:
            print("none")
        else:
            print(
                true_alerts.groupby(["regime", "sub_regime"], observed=False)
                .size()
                .to_string()
            )
    print()
    print("False-positive rate by speed band:")
    normal_with_bands = normal_rows.copy()
    normal_with_bands["speed_band"] = pd.qcut(
        normal_with_bands["speed_rpm"],
        q=5,
        duplicates="drop",
    )
    print(
        normal_with_bands.groupby("speed_band", observed=False)["fp"]
        .mean()
        .to_string()
    )


if __name__ == "__main__":
    main()
