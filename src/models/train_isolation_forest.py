from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import RobustScaler


NORMAL_FEATURES_FILE = Path("data/processed/features_window_new.csv")
OLD_FEATURES_FILE = Path("data/processed/features_window.csv")
MODEL_FILE = Path("models/isolation_forest_normal_behavior.joblib")
SCALER_FILE = Path("models/scaler.joblib")
THRESHOLD_FILE = Path("models/isolation_forest_threshold.npy")
FEATURE_COLUMNS_FILE = Path("models/isolation_feature_columns.joblib")
EXPERIMENT_RESULTS_FILE = Path("reports/isolation_forest_experiment_results.csv")
NORMAL_SCORES_FILE = Path("reports/isolation_forest_normal_scores.csv")
OLD_SCORES_FILE = Path("reports/isolation_forest_old_validation_scores.csv")
SCORE_HISTOGRAM_FILE = Path("reports/isolation_forest_score_histogram.png")
OLD_SCORE_HISTOGRAM_FILE = Path("reports/isolation_forest_old_score_histogram.png")
TARGET_COLUMN = "target"
DROP_COLUMNS = [
    "Date",
    "Anomaly",
    "Anomaly_Details",
    "Anomaly_Count",
    "File",
    "dataset_id",
    TARGET_COLUMN,
]
CONTAMINATION = 0.05
THRESHOLD_PERCENTILES = [1, 2, 3, 5]
RANDOM_STATE = 42


def load_feature_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"])
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column in {path}: {TARGET_COLUMN}")
    return df.sort_values("Date").reset_index(drop=True)


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in df.columns
        if column not in DROP_COLUMNS and pd.api.types.is_numeric_dtype(df[column])
    ]


def validate_feature_columns(normal_df: pd.DataFrame, old_df: pd.DataFrame) -> list[str]:
    normal_features = feature_columns(normal_df)
    old_features = feature_columns(old_df)
    if normal_features != old_features:
        missing_in_old = sorted(set(normal_features).difference(old_features))
        missing_in_normal = sorted(set(old_features).difference(normal_features))
        raise ValueError(
            "Feature columns are not identical. "
            f"Missing in old: {missing_in_old}. Missing in normal: {missing_in_normal}"
        )
    return normal_features


def fit_normal_scaler(
    normal_df: pd.DataFrame,
    old_df: pd.DataFrame,
    columns: list[str],
) -> RobustScaler:
    x_new_normal = normal_df[columns]
    x_old_normal = old_df.loc[old_df[TARGET_COLUMN] == 0, columns]
    x_scaler_fit = pd.concat([x_new_normal, x_old_normal], axis=0, ignore_index=True)

    scaler = RobustScaler()
    scaler.fit(x_scaler_fit)
    return scaler


def train_isolation_forest(x_train: np.ndarray) -> IsolationForest:
    model = IsolationForest(
        n_estimators=300,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    model.fit(x_train)
    return model


def evaluate_scores(
    y_true: pd.Series,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, object]:
    y_pred = (scores < threshold).astype(int)
    matrix = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = matrix.ravel()
    return {
        "threshold": threshold,
        "flagged": int(y_pred.sum()),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "true_negatives": int(tn),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": matrix,
        "y_pred": y_pred,
    }


def select_best_result(results: list[dict[str, object]]) -> dict[str, object]:
    # Keep recall high first, then reduce false positives, then maximize F1.
    return sorted(
        results,
        key=lambda row: (
            -float(row["recall"]),
            int(row["false_positives"]),
            -float(row["f1"]),
        ),
    )[0]


def plot_scores(
    scores: np.ndarray,
    threshold: float,
    output_file: Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(scores, bins=50, color="steelblue", alpha=0.75)
    ax.axvline(threshold, color="crimson", linestyle="--", label=f"threshold = {threshold:.4f}")
    ax.set_title(title)
    ax.set_xlabel("Isolation Forest decision_function score")
    ax.set_ylabel("Rows")
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close(fig)


def main() -> None:
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    normal_df = load_feature_data(NORMAL_FEATURES_FILE)
    old_df = load_feature_data(OLD_FEATURES_FILE)
    columns = validate_feature_columns(normal_df, old_df)

    scaler = fit_normal_scaler(normal_df, old_df, columns)
    x_new_scaled = scaler.transform(normal_df[columns])
    x_old_scaled = scaler.transform(old_df[columns])
    x_old_normal_scaled = scaler.transform(old_df.loc[old_df[TARGET_COLUMN] == 0, columns])

    experiments = {
        "A_new_normal_only": x_new_scaled,
        "B_new_plus_old_normal": np.vstack([x_new_scaled, x_old_normal_scaled]),
    }

    y_old = old_df[TARGET_COLUMN]
    experiment_rows = []
    trained_models: dict[str, IsolationForest] = {}
    score_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    for experiment_name, x_train_scaled in experiments.items():
        model = train_isolation_forest(x_train_scaled)
        trained_models[experiment_name] = model

        train_scores = model.decision_function(x_train_scaled)
        old_scores = model.decision_function(x_old_scaled)
        score_cache[experiment_name] = (train_scores, old_scores)

        for percentile in THRESHOLD_PERCENTILES:
            threshold = float(np.percentile(train_scores, percentile))
            metrics = evaluate_scores(y_old, old_scores, threshold)
            experiment_rows.append(
                {
                    "experiment": experiment_name,
                    "threshold_percentile": percentile,
                    "threshold": threshold,
                    "train_rows": len(x_train_scaled),
                    "old_flagged": metrics["flagged"],
                    "false_positives": metrics["false_positives"],
                    "false_negatives": metrics["false_negatives"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                }
            )

    results = pd.DataFrame(experiment_rows)
    results.to_csv(EXPERIMENT_RESULTS_FILE, index=False)

    best = select_best_result(experiment_rows)
    best_experiment = str(best["experiment"])
    best_percentile = int(best["threshold_percentile"])
    best_threshold = float(best["threshold"])
    best_model = trained_models[best_experiment]
    best_train_scores, best_old_scores = score_cache[best_experiment]
    best_metrics = evaluate_scores(y_old, best_old_scores, best_threshold)

    normal_scores_df = normal_df[["Date", TARGET_COLUMN]].copy()
    normal_scores_df["score"] = best_model.decision_function(x_new_scaled)
    normal_scores_df["is_suspicious"] = (normal_scores_df["score"] < best_threshold).astype(int)
    normal_scores_df.to_csv(NORMAL_SCORES_FILE, index=False)

    old_scores_df = old_df[["Date", TARGET_COLUMN, "Anomaly", "Anomaly_Details"]].copy()
    old_scores_df["score"] = best_old_scores
    old_scores_df["is_suspicious"] = best_metrics["y_pred"]
    old_scores_df.to_csv(OLD_SCORES_FILE, index=False)

    plot_scores(
        best_train_scores,
        best_threshold,
        SCORE_HISTOGRAM_FILE,
        f"Isolation Forest Training Scores - {best_experiment}",
    )
    plot_scores(
        best_old_scores,
        best_threshold,
        OLD_SCORE_HISTOGRAM_FILE,
        "Isolation Forest Scores - Old Labeled Dataset",
    )

    joblib.dump(scaler, SCALER_FILE)
    joblib.dump(best_model, MODEL_FILE)
    joblib.dump(columns, FEATURE_COLUMNS_FILE)
    np.save(THRESHOLD_FILE, best_threshold)

    print(f"New normal rows: {len(normal_df)}")
    print(f"Old labeled rows: {len(old_df)}")
    print(f"Old normal rows used for scaler: {int((old_df[TARGET_COLUMN] == 0).sum())}")
    print(f"Feature columns: {len(columns)}")
    print(f"Scaler: RobustScaler fit on new normal + old normal only")
    print()
    print("Experiment comparison:")
    print(
        results[
            [
                "experiment",
                "threshold_percentile",
                "old_flagged",
                "false_positives",
                "false_negatives",
                "precision",
                "recall",
                "f1",
            ]
        ].to_string(index=False)
    )
    print()
    print(f"Selected experiment: {best_experiment}")
    print(f"Selected threshold percentile: {best_percentile}%")
    print(f"Selected threshold: {best_threshold:.6f}")
    print("Validation on old labeled dataset:")
    print(f"Flagged rows: {best_metrics['flagged']} / {len(old_df)}")
    print(f"False positives: {best_metrics['false_positives']}")
    print(f"False negatives: {best_metrics['false_negatives']}")
    print(f"Precision: {best_metrics['precision']:.4f}")
    print(f"Recall: {best_metrics['recall']:.4f}")
    print(f"F1: {best_metrics['f1']:.4f}")
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(best_metrics["confusion_matrix"])
    print()
    print(
        classification_report(
            y_old,
            best_metrics["y_pred"],
            target_names=["Normal", "Anomaly"],
            zero_division=0,
        )
    )
    print(f"Saved scaler: {SCALER_FILE}")
    print(f"Saved model: {MODEL_FILE}")
    print(f"Saved threshold: {THRESHOLD_FILE}")
    print(f"Saved feature columns: {FEATURE_COLUMNS_FILE}")
    print(f"Saved experiment results: {EXPERIMENT_RESULTS_FILE}")
    print(f"Saved normal scores: {NORMAL_SCORES_FILE}")
    print(f"Saved old validation scores: {OLD_SCORES_FILE}")


if __name__ == "__main__":
    main()
