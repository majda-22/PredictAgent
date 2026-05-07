from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score


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
REPORT_FILE = Path("reports/reduced_threshold_tuning.csv")
PERCENTILES = [1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 50, 60, 70]
MIN_RECALL = 0.90


def main() -> None:
    model = joblib.load(MODEL_FILE)
    scaler = joblib.load(SCALER_FILE)
    vib_scaler = joblib.load(VIB_SCALER_FILE)
    ratio_clip_bounds = joblib.load(RATIO_CLIP_BOUNDS_FILE)

    old_df = pd.read_csv(OLD_LABELED_FILE, parse_dates=["Date"])
    x_old = build_reduced_features_from_dataset(
        old_df,
        vib_scaler=vib_scaler,
        ratio_clip_bounds=ratio_clip_bounds,
    )
    y_true = old_df.loc[x_old.index, "target"].astype(int).to_numpy()
    scores = model.decision_function(scaler.transform(x_old))

    rows = []
    for pct in PERCENTILES:
        threshold = float(np.percentile(scores, pct))
        preds = (scores < threshold).astype(int)
        rows.append(
            {
                "percentile": pct,
                "threshold": threshold,
                "precision": precision_score(y_true, preds, zero_division=0),
                "recall": recall_score(y_true, preds, zero_division=0),
                "f1": f1_score(y_true, preds, zero_division=0),
                "false_positives": int(((preds == 1) & (y_true == 0)).sum()),
                "false_negatives": int(((preds == 0) & (y_true == 1)).sum()),
            }
        )
    default_preds = (scores < 0.0).astype(int)
    rows.append(
        {
            "percentile": "default_0",
            "threshold": 0.0,
            "precision": precision_score(y_true, default_preds, zero_division=0),
            "recall": recall_score(y_true, default_preds, zero_division=0),
            "f1": f1_score(y_true, default_preds, zero_division=0),
            "false_positives": int(((default_preds == 1) & (y_true == 0)).sum()),
            "false_negatives": int(((default_preds == 0) & (y_true == 1)).sum()),
        }
    )

    results = pd.DataFrame(rows)
    eligible = results[results["recall"] >= MIN_RECALL].copy()
    if eligible.empty:
        selected = results.sort_values(["recall", "precision"], ascending=False).iloc[0]
    else:
        selected = eligible.sort_values(["precision", "f1"], ascending=False).iloc[0]

    THRESHOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.save(THRESHOLD_FILE, float(selected["threshold"]))
    results.to_csv(REPORT_FILE, index=False)

    for row in rows:
        print(
            f"pct={row['percentile']!s:>9} "
            f"t={row['threshold']:.6f} "
            f"P={row['precision']:.4f} "
            f"R={row['recall']:.4f} "
            f"F1={row['f1']:.4f} "
            f"FP={row['false_positives']} "
            f"FN={row['false_negatives']}"
        )

    print()
    print(
        "Selected threshold: "
        f"pct={selected['percentile']} "
        f"t={selected['threshold']:.6f} "
        f"P={selected['precision']:.4f} "
        f"R={selected['recall']:.4f} "
        f"F1={selected['f1']:.4f}"
    )
    print(f"Saved threshold: {THRESHOLD_FILE}")
    print(f"Saved report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
