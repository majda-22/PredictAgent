from pathlib import Path
import argparse
import sys

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.agent.decision_policy import DecisionState, make_decision


FEATURES_FILE = Path("data/processed/features_window_new.csv")
SCALER_FILE = Path("models/scaler.joblib")
MODEL_FILE = Path("models/isolation_forest_normal_behavior.joblib")
THRESHOLD_FILE = Path("models/isolation_forest_threshold.npy")
FEATURE_COLUMNS_FILE = Path("models/isolation_feature_columns.joblib")
OUTPUT_FILE = Path("reports/replay_decisions_new.csv")


def load_artifacts() -> tuple[object, object, float, list[str]]:
    scaler = joblib.load(SCALER_FILE)
    model = joblib.load(MODEL_FILE)
    threshold = float(np.load(THRESHOLD_FILE))
    feature_columns = joblib.load(FEATURE_COLUMNS_FILE)
    return scaler, model, threshold, feature_columns


def replay(features_file: Path = FEATURES_FILE, output_file: Path = OUTPUT_FILE) -> pd.DataFrame:
    scaler, model, threshold, feature_columns = load_artifacts()
    df = pd.read_csv(features_file, parse_dates=["Date"])

    missing_columns = sorted(set(feature_columns).difference(df.columns))
    if missing_columns:
        raise ValueError(f"Replay data is missing feature columns: {missing_columns}")

    output_rows = []
    consecutive_anomaly_count = 0
    df = df.sort_values("Date").reset_index(drop=True)
    feature_frame = df[feature_columns]
    scaled_features = scaler.transform(feature_frame)
    scores = model.decision_function(scaled_features)

    for row, score in zip(df.to_dict(orient="records"), scores):
        decision = make_decision(
            score=float(score),
            threshold=threshold,
            consecutive_anomaly_count=consecutive_anomaly_count,
            features=row,
        )
        consecutive_anomaly_count = decision.consecutive_anomaly_count

        output_rows.append(
            {
                "Date": row["Date"],
                "target": row.get("target"),
                "score": float(score),
                "threshold": threshold,
                "is_anomaly": int(decision.is_anomaly),
                "consecutive_anomalies": decision.consecutive_anomaly_count,
                "decision": decision.state.value,
                "reason": decision.reason,
            }
        )

    decisions = pd.DataFrame(output_rows)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(output_file, index=False)
    return decisions


def print_decision_counts(decisions: pd.DataFrame) -> None:
    counts = decisions["decision"].value_counts().to_dict()
    for state in DecisionState:
        print(f"{state.value} count: {counts.get(state.value, 0)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay feature rows through the anomaly decision policy.")
    parser.add_argument("--features-file", type=Path, default=FEATURES_FILE)
    parser.add_argument("--output-file", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    replay_decisions = replay(features_file=args.features_file, output_file=args.output_file)
    print(f"Saved replay output to {args.output_file}")
    print_decision_counts(replay_decisions)
